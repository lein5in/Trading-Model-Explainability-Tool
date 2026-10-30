import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
TICKERS = ["SPY", "QQQ", "AAPL"]
START = "2010-01-01"
END_EXCLUSIVE = "2025-01-01"
PRICE_DECIMALS = 6


def build(ticker: str) -> Path:
    import yfinance as yf
    from app.data.ingestion import FALLBACK_DIR, normalize_yfinance_frame
    from app.data.schemas import validate_ohlcv

    raw = yf.download(ticker, start=START, end=END_EXCLUSIVE, interval="1d", progress=False, auto_adjust=True, threads=False, timeout=60)
    if raw is None or raw.empty:
        raise SystemExit(f"No data returned for {ticker}.")
    frame, invalid_count = validate_ohlcv(normalize_yfinance_frame(raw))
    for column in ["open", "high", "low", "close"]:
        frame[column] = frame[column].round(PRICE_DECIMALS)
    frame["volume"] = frame["volume"].round(0)
    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    path = FALLBACK_DIR / f"{ticker}.csv"
    frame.to_csv(path, index=False, lineterminator="\n")
    print(f"{ticker}: {len(frame)} rows, {invalid_count} invalid, {frame['date'].iloc[0]} to {frame['date'].iloc[-1]} -> {path}")
    return path


def main() -> None:
    sys.path.insert(0, str(BACKEND_DIR))
    for symbol in TICKERS:
        build(symbol)


if __name__ == "__main__":
    main()
