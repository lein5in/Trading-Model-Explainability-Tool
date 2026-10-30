import math
from datetime import date, timedelta
import numpy as np
import pandas as pd
from app.data.indicators import compute_indicators, max_warmup

CALENDAR_DAYS_PER_TRADING_DAY = 7 / 5
WARMUP_MARGIN_DAYS = 10


class DatasetError(Exception):
    def __init__(self, message: str, code: str = "insufficient_data"):
        super().__init__(message)
        self.code = code


def extended_start(requested_start: str, feature_ids: list[str]) -> str:
    extra_days = math.ceil(max_warmup(feature_ids) * CALENDAR_DAYS_PER_TRADING_DAY) + WARMUP_MARGIN_DAYS
    return (date.fromisoformat(requested_start) - timedelta(days=extra_days)).isoformat()


def drop_leading_warmup(frame: pd.DataFrame, feature_columns: list[str]) -> tuple[pd.DataFrame, int]:
    complete = np.isfinite(frame[feature_columns].to_numpy(dtype=float)).all(axis=1)
    if not complete.any():
        raise DatasetError("No bar has every feature defined in the requested period.")
    first_complete = int(np.argmax(complete))
    return frame.iloc[first_complete:].reset_index(drop=True), first_complete


def restrict_period(frame: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    if start:
        mask &= frame["date"] >= start
    if end:
        mask &= frame["date"] <= end
    return frame.loc[mask].reset_index(drop=True)


def build_catalog_dataset(ohlcv: pd.DataFrame, feature_ids: list[str], requested_start: str, requested_end: str) -> dict:
    features = compute_indicators(ohlcv, feature_ids)
    frame = pd.concat([ohlcv.reset_index(drop=True), features.reset_index(drop=True)], axis=1)
    frame = restrict_period(frame, requested_start, requested_end)
    if frame.empty:
        raise DatasetError("No market data in the requested period.")
    frame, warmup_dropped = drop_leading_warmup(frame, feature_ids)
    return {
        "frame": frame,
        "feature_columns": list(feature_ids),
        "warmup_dropped": warmup_dropped,
        "requested_start": requested_start,
        "effective_start": frame["date"].iloc[0],
        "end": frame["date"].iloc[-1],
    }


def build_csv_dataset(parsed: dict, start: str | None, end: str | None) -> dict:
    frame = restrict_period(parsed["frame"], start, end)
    if frame.empty:
        raise DatasetError("The CSV has no rows in the requested period.")
    frame, warmup_dropped = drop_leading_warmup(frame, parsed["feature_columns"])
    return {
        "frame": frame,
        "feature_columns": list(parsed["feature_columns"]),
        "warmup_dropped": warmup_dropped,
        "requested_start": start or parsed["frame"]["date"].iloc[0],
        "effective_start": frame["date"].iloc[0],
        "end": frame["date"].iloc[-1],
    }
