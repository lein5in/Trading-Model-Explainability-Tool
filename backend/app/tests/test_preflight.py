import io
import json
import pickle
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeClassifier
from app.data.indicators import compute_indicators
from app.data.ingestion import load_fallback
from app.pipeline import stages
from app.sandbox.predict_entrypoint import handle_predict, handle_preflight
from app.sandbox.sandbox_common import SandboxTaskError
from app.sandbox.runner import SandboxExecutionError, run_preflight_in_sandbox
from app.tests.conftest import requires_docker
from app.tests.test_pipeline import WAIT_SECONDS, bundled_fetch, ok_report

COLUMNS = ["a", "b", "c"]


def training_frame(n: int = 60) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(n, 3)), columns=COLUMNS)
    return X, (X["a"] - X["c"] > 0).astype(int).to_numpy()


def payload(model_columns: list[str], X: pd.DataFrame) -> dict:
    return {"mode": "preflight", "feature_names": model_columns, "rows": X[model_columns].iloc[:5].to_numpy().tolist()}


def test_preflight_rejects_wrong_column_names():
    X, y = training_frame()
    model = DecisionTreeClassifier(max_depth=2).fit(X, y)
    renamed = X.rename(columns={"c": "z"})
    with pytest.raises(SandboxTaskError) as excinfo:
        handle_preflight(model, payload(["a", "b", "z"], renamed))
    assert excinfo.value.code == "feature_mismatch"
    assert excinfo.value.details["missing"] == ["c"]
    assert excinfo.value.details["unexpected"] == ["z"]
    assert "['c']" in str(excinfo.value) and "['z']" in str(excinfo.value)


def test_preflight_rejects_wrong_feature_count():
    X, y = training_frame()
    model = DecisionTreeClassifier(max_depth=2).fit(X.to_numpy(), y)
    with pytest.raises(SandboxTaskError) as excinfo:
        handle_preflight(model, payload(["a", "b"], X))
    assert excinfo.value.code == "feature_count_mismatch"
    assert excinfo.value.details == {"expected": 3, "provided": 2}


def test_preflight_rejects_a_model_that_cannot_predict():
    X, _ = training_frame()
    with pytest.raises(SandboxTaskError) as excinfo:
        handle_preflight(DecisionTreeClassifier(), payload(COLUMNS, X))
    assert excinfo.value.code == "predict_failed"


def test_preflight_rejects_an_unsupported_object():
    X, _ = training_frame()
    with pytest.raises(SandboxTaskError) as excinfo:
        handle_preflight({"not": "a model"}, payload(COLUMNS, X))
    assert excinfo.value.code == "unsupported_model"


def test_preflight_accepts_a_permuted_order_and_reorders():
    X, y = training_frame()
    model = DecisionTreeClassifier(max_depth=3, random_state=0).fit(X, y)
    permuted = ["c", "a", "b"]
    result = handle_preflight(model, payload(permuted, X))
    assert result["column_order"] == COLUMNS
    assert result["reordered"] is True
    assert result["sample_outputs"] == pytest.approx(model.predict_proba(X.iloc[:5])[:, 1].tolist())
    predicted = handle_predict(model, {"feature_names": result["column_order"], "rows": X[COLUMNS].to_numpy().tolist()})
    assert predicted["outputs"] == pytest.approx(model.predict_proba(X)[:, 1].tolist())


def test_preflight_infers_the_signal_type():
    X, y = training_frame()
    classifier = handle_preflight(DecisionTreeClassifier(max_depth=2).fit(X, y), payload(COLUMNS, X))
    regressor = handle_preflight(LinearRegression().fit(X, X["a"]), payload(COLUMNS, X))
    assert classifier["signal_type"] == "discrete"
    assert classifier["explained_output"] == "P(buy)"
    assert classifier["family"] == "DecisionTreeClassifier"
    assert regressor["signal_type"] == "continuous"
    assert regressor["explained_output"] == "prediction"


@requires_docker
def test_preflight_rejection_inside_the_sandbox(tmp_path):
    X, y = training_frame()
    path = tmp_path / "model.pkl"
    path.write_bytes(pickle.dumps(DecisionTreeClassifier(max_depth=2).fit(X, y)))
    with pytest.raises(SandboxExecutionError) as excinfo:
        run_preflight_in_sandbox(str(path), ["a", "b", "z"], X.iloc[:5].to_numpy().tolist())
    assert excinfo.value.code == "feature_mismatch"


def spy_training_model() -> tuple[DecisionTreeClassifier, list[str]]:
    features = ["rsi_14", "vol_20d", "ret_lag_5"]
    ohlcv = load_fallback("SPY", "2010-01-01", "2014-12-31")
    values = compute_indicators(ohlcv, features)
    label = (ohlcv["close"].shift(-1) > ohlcv["close"]).astype(int)
    mask = values.notna().all(axis=1) & ohlcv["close"].shift(-1).notna()
    model = DecisionTreeClassifier(max_depth=4, random_state=0).fit(values[mask], label[mask])
    return model, features


@requires_docker
def test_pipeline_end_to_end_with_the_real_sandbox(make_api, monkeypatch):
    monkeypatch.setattr(stages, "fetch_ohlcv", bundled_fetch)
    model, features = spy_training_model()
    client, services = make_api(run_job=None, report_generator=ok_report)
    response = client.post(
        "/analysis/run",
        data={"ticker": "SPY", "start_date": "2016-01-01", "end_date": "2017-12-31", "feature_ids": json.dumps(list(reversed(features)))},
        files={"model_file": ("tree.pkl", io.BytesIO(pickle.dumps(model)), "application/octet-stream")},
    )
    analysis_id = response.json()["analysis_id"]
    services.job_manager.wait(analysis_id, timeout=WAIT_SECONDS * 5)
    body = client.get(f"/analysis/{analysis_id}").json()

    assert body["status"] == "completed", body["error"]
    assert body["model_meta"]["feature_columns"] == features
    assert body["model_meta"]["columns_reordered"] is True
    assert body["result"]["shap"]["explainer"] == "tree"
    assert body["result"]["shap"]["max_additivity_gap"] < 0.01
    signals = [s for s in body["result"]["predictions"]["signal"] if s is not None]
    assert set(signals) <= {-1, 1}
    json.dumps(body, allow_nan=False)
