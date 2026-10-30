import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import yfinance as yf
from app.data.schemas import OHLCV_COLUMNS, format_daily_dates, validate_ohlcv

YFINANCE_TIMEOUT_SECONDS = 20
YFINANCE_ATTEMPTS = 3
YFINANCE_BACKOFF_SECONDS = 1.0
CACHE_TTL = timedelta(hours=24)
FALLBACK_DIR = Path(__file__).resolve().parent / "fallback"
DATA_SOURCE_YFINANCE = "yfinance"
DATA_SOURCE_BUNDLED = "bundled"

sleep = time.sleep


class DataUnavailableError(Exception):
    def __init__(self, ticker: str, message: str | None = None):
        super().__init__(message or f"Market data for '{ticker}' could not be fetched.")
        self.ticker = ticker
        self.code = "data_unavailable"
        self.status_code = 502


def cache_key(ticker: str, start: str, end: str) -> str:
    return f"{ticker}|{start}|{end}"


def normalize_yfinance_frame(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.reset_index()
    frame = frame.rename(columns={
        "Date": "date",
        "Datetime": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })
    frame["date"] = format_daily_dates(frame["date"])
    return frame[OHLCV_COLUMNS]


def download_with_retries(ticker: str, start: str, end: str) -> pd.DataFrame:
    end_exclusive = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
    last_error: Exception | None = None
    for attempt in range(YFINANCE_ATTEMPTS):
        try:
            raw = yf.download(
                ticker,
                start=start,
                end=end_exclusive,
                interval="1d",
                progress=False,
                auto_adjust=True,
                threads=False,
                timeout=YFINANCE_TIMEOUT_SECONDS,
            )
            if raw is None or raw.empty:
                raise ValueError("yfinance returned no rows.")
            return normalize_yfinance_frame(raw)
        except Exception as exc:
            last_error = exc
            if attempt < YFINANCE_ATTEMPTS - 1:
                sleep(YFINANCE_BACKOFF_SECONDS * (2 ** attempt))
    raise DataUnavailableError(ticker, f"Market data for '{ticker}' could not be fetched: {last_error}")


def load_fallback(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    path = FALLBACK_DIR / f"{ticker.upper()}.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path, dtype={"date": str})
    frame = frame[(frame["date"] >= start) & (frame["date"] <= end)].reset_index(drop=True)
    return frame[OHLCV_COLUMNS] if not frame.empty else None


def bundled_tickers() -> list[str]:
    return sorted(path.stem for path in FALLBACK_DIR.glob("*.csv"))


def frame_to_rows(frame: pd.DataFrame) -> list[list]:
    return [
        [row.date, float(row.open), float(row.high), float(row.low), float(row.close), float(row.volume)]
        for row in frame.itertuples(index=False)
    ]


def rows_to_frame(rows: list[list]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=OHLCV_COLUMNS)


def read_cache(repository, key: str, now: datetime) -> dict | None:
    if repository is None:
        return None
    entry = repository.get_cache(key)
    if not entry or not entry.get("payload"):
        return None
    fetched_at = datetime.fromisoformat(str(entry["fetched_at"]).replace("Z", "+00:00"))
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    if now - fetched_at > CACHE_TTL:
        return None
    return entry["payload"]


def fetch_ohlcv(ticker: str, start: str, end: str, repository=None, now: datetime | None = None) -> dict:
    current_time = now or datetime.now(timezone.utc)
    key = cache_key(ticker, start, end)
    cached = read_cache(repository, key, current_time)
    if cached is not None:
        return {
            "data": rows_to_frame(cached["rows"]),
            "invalid_count": int(cached["invalid_count"]),
            "data_source": DATA_SOURCE_YFINANCE,
            "cached": True,
        }

    try:
        raw = download_with_retries(ticker, start, end)
        source = DATA_SOURCE_YFINANCE
    except DataUnavailableError as download_error:
        raw = load_fallback(ticker, start, end)
        if raw is None:
            raise download_error
        source = DATA_SOURCE_BUNDLED

    valid, invalid_count = validate_ohlcv(raw)
    if valid.empty:
        raise DataUnavailableError(ticker, f"No valid market data for '{ticker}' between {start} and {end}.")

    if source == DATA_SOURCE_YFINANCE and repository is not None:
        repository.set_cache(key, {"rows": frame_to_rows(valid), "invalid_count": invalid_count})

    return {"data": valid, "invalid_count": invalid_count, "data_source": source, "cached": False}
