import yfinance as yf
import pandas as pd
from app.data.schemas import validate_ohlcv


def fetch_ohlcv(ticker: str, start: str, end: str, interval: str = "1d") -> dict:
    raw = yf.download(ticker, start=start, end=end, interval=interval, progress=False, auto_adjust=True)

    if raw.empty:
        return {
            "data": pd.DataFrame(),
            "invalid_rows": pd.DataFrame(),
            "row_count": 0,
            "invalid_count": 0,
        }

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    raw = raw.reset_index()
    raw = raw.rename(columns={
        "Date": "timestamp",
        "Datetime": "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    if raw["timestamp"].dt.tz is None:
        raw["timestamp"] = raw["timestamp"].dt.tz_localize("UTC")
    else:
        raw["timestamp"] = raw["timestamp"].dt.tz_convert("UTC")

    valid_rows, invalid_rows = validate_ohlcv(raw)

    return {
        "data": valid_rows,
        "invalid_rows": invalid_rows,
        "row_count": len(valid_rows),
        "invalid_count": len(invalid_rows),
    }