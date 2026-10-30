import math
import numpy as np
import pandas as pd
import pytest
from app.data.indicators import CATALOG, compute_indicators

EXPECTED_IDS = [
    "rsi_14", "sma_ratio_20_50", "ema_ratio_12_26", "macd_hist", "atr_14_pct",
    "vol_20d", "ret_lag_1", "ret_lag_5", "ret_lag_21", "volume_z_20",
]
SERIES_LENGTH = 90
TRUNCATION_BAR = 63
VOLUME_ONE_TO_TWENTY_Z = 9.5 / math.sqrt(35.0)


def synthetic_ohlcv(n: int = SERIES_LENGTH) -> pd.DataFrame:
    close = [100.0 + 10.0 * math.sin(i / 5.0) + 0.3 * i for i in range(n)]
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
        "open": [c - 0.2 for c in close],
        "high": [c + 1.0 + (i % 3) * 0.5 for i, c in enumerate(close)],
        "low": [c - 1.0 - (i % 2) * 0.4 for i, c in enumerate(close)],
        "close": close,
        "volume": [1000.0 + (i * 37) % 200 for i in range(n)],
    })


def frame_from_close(close: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=len(close), freq="D").strftime("%Y-%m-%d"),
        "open": close, "high": close, "low": close, "close": close, "volume": [1.0] * len(close),
    })


def ref_ema(values: list[float], span: int) -> list[float]:
    alpha = 2.0 / (span + 1.0)
    out = [values[0]]
    for value in values[1:]:
        out.append(alpha * value + (1.0 - alpha) * out[-1])
    return out


def ref_wilder(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    average = sum(values[1:period + 1]) / period
    out[period] = average
    for index in range(period + 1, len(values)):
        average = (average * (period - 1) + values[index]) / period
        out[index] = average
    return out


def ref_sample_std(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))


def reference_values(df: pd.DataFrame) -> dict[str, list[float | None]]:
    close = df["close"].tolist()
    high = df["high"].tolist()
    low = df["low"].tolist()
    volume = df["volume"].tolist()
    n = len(close)
    deltas = [0.0] + [close[i] - close[i - 1] for i in range(1, n)]
    gains = ref_wilder([max(d, 0.0) for d in deltas], 14)
    losses = ref_wilder([max(-d, 0.0) for d in deltas], 14)
    true_range = [0.0] + [
        max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])) for i in range(1, n)
    ]
    atr = ref_wilder(true_range, 14)
    ema12, ema26 = ref_ema(close, 12), ref_ema(close, 26)
    macd = [a - b for a, b in zip(ema12, ema26)]
    signal = ref_ema(macd, 9)
    log_returns = [None] + [math.log(close[i] / close[i - 1]) for i in range(1, n)]

    def rsi(i):
        if gains[i] is None:
            return None
        if losses[i] == 0:
            return 100.0 if gains[i] > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + gains[i] / losses[i])

    def window_z(i):
        if i < 19:
            return None
        window = volume[i - 19:i + 1]
        std = ref_sample_std(window)
        return None if std == 0 else (volume[i] - sum(window) / 20.0) / std

    return {
        "rsi_14": [rsi(i) for i in range(n)],
        "sma_ratio_20_50": [None if i < 49 else (sum(close[i - 19:i + 1]) / 20) / (sum(close[i - 49:i + 1]) / 50) for i in range(n)],
        "ema_ratio_12_26": [None if i < 25 else ema12[i] / ema26[i] for i in range(n)],
        "macd_hist": [None if i < 33 else macd[i] - signal[i] for i in range(n)],
        "atr_14_pct": [None if atr[i] is None else atr[i] / close[i] for i in range(n)],
        "vol_20d": [None if i < 20 else ref_sample_std(log_returns[i - 19:i + 1]) for i in range(n)],
        "ret_lag_1": [None if i < 1 else close[i] / close[i - 1] - 1 for i in range(n)],
        "ret_lag_5": [None if i < 5 else close[i] / close[i - 5] - 1 for i in range(n)],
        "ret_lag_21": [None if i < 21 else close[i] / close[i - 21] - 1 for i in range(n)],
        "volume_z_20": [window_z(i) for i in range(n)],
    }


def test_catalog_has_exactly_the_ten_ids():
    assert list(CATALOG) == EXPECTED_IDS


@pytest.mark.parametrize("feature_id", EXPECTED_IDS)
def test_indicator_matches_pure_python_reference(feature_id):
    df = synthetic_ohlcv()
    computed = compute_indicators(df, [feature_id])[feature_id].tolist()
    expected = reference_values(df)[feature_id]
    for index, (got, want) in enumerate(zip(computed, expected)):
        if want is None:
            assert math.isnan(got), (feature_id, index)
        else:
            assert got == pytest.approx(want, rel=1e-10, abs=1e-12), (feature_id, index)


@pytest.mark.parametrize("feature_id", EXPECTED_IDS)
def test_warmup_equals_first_defined_bar(feature_id):
    values = compute_indicators(synthetic_ohlcv(), [feature_id])[feature_id].to_numpy()
    first_defined = int(np.argmax(np.isfinite(values)))
    assert first_defined == CATALOG[feature_id].warmup


def test_hand_values_for_lagged_return_and_rsi():
    assert compute_indicators(frame_from_close([100.0, 110.0, 99.0]), ["ret_lag_1"])["ret_lag_1"].tolist()[1:] == pytest.approx([0.1, -0.1])
    rising = compute_indicators(frame_from_close([float(v) for v in range(1, 17)]), ["rsi_14"])["rsi_14"].tolist()
    assert rising[14:] == [100.0, 100.0]
    flat = compute_indicators(frame_from_close([5.0] * 16), ["rsi_14"])["rsi_14"].tolist()
    assert flat[14:] == [50.0, 50.0]


def test_hand_value_for_volume_z_score():
    df = frame_from_close([10.0] * 20)
    df["volume"] = [float(v) for v in range(1, 21)]
    z = compute_indicators(df, ["volume_z_20"])["volume_z_20"].tolist()
    assert z[19] == pytest.approx(VOLUME_ONE_TO_TWENTY_Z)


def test_indicators_are_point_in_time():
    full = synthetic_ohlcv()
    truncated = full.iloc[:TRUNCATION_BAR].copy()
    full_values = compute_indicators(full, EXPECTED_IDS).iloc[:TRUNCATION_BAR]
    truncated_values = compute_indicators(truncated, EXPECTED_IDS)
    np.testing.assert_array_equal(full_values.to_numpy(), truncated_values.to_numpy())


def test_future_change_does_not_alter_past_values():
    base = synthetic_ohlcv()
    altered = base.copy()
    altered.loc[TRUNCATION_BAR:, ["open", "high", "low", "close"]] *= 1.5
    altered.loc[TRUNCATION_BAR:, "volume"] *= 3
    a = compute_indicators(base, EXPECTED_IDS).iloc[:TRUNCATION_BAR].to_numpy()
    b = compute_indicators(altered, EXPECTED_IDS).iloc[:TRUNCATION_BAR].to_numpy()
    np.testing.assert_array_equal(a, b)
