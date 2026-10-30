import io
import json
import math
import pytest
from app.data.indicators import CATALOG, compute_indicators
from app.data.ingestion import load_fallback
from app.demo_models.registry import demo_model_path, load_manifest
from app.pipeline.sandbox_client import SandboxClient
from app.tests.conftest import requires_docker

EXPECTED_IDS = ["demo_decision_tree", "demo_logistic_regression", "demo_mlp", "demo_xgboost"]
EXPECTED_FEATURES = ["rsi_14", "vol_20d", "sma_ratio_20_50", "macd_hist", "ret_lag_5", "atr_14_pct", "ema_ratio_12_26", "ret_lag_1"]
PROBABILITY_THRESHOLD = 0.5


def test_manifest_lists_four_models_with_consistent_fields():
    models = load_manifest()
    assert [model["id"] for model in models] == EXPECTED_IDS
    for model in models:
        assert set(model) == {"id", "name", "family", "file", "feature_columns", "signal_type", "explained_output", "trained_on"}
        assert model["file"] == f"{model['id']}.joblib"
        assert model["signal_type"] == "discrete"
        assert model["explained_output"] == "P(buy)"
        assert model["feature_columns"] == EXPECTED_FEATURES
        assert model["trained_on"]["ticker"] == "SPY"
        assert model["trained_on"]["start"] >= "2010-01-01"
        assert model["trained_on"]["end"] <= "2017-12-31"
        assert demo_model_path(model).endswith(model["file"])


def test_demo_feature_columns_are_catalog_ids():
    for model in load_manifest():
        assert all(feature in CATALOG for feature in model["feature_columns"])


def test_demo_models_endpoint(make_api):
    client, _ = make_api()
    body = client.get("/demo-models").json()
    assert [model["id"] for model in body["models"]] == EXPECTED_IDS


def test_demo_id_bypasses_the_upload_cap_and_kill_switch(make_api, monkeypatch):
    monkeypatch.setenv("ALLOW_UPLOAD", "false")
    monkeypatch.setenv("MAX_MODEL_FILE_BYTES", "1")
    client, services = make_api()
    response = client.post(
        "/analysis/run",
        data={"demo_model_id": "demo_xgboost", "ticker": "SPY", "start_date": "2019-01-01", "end_date": "2020-12-31", "feature_ids": json.dumps(["rsi_14"])},
        files={"model_file": ("ignored.pkl", io.BytesIO(b"xx"), "application/octet-stream")},
    )
    assert response.status_code == 202
    row = services.repository.get_analysis(response.json()["analysis_id"])
    assert row["model_meta"]["source"] == "demo"
    assert row["model_meta"]["demo_model_id"] == "demo_xgboost"
    assert row["params"]["feature_ids"] == EXPECTED_FEATURES


def test_unknown_demo_id_gives_404(make_api):
    client, _ = make_api()
    response = client.post(
        "/analysis/run",
        data={"demo_model_id": "nope", "ticker": "SPY", "start_date": "2019-01-01", "end_date": "2020-12-31"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "unknown_demo_model"


@requires_docker
@pytest.mark.parametrize("demo_id", EXPECTED_IDS)
def test_demo_model_runs_through_preflight_and_predict(demo_id):
    entry = next(model for model in load_manifest() if model["id"] == demo_id)
    ohlcv = load_fallback("SPY", "2018-01-01", "2019-12-31")
    features = compute_indicators(ohlcv, entry["feature_columns"]).dropna()
    rows = features.to_numpy().tolist()
    sandbox = SandboxClient()

    preflight = sandbox.preflight(demo_model_path(entry), entry["feature_columns"], rows[:5], 120)
    outputs = sandbox.predict(demo_model_path(entry), preflight["column_order"], rows, 120)["outputs"]

    assert preflight["column_order"] == entry["feature_columns"]
    assert preflight["signal_type"] == "discrete"
    assert len(outputs) == len(rows)
    assert all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in outputs)
    signals = {1 if value >= PROBABILITY_THRESHOLD else -1 for value in outputs}
    assert signals <= {-1, 1}


@requires_docker
def test_demo_run_end_to_end_with_kernel_shap(make_api, monkeypatch):
    import time
    from app.pipeline import stages
    from app.tests.test_pipeline import bundled_fetch, ok_report

    monkeypatch.setattr(stages, "fetch_ohlcv", bundled_fetch)
    client, services = make_api(run_job=None, report_generator=ok_report)
    started = time.monotonic()
    response = client.post(
        "/analysis/run",
        data={"demo_model_id": "demo_logistic_regression", "ticker": "SPY", "start_date": "2018-01-01", "end_date": "2020-12-31"},
    )
    analysis_id = response.json()["analysis_id"]
    services.job_manager.wait(analysis_id, timeout=400)
    body = client.get(f"/analysis/{analysis_id}").json()

    assert body["status"] == "completed", body["error"]
    assert body["result"]["shap"]["explainer"] == "kernel"
    assert body["result"]["shap"]["max_additivity_gap"] < 0.01
    assert time.monotonic() - started < 300
