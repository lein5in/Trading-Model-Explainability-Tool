import io
import json
import re
from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest
from app.data import ingestion
from app.data.csv_input import CsvValidationError, parse_csv
from app.data.dataset import build_catalog_dataset, extended_start
from app.data.schemas import validate_ohlcv
from app.db.repository import InMemoryRepository

ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SMA_WARMUP_DAYS = 79


def yahoo_frame(n: int = 5, start: str = "2024-01-02", tz: str | None = "America/New_York") -> pd.DataFrame:
    index = pd.date_range(start, periods=n, freq="B", tz=tz, name="Date")
    columns = pd.MultiIndex.from_product([["Close", "High", "Low", "Open", "Volume"], ["SPY"]])
    data = [[100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000.0 + i] for i in range(n)]
    return pd.DataFrame(data, index=index, columns=columns)


class CountingDownload:
    def __init__(self, frame=None, error=None):
        self.calls = 0
        self.frame = frame
        self.error = error
        self.kwargs = []

    def __call__(self, *args, **kwargs):
        self.calls += 1
        self.kwargs.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.frame


def test_validation_resets_the_index_after_removing_a_middle_row():
    frame = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        "open": [1.0, 2.0, 3.0, 4.0, 5.0],
        "high": [1.0, 2.0, 3.0, 4.0, 5.0],
        "low": [1.0, 2.0, 3.0, 4.0, 5.0],
        "close": [1.0, 2.0, -3.0, 4.0, 5.0],
        "volume": [1.0, 1.0, 1.0, 1.0, 1.0],
    })
    valid, invalid_count = validate_ohlcv(frame)
    assert invalid_count == 1
    assert list(valid.index) == [0, 1, 2, 3]
    assert valid.iloc[2]["date"] == "2024-01-04"
    assert valid.loc[2, "date"] == valid.iloc[2]["date"]
    assert valid["close"].tolist() == [1.0, 2.0, 4.0, 5.0]


def test_nan_prices_are_counted_as_invalid():
    frame = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "open": [1.0, float("nan")], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0], "volume": [1.0, 1.0],
    })
    valid, invalid_count = validate_ohlcv(frame)
    assert invalid_count == 1
    assert len(valid) == 1


def test_yfinance_frame_dates_are_iso_days():
    normalized = ingestion.normalize_yfinance_frame(yahoo_frame())
    assert normalized["date"].tolist()[:2] == ["2024-01-02", "2024-01-03"]
    assert all(ISO_DAY.match(value) for value in normalized["date"])


def test_cache_hit_avoids_a_second_download(monkeypatch):
    download = CountingDownload(frame=yahoo_frame())
    monkeypatch.setattr(ingestion.yf, "download", download)
    repository = InMemoryRepository()

    first = ingestion.fetch_ohlcv("SPY", "2024-01-01", "2024-01-31", repository)
    second = ingestion.fetch_ohlcv("SPY", "2024-01-01", "2024-01-31", repository)

    assert download.calls == 1
    assert first["cached"] is False and second["cached"] is True
    assert second["data"].equals(first["data"])
    assert download.kwargs[0]["timeout"] == ingestion.YFINANCE_TIMEOUT_SECONDS
    assert download.kwargs[0]["end"] == "2024-02-01"


def test_cache_expires_after_24_hours(monkeypatch):
    download = CountingDownload(frame=yahoo_frame())
    monkeypatch.setattr(ingestion.yf, "download", download)
    repository = InMemoryRepository()

    ingestion.fetch_ohlcv("SPY", "2024-01-01", "2024-01-31", repository)
    later = datetime.now(timezone.utc) + timedelta(hours=25)
    ingestion.fetch_ohlcv("SPY", "2024-01-01", "2024-01-31", repository, now=later)

    assert download.calls == 2


def test_fallback_is_used_after_three_failed_attempts(monkeypatch):
    download = CountingDownload(error=ConnectionError("blocked"))
    sleeps = []
    monkeypatch.setattr(ingestion.yf, "download", download)
    monkeypatch.setattr(ingestion, "sleep", sleeps.append)
    repository = InMemoryRepository()

    result = ingestion.fetch_ohlcv("SPY", "2015-01-01", "2015-12-31", repository)

    assert download.calls == 3
    assert sleeps == [1.0, 2.0]
    assert result["data_source"] == "bundled"
    assert result["data"]["date"].iloc[0] == "2015-01-02"
    assert result["data"]["date"].iloc[-1] == "2015-12-31"
    assert repository.get_cache(ingestion.cache_key("SPY", "2015-01-01", "2015-12-31")) is None


def test_unknown_ticker_without_fallback_raises_a_502_error_naming_it(monkeypatch):
    monkeypatch.setattr(ingestion.yf, "download", CountingDownload(frame=pd.DataFrame()))
    monkeypatch.setattr(ingestion, "sleep", lambda seconds: None)

    with pytest.raises(ingestion.DataUnavailableError) as excinfo:
        ingestion.fetch_ohlcv("ZZZZ", "2015-01-01", "2015-12-31")

    assert excinfo.value.status_code == 502
    assert "ZZZZ" in str(excinfo.value)


def test_bundled_datasets_cover_2010_to_2024():
    assert ingestion.bundled_tickers() == ["AAPL", "QQQ", "SPY"]
    for ticker in ingestion.bundled_tickers():
        frame = pd.read_csv(ingestion.FALLBACK_DIR / f"{ticker}.csv", dtype={"date": str})
        assert frame["date"].iloc[0] == "2010-01-04"
        assert frame["date"].iloc[-1] == "2024-12-31"
        assert list(frame.columns) == ["date", "open", "high", "low", "close", "volume"]


