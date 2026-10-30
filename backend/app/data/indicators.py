from dataclasses import dataclass
from typing import Callable
import numpy as np
import pandas as pd

RSI_PERIOD = 14
ATR_PERIOD = 14
SMA_FAST = 20
SMA_SLOW = 50
EMA_FAST = 12
EMA_SLOW = 26
MACD_SIGNAL = 9
VOLATILITY_WINDOW = 20
VOLUME_WINDOW = 20


@dataclass(frozen=True)
class Indicator:
    id: str
    label: str
    description: str
    warmup: int
    parameters: dict[str, int]
    compute: Callable[[pd.DataFrame], np.ndarray]


def wilder_average(values: np.ndarray, period: int) -> np.ndarray:
    result = np.full(len(values), np.nan)
    if len(values) <= period:
        return result
    average = float(np.mean(values[1:period + 1]))
    result[period] = average
    for index in range(period + 1, len(values)):
        average = (average * (period - 1) + values[index]) / period
        result[index] = average
    return result


def rsi_14(df: pd.DataFrame) -> np.ndarray:
    close = df["close"].to_numpy(dtype=float)
    deltas = np.zeros(len(close))
    deltas[1:] = np.diff(close)
    average_gain = wilder_average(np.where(deltas > 0, deltas, 0.0), RSI_PERIOD)
    average_loss = wilder_average(np.where(deltas < 0, -deltas, 0.0), RSI_PERIOD)
    result = np.full(len(close), np.nan)
    for index in range(len(close)):
        gain, loss = average_gain[index], average_loss[index]
        if np.isnan(gain) or np.isnan(loss):
            continue
        if loss == 0:
            result[index] = 100.0 if gain > 0 else 50.0
        else:
            result[index] = 100.0 - 100.0 / (1.0 + gain / loss)
    return result


def atr_14_pct(df: pd.DataFrame) -> np.ndarray:
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    true_range = np.zeros(len(close))
    for index in range(1, len(close)):
        previous_close = close[index - 1]
        true_range[index] = max(
            high[index] - low[index],
            abs(high[index] - previous_close),
            abs(low[index] - previous_close),
        )
    return wilder_average(true_range, ATR_PERIOD) / close


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def mask_before(values, first_valid: int) -> np.ndarray:
    result = np.asarray(values, dtype=float).copy()
    result[:first_valid] = np.nan
    return result


def sma_ratio_20_50(df: pd.DataFrame) -> np.ndarray:
    close = df["close"].astype(float)
    return (close.rolling(SMA_FAST).mean() / close.rolling(SMA_SLOW).mean()).to_numpy()


def ema_ratio_12_26(df: pd.DataFrame) -> np.ndarray:
    close = df["close"].astype(float)
    return mask_before(ema(close, EMA_FAST) / ema(close, EMA_SLOW), EMA_SLOW - 1)


def macd_hist(df: pd.DataFrame) -> np.ndarray:
    close = df["close"].astype(float)
    macd = ema(close, EMA_FAST) - ema(close, EMA_SLOW)
    signal = ema(macd, MACD_SIGNAL)
    return mask_before(macd - signal, EMA_SLOW - 1 + MACD_SIGNAL - 1)


def vol_20d(df: pd.DataFrame) -> np.ndarray:
    log_returns = np.log(df["close"].astype(float)).diff()
    return log_returns.rolling(VOLATILITY_WINDOW).std(ddof=1).to_numpy()


def lagged_return(lag: int) -> Callable[[pd.DataFrame], np.ndarray]:
    def compute(df: pd.DataFrame) -> np.ndarray:
        close = df["close"].astype(float)
        return (close / close.shift(lag) - 1.0).to_numpy()
    return compute


def volume_z_20(df: pd.DataFrame) -> np.ndarray:
    volume = df["volume"].astype(float)
    mean = volume.rolling(VOLUME_WINDOW).mean()
    std = volume.rolling(VOLUME_WINDOW).std(ddof=1)
    z = (volume - mean) / std.where(std > 0)
    return z.to_numpy()


CATALOG: dict[str, Indicator] = {
    indicator.id: indicator
    for indicator in [
        Indicator("rsi_14", "RSI 14", "Relative Strength Index over 14 bars, Wilder smoothing.", RSI_PERIOD, {"period": RSI_PERIOD}, rsi_14),
        Indicator("sma_ratio_20_50", "SMA 20 / SMA 50", "Ratio of the 20-bar to the 50-bar simple moving average of the close.", SMA_SLOW - 1, {"fast_window": SMA_FAST, "slow_window": SMA_SLOW}, sma_ratio_20_50),
        Indicator("ema_ratio_12_26", "EMA 12 / EMA 26", "Ratio of the 12-bar to the 26-bar exponential moving average of the close.", EMA_SLOW - 1, {"fast_span": EMA_FAST, "slow_span": EMA_SLOW}, ema_ratio_12_26),
        Indicator("macd_hist", "MACD histogram", "MACD (12, 26) minus its 9-bar signal line.", EMA_SLOW - 1 + MACD_SIGNAL - 1, {"fast_span": EMA_FAST, "slow_span": EMA_SLOW, "signal_span": MACD_SIGNAL}, macd_hist),
        Indicator("atr_14_pct", "ATR 14 / close", "Average True Range over 14 bars (Wilder) divided by the close.", ATR_PERIOD, {"period": ATR_PERIOD}, atr_14_pct),
        Indicator("vol_20d", "Volatility 20d", "Standard deviation of daily log returns over 20 bars.", VOLATILITY_WINDOW, {"window": VOLATILITY_WINDOW}, vol_20d),
        Indicator("ret_lag_1", "Return 1d", "Simple return over the last bar.", 1, {"lag": 1}, lagged_return(1)),
        Indicator("ret_lag_5", "Return 5d", "Simple return over the last 5 bars.", 5, {"lag": 5}, lagged_return(5)),
        Indicator("ret_lag_21", "Return 21d", "Simple return over the last 21 bars.", 21, {"lag": 21}, lagged_return(21)),
        Indicator("volume_z_20", "Volume z-score 20", "Z-score of volume against the last 20 bars, current bar included.", VOLUME_WINDOW - 1, {"window": VOLUME_WINDOW}, volume_z_20),
    ]
}


def catalog_listing() -> list[dict]:
    return [
        {"id": item.id, "label": item.label, "description": item.description, "warmup": item.warmup}
        for item in CATALOG.values()
    ]


def unknown_feature_ids(feature_ids: list[str]) -> list[str]:
    return [feature_id for feature_id in feature_ids if feature_id not in CATALOG]


def max_warmup(feature_ids: list[str]) -> int:
    return max((CATALOG[feature_id].warmup for feature_id in feature_ids), default=0)


def compute_indicators(ohlcv: pd.DataFrame, feature_ids: list[str]) -> pd.DataFrame:
    values = {}
    for feature_id in feature_ids:
        column = np.asarray(CATALOG[feature_id].compute(ohlcv), dtype=float)
        column[~np.isfinite(column)] = np.nan
        values[feature_id] = column
    return pd.DataFrame(values, index=ohlcv.index)
