import numpy as np
import pandas as pd
from app.regime.hmm_detector import detect_regimes


def build_two_regime_ohlcv(n: int = 300) -> pd.DataFrame:
    np.random.seed(7)
    timestamps = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")

    prices = [100.0]
    for i in range(1, n):
        if i < n // 2:
            drift = 0.8
            noise_std = 0.2
        else:
            drift = -0.8
            noise_std = 0.2
        shock = np.random.normal(drift, noise_std)
        prices.append(max(prices[-1] + shock, 1.0))

    close = np.array(prices)
    open_ = close + np.random.normal(0, 0.05, n)
    high = np.maximum(open_, close) + np.abs(np.random.normal(0, 0.1, n))
    low = np.minimum(open_, close) - np.abs(np.random.normal(0, 0.1, n))
    volume = np.random.uniform(900, 1300, n)

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def test_regime_detection_produces_more_than_one_distinct_regime():
    ohlcv = build_two_regime_ohlcv()
    result = detect_regimes(ohlcv)

    distinct_regimes = set(r for r in result["regime_per_bar"] if r is not None)

    assert len(distinct_regimes) > 1, (
        "Only one distinct regime was detected across a clearly two-phase synthetic "
        "series. This is the exact symptom of using predict() (Viterbi/smoothed) "
        "instead of predict_proba() (filtered) for regime labeling."
    )


def test_time_in_regime_percentages_sum_to_approximately_one():
    ohlcv = build_two_regime_ohlcv()
    result = detect_regimes(ohlcv)

    total_pct = sum(result["time_in_regime_pct"].values())

    assert abs(total_pct - 1.0) < 1e-6


def test_bullish_phase_has_higher_bullish_time_share_than_bearish_phase():
    ohlcv = build_two_regime_ohlcv()
    result = detect_regimes(ohlcv)

    n = len(ohlcv)
    first_half_regimes = [r for r in result["regime_per_bar"][: n // 2] if r is not None]
    second_half_regimes = [r for r in result["regime_per_bar"][n // 2:] if r is not None]

    first_half_bullish_share = first_half_regimes.count("bullish") / len(first_half_regimes)
    second_half_bullish_share = second_half_regimes.count("bullish") / len(second_half_regimes)

    assert first_half_bullish_share > second_half_bullish_share