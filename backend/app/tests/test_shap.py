import pickle
import numpy as np
import pandas as pd
import pytest
from lightgbm import LGBMClassifier
from sklearn.ensemble import (
    BaggingClassifier,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier
from app.explainability.shap_engine import ShapConfig, ShapStageError, allocate, compute_shap, stratified_sample
from app.tests.tests_synthetic import build_rsi_only_frame, build_rsi_only_model, run_single_feature_sanity_check
from app.sandbox.explain_core import AdditivityError, explain, positive_class_index, select_output
from app.sandbox.runner import SandboxExecutionError
from app.tests.conftest import requires_docker

EPSILON = 0.01
FEATURES = ["f0", "f1", "f2", "f3"]
N_ROWS = 400
EXPLAINED_ROWS = 40


def synthetic_data(seed: int = 0) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.normal(size=(N_ROWS, len(FEATURES))), columns=FEATURES)
    score = 2.0 * X["f0"] - X["f1"] + 0.5 * X["f2"] + rng.normal(scale=0.8, size=N_ROWS)
    return X, (score > 0).astype(int).to_numpy(), score.to_numpy()


CLASSIFIERS = {
    "decision_tree": (lambda: DecisionTreeClassifier(max_depth=4, random_state=0), "tree"),
    "random_forest": (lambda: RandomForestClassifier(n_estimators=20, max_depth=4, random_state=0), "tree"),
    "gradient_boosting": (lambda: GradientBoostingClassifier(n_estimators=30, max_depth=2, random_state=0), "tree"),
    "xgboost": (lambda: XGBClassifier(n_estimators=30, max_depth=3, random_state=0), "tree"),
    "lightgbm": (lambda: LGBMClassifier(n_estimators=30, max_depth=3, random_state=0, verbose=-1), "tree"),
    "logistic_regression": (lambda: LogisticRegression(), "kernel"),
    "mlp": (lambda: MLPClassifier(hidden_layer_sizes=(8, 4), max_iter=800, random_state=0), "kernel"),
    "pipeline_logistic": (lambda: Pipeline([("scale", StandardScaler()), ("model", LogisticRegression())]), "kernel"),
}


@pytest.mark.parametrize("name", list(CLASSIFIERS))
def test_classifier_additivity_against_probability(name):
    factory, expected_explainer = CLASSIFIERS[name]
    X, labels, _ = synthetic_data()
    model = factory().fit(X, labels)

    result = explain(model, X.iloc[:EXPLAINED_ROWS], X.iloc[:100])

    assert result["explainer"] == expected_explainer
    assert result["explained_output"] == "P(buy)"
    assert result["explained_class"] == 1
    assert result["values"].shape == (EXPLAINED_ROWS, len(FEATURES))
    probabilities = model.predict_proba(X.iloc[:EXPLAINED_ROWS])[:, 1]
    reconstructed = result["values"].sum(axis=1) + result["base_value"]
    assert np.max(np.abs(reconstructed - probabilities)) < EPSILON
    assert result["max_additivity_gap"] < EPSILON


def test_regressor_additivity_against_prediction():
    X, _, score = synthetic_data()
    model = GradientBoostingRegressor(n_estimators=30, max_depth=2, random_state=0).fit(X, score)

    result = explain(model, X.iloc[:EXPLAINED_ROWS], X.iloc[:100])

    assert result["explainer"] == "tree"
    assert result["explained_output"] == "prediction"
    reconstructed = result["values"].sum(axis=1) + result["base_value"]
    assert np.max(np.abs(reconstructed - model.predict(X.iloc[:EXPLAINED_ROWS]))) < EPSILON


def test_additivity_is_checked_against_probability_not_labels():
    X, labels, _ = synthetic_data()
    model = RandomForestClassifier(n_estimators=20, max_depth=3, random_state=0).fit(X, labels)
    rows = X.iloc[:EXPLAINED_ROWS]

    result = explain(model, rows, X.iloc[:100])
    reconstructed = result["values"].sum(axis=1) + result["base_value"]

    assert np.max(np.abs(reconstructed - model.predict_proba(rows)[:, 1])) < EPSILON
    assert np.max(np.abs(reconstructed - model.predict(rows))) > EPSILON


def test_three_dimensional_output_yields_the_positive_class():
    raw = np.arange(24, dtype=float).reshape(4, 3, 2)
    values, base = select_output(raw, np.array([0.3, 0.7]), positive_index=1)
    np.testing.assert_array_equal(values, raw[:, :, 1])
    assert base == 0.7
    values, base = select_output(raw, np.array([0.3, 0.7]), positive_index=0)
    np.testing.assert_array_equal(values, raw[:, :, 0])
    assert base == 0.3


