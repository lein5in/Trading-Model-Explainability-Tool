import pickle
import pandas as pd
import numpy as np
import pytest
from sklearn.tree import DecisionTreeClassifier
from app.models.wrapper import ModelMetadata, SignalType
from app.models.validation import register_model
from app.backtest.engine import run_backtest, is_signal_nan
from app.sandbox.predict_entrypoint import validate_signal_contract, SignalContractViolation
from app.tests.conftest import requires_docker


def build_ohlcv(n: int) -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    close = np.linspace(100, 100 + n, n)
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": np.full(n, 1000.0),
    })


def test_missing_feature_columns_are_detected_before_predictions():
    ohlcv = build_ohlcv(5)
    requested_columns = ["open", "close", "rsi_14"]
    missing = [c for c in requested_columns if c not in ohlcv.columns]

    assert missing == ["rsi_14"]


def test_nan_signals_are_ignored_and_counted_not_dropped_silently():
    ohlcv = build_ohlcv(5)
    features = ohlcv[["open", "close"]]
    signals = [1, float("nan"), 1, 0, -1]

    result = run_backtest(
        ohlcv=ohlcv,
        features=features,
        signals=signals,
        signal_type="discrete",
    )

    assert result["ignored_bar_count"] == 1


def test_nan_signal_freezes_open_position_instead_of_closing_it():
    ohlcv = build_ohlcv(4)
    features = ohlcv[["open", "close"]]
    signals = [1, float("nan"), 1, 0]

    result = run_backtest(
        ohlcv=ohlcv,
        features=features,
        signals=signals,
        signal_type="discrete",
    )

    assert result["ignored_bar_count"] == 1
    assert result["trade_count"] == 1


def test_is_signal_nan_discrete():
    assert is_signal_nan(float("nan"), "discrete") is True
    assert is_signal_nan(1, "discrete") is False
    assert is_signal_nan(0, "discrete") is False


def test_is_signal_nan_continuous():
    assert is_signal_nan(float("nan"), "continuous") is True
    assert is_signal_nan(0.35, "continuous") is False


def test_discrete_contract_rejects_continuous_output():
    with pytest.raises(SignalContractViolation):
        validate_signal_contract([1.0, 0.35, -1.0], "discrete")


def test_discrete_contract_accepts_valid_values():
    validate_signal_contract([1.0, 0.0, -1.0, float("nan")], "discrete")


def test_continuous_contract_rejects_out_of_range_output():
    with pytest.raises(SignalContractViolation):
        validate_signal_contract([0.5, 1.4, -0.2], "continuous")


def test_continuous_contract_accepts_valid_values():
    validate_signal_contract([0.5, 1.0, -1.0, 0.0, float("nan")], "continuous")


@requires_docker
def test_sandbox_rejects_mismatched_signal_type_end_to_end():
    from app.sandbox.runner import run_predict_in_sandbox

    X_train = pd.DataFrame({
        "open": [100.0, 100.0, 50.0, 80.0],
        "close": [105.0, 95.0, 50.0, 85.0],
    })
    y_train_continuous = [0.9, -0.9, -0.1, 0.5]

    from sklearn.tree import DecisionTreeRegressor
    model = DecisionTreeRegressor(max_depth=2, random_state=0)
    model.fit(X_train, y_train_continuous)
    model_bytes = pickle.dumps(model)

    metadata = ModelMetadata(
        name="test_mismatched_contract_model",
        signal_type=SignalType.DISCRETE,
        expected_columns=["open", "close"],
    )
    registered = register_model(metadata, model_bytes, "test_mismatched_contract_model.pkl")

    records = X_train.to_dict(orient="records")

    with pytest.raises(Exception):
        run_predict_in_sandbox(registered.storage_path, records, "discrete")