def bundled_spy() -> pd.DataFrame:
    return pd.read_csv(ingestion.FALLBACK_DIR / "SPY.csv", dtype={"date": str})


def test_extended_start_covers_the_warmup():
    assert extended_start("2015-06-01", ["sma_ratio_20_50"]) == (
        datetime(2015, 6, 1) - timedelta(days=SMA_WARMUP_DAYS)
    ).date().isoformat()


def test_warmup_rows_are_dropped_and_counted_when_history_is_missing():
    ohlcv = bundled_spy()
    dataset = build_catalog_dataset(ohlcv, ["sma_ratio_20_50", "rsi_14"], "2010-01-01", "2010-12-31")
    assert dataset["warmup_dropped"] == 49
    assert dataset["effective_start"] == ohlcv["date"].iloc[49]
    assert dataset["requested_start"] == "2010-01-01"


def test_no_warmup_is_lost_when_extra_history_is_fetched():
    ohlcv = bundled_spy()
    fetch_start = extended_start("2015-06-01", ["sma_ratio_20_50"])
    window = ohlcv[ohlcv["date"] >= fetch_start].reset_index(drop=True)
    dataset = build_catalog_dataset(window, ["sma_ratio_20_50"], "2015-06-01", "2015-12-31")
    assert dataset["warmup_dropped"] == 0
    assert dataset["effective_start"] == "2015-06-01"
    assert list(dataset["frame"].index) == list(range(len(dataset["frame"])))


def csv_bytes(lines: list[str]) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


VALID_CSV = [
    "date,open,high,low,close,volume,signal_a,signal_b",
    "2024-01-02,10,11,9,10.5,100,0.1,1",
    "2024-01-03,10.5,11,10,10.8,120,0.2,0",
    "2024-01-04,10.8,11.2,10.1,11,90,0.3,1",
]


def test_csv_parses_features_and_counts_invalid_rows():
    lines = VALID_CSV + ["2024-01-05,11,11.5,10.5,-1,80,0.4,0"]
    parsed = parse_csv(csv_bytes(lines), max_rows=100, max_features=30)
    assert parsed["feature_columns"] == ["signal_a", "signal_b"]
    assert parsed["invalid_count"] == 1
    assert parsed["frame"]["date"].tolist() == ["2024-01-02", "2024-01-03", "2024-01-04"]
    assert parsed["frame"]["signal_a"].tolist() == [0.1, 0.2, 0.3]


@pytest.mark.parametrize(
    "lines,code",
    [
        (["date,open,high,low,close,signal_a", "2024-01-02,1,1,1,1,0.1"], "csv_missing_columns"),
        (["date,open,high,low,close,volume", "2024-01-02,1,1,1,1,1"], "csv_no_features"),
        (VALID_CSV[:1] + ["02/01/2024,1,1,1,1,1,0.1,1"], "csv_invalid_dates"),
        (VALID_CSV[:2] + [VALID_CSV[1]], "csv_duplicate_dates"),
        (VALID_CSV[:1] + [VALID_CSV[2], VALID_CSV[1]], "csv_dates_not_increasing"),
        (VALID_CSV[:1] + ["2024-01-02,10,11,9,10.5,100,abc,1"], "csv_non_numeric"),
        (VALID_CSV, "csv_too_many_rows"),
    ],
)
def test_csv_validation_errors(lines, code):
    with pytest.raises(CsvValidationError) as excinfo:
        parse_csv(csv_bytes(lines), max_rows=2, max_features=30)
    assert excinfo.value.code == code


def test_csv_feature_cap():
    header = "date,open,high,low,close,volume," + ",".join(f"f{i}" for i in range(4))
    with pytest.raises(CsvValidationError) as excinfo:
        parse_csv(csv_bytes([header, "2024-01-02,1,1,1,1,1,1,1,1,1"]), max_rows=10, max_features=3)
    assert excinfo.value.code == "too_many_features"


def test_indicators_endpoint_lists_the_catalog(make_api):
    client, _ = make_api()
    body = client.get("/indicators").json()
    assert [item["id"] for item in body["indicators"]] == [
        "rsi_14", "sma_ratio_20_50", "ema_ratio_12_26", "macd_hist", "atr_14_pct",
        "vol_20d", "ret_lag_1", "ret_lag_5", "ret_lag_21", "volume_z_20",
    ]
    assert all({"id", "label", "description", "warmup"} <= set(item) for item in body["indicators"])


def test_unknown_feature_id_is_rejected_at_submission(make_api):
    client, _ = make_api()
    response = client.post(
        "/analysis/run",
        data={"ticker": "SPY", "start_date": "2020-01-01", "end_date": "2021-01-01", "feature_ids": json.dumps(["rsi_14", "nope"])},
        files={"model_file": ("m.pkl", io.BytesIO(b"x"), "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "unknown_feature"


def test_invalid_csv_is_rejected_at_submission(make_api):
    client, _ = make_api()
    response = client.post(
        "/analysis/run",
        data={},
        files={
            "model_file": ("m.pkl", io.BytesIO(b"x"), "application/octet-stream"),
            "csv_file": ("d.csv", io.BytesIO(csv_bytes(VALID_CSV[:1] + [VALID_CSV[2], VALID_CSV[1]])), "text/csv"),
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "csv_dates_not_increasing"