def test_list_output_yields_the_positive_class():
    raw = [np.zeros((2, 3)), np.ones((2, 3))]
    values, base = select_output(raw, [0.4, 0.6], positive_index=1)
    np.testing.assert_array_equal(values, np.ones((2, 3)))
    assert base == 0.6


def test_positive_class_is_one_when_present_else_the_largest_label():
    X, labels, _ = synthetic_data()
    signed = DecisionTreeClassifier(max_depth=2).fit(X, np.where(labels == 1, 1, -1))
    shifted = DecisionTreeClassifier(max_depth=2).fit(X, np.where(labels == 1, 5, 2))
    assert positive_class_index(signed) == list(signed.classes_).index(1)
    assert positive_class_index(shifted) == list(shifted.classes_).index(5)
    result = explain(shifted, X.iloc[:10], X.iloc[:50])
    assert result["explained_class"] == 5


def test_rsi_only_model_puts_all_importance_on_rsi():
    frame = build_rsi_only_frame()
    model = build_rsi_only_model(frame)
    features = frame[["rsi_14", "noise_feature"]]

    result = explain(model, features.iloc[:100], features)
    importance = np.abs(result["values"]).mean(axis=0)

    assert importance[0] / importance.sum() > 0.99


def test_unsupported_tree_model_falls_back_to_kernel():
    X, labels, _ = synthetic_data()
    model = BaggingClassifier(estimator=DecisionTreeClassifier(max_depth=3), n_estimators=5, random_state=0).fit(X, labels)

    result = explain(model, X.iloc[:20], X.iloc[:100])

    assert result["explainer"] == "kernel"
    assert result["max_additivity_gap"] < EPSILON


def test_additivity_failure_is_blocking():
    X, labels, _ = synthetic_data()
    model = DecisionTreeClassifier(max_depth=3, random_state=0).fit(X, labels)
    with pytest.raises(AdditivityError) as excinfo:
        explain(model, X.iloc[:10], X.iloc[:50], epsilon=-1.0)
    assert excinfo.value.max_gap >= 0.0


def test_allocation_is_proportional_with_a_minimum():
    assert allocate({0: 1200, 1: 600, 2: 200}, 600, 30) == {0: 360, 1: 180, 2: 60}
    assert allocate({0: 1950, 1: 50}, 600, 30) == {0: 570, 1: 30}
    assert allocate({0: 100, 1: 20}, 600, 30) == {0: 100, 1: 20}


def regime_frame(regime_sizes: list[int]) -> tuple[pd.DataFrame, list[int]]:
    regimes = [index for index, size in enumerate(regime_sizes) for _ in range(size)]
    rng = np.random.default_rng(1)
    frame = pd.DataFrame(rng.normal(size=(len(regimes), len(FEATURES))), columns=FEATURES)
    frame.insert(0, "date", pd.date_range("2015-01-01", periods=len(regimes), freq="D").strftime("%Y-%m-%d"))
    return frame, regimes


def fake_explainer(calls: list):
    def run(model_path, payload, timeout_seconds):
        calls.append(payload)
        n_features = len(payload["feature_names"])
        global_rows = np.asarray(payload["global_rows"]).reshape(-1, n_features)
        trade_rows = np.asarray(payload["trade_rows"]).reshape(-1, n_features)
        return {
            "explainer": "tree",
            "explained_output": "P(buy)",
            "explained_class": 1,
            "base_value": 0.5,
            "max_additivity_gap": 0.0,
            "global_values": (global_rows * 0.01).tolist(),
            "global_outputs": [0.5] * len(global_rows),
            "trade_values": (trade_rows * 0.01).tolist(),
            "trade_outputs": [0.6] * len(trade_rows),
        }
    return run


def test_stratified_sampling_respects_regime_proportions_and_flags_low_samples():
    frame, regimes = regime_frame([1200, 600, 200])
    shuffled = list(np.random.default_rng(3).permutation(regimes))
    calls = []
    result = compute_shap(
        "model.pkl", frame, FEATURES, list(range(len(frame))),
        {"regimes_available": True, "regime_index_per_bar": shuffled}, [],
        ShapConfig(), 60, run_explain=fake_explainer(calls),
    )["shap"]

    by_regime = result["feature_importance_by_regime"]
    assert [by_regime[name]["n_rows"] for name in ["Low vol", "Mid vol", "High vol"]] == [360, 180, 60]
    assert [by_regime[name]["low_sample"] for name in ["Low vol", "Mid vol", "High vol"]] == [False, False, True]
    assert result["sampling"] == "stratified_by_regime"
    assert result["sample_size"] == 600


def test_regime_without_rows_returns_null_importance():
    frame, regimes = regime_frame([500, 300])
    result = compute_shap(
        "model.pkl", frame, FEATURES, list(range(len(frame))),
        {"regimes_available": True, "regime_index_per_bar": regimes}, [],
        ShapConfig(), 60, run_explain=fake_explainer([]),
    )["shap"]
    high = result["feature_importance_by_regime"]["High vol"]
    assert high == {"n_rows": 0, "low_sample": True, "importance": None}


def test_uniform_sampling_when_regimes_are_unavailable():
    frame, _ = regime_frame([1000])
    calls = []
    result = compute_shap(
        "model.pkl", frame, FEATURES, list(range(len(frame))),
        {"regimes_available": False}, [], ShapConfig(), 60, run_explain=fake_explainer(calls),
    )["shap"]
    assert result["feature_importance_by_regime"] is None
    assert result["sampling"] == "uniform"
    assert len(calls[0]["global_rows"]) == 600


def test_shap_row_index_points_into_the_trade_array():
    frame, regimes = regime_frame([300, 300])
    trades = [
        {"id": 1, "signal_bar_index": 10},
        {"id": 2, "signal_bar_index": 25},
        {"id": 3, "signal_bar_index": 40},
    ]
    eligible = [p for p in range(len(frame)) if p != 25]
    calls = []
    output = compute_shap(
        "model.pkl", frame, FEATURES, eligible,
        {"regimes_available": True, "regime_index_per_bar": regimes}, trades,
        ShapConfig(sample_size=50), 60, run_explain=fake_explainer(calls),
    )
    index = output["trade_row_index"]
    rows = output["shap"]["trade_rows"]

    assert index == {1: 0, 3: 1}
    assert [rows[i]["trade_id"] for i in index.values()] == [1, 3]
    assert [rows[i]["bar_index"] for i in index.values()] == [10, 40]
    assert len(calls[0]["trade_rows"]) == 2
    assert len(calls[0]["global_rows"]) == 50
    np.testing.assert_allclose(calls[0]["trade_rows"][1], frame.loc[40, FEATURES].to_numpy(dtype=float))
    assert rows[1]["contributions"]["f0"] == pytest.approx(round(frame.loc[40, "f0"] * 0.01, 6))


def test_additivity_failure_from_the_sandbox_is_a_distinct_stage_error():
    frame, regimes = regime_frame([300])

    def failing(model_path, payload, timeout_seconds):
        raise SandboxExecutionError("gap too large", code="shap_additivity_failed", details={"max_gap": 0.2})

    with pytest.raises(ShapStageError) as excinfo:
        compute_shap("model.pkl", frame, FEATURES, list(range(300)), None, [], ShapConfig(), 60, run_explain=failing)
    assert excinfo.value.code == "shap_additivity_failed"
    assert excinfo.value.details["max_gap"] == 0.2


def test_stratified_sample_is_uniform_within_regimes():
    regimes = [0] * 100 + [1] * 100
    sample = stratified_sample(list(range(200)), regimes, 50, 10, seed=0)
    assert len(sample) == 50
    assert sum(1 for p in sample if p < 100) == 25


@requires_docker
@pytest.mark.parametrize("factory", [
    lambda: DecisionTreeClassifier(max_depth=4, random_state=0),
    lambda: Pipeline([("scale", StandardScaler()), ("model", LogisticRegression())]),
    lambda: XGBClassifier(n_estimators=20, max_depth=3, random_state=0),
])
def test_explain_inside_the_sandbox(tmp_path, factory):
    X, labels, _ = synthetic_data()
    model = factory().fit(X, labels)
    path = tmp_path / "model.pkl"
    path.write_bytes(pickle.dumps(model))
    frame = X.copy()
    frame.insert(0, "date", pd.date_range("2015-01-01", periods=len(frame), freq="D").strftime("%Y-%m-%d"))
    trades = [{"id": 1, "signal_bar_index": 5}]

    output = compute_shap(str(path), frame, FEATURES, list(range(len(frame))), None, trades, ShapConfig(sample_size=60), 180)

    shap_result = output["shap"]
    assert shap_result["max_additivity_gap"] < EPSILON
    row = shap_result["trade_rows"][0]
    assert sum(row["contributions"].values()) + row["base_value"] == pytest.approx(model.predict_proba(X.iloc[[5]])[0, 1], abs=EPSILON)


@requires_docker
def test_rsi_only_sanity_inside_the_sandbox():
    result = run_single_feature_sanity_check()
    assert result["rsi_share"] > 0.9
    assert result["max_additivity_gap"] <= EPSILON
