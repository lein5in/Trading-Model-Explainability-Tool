import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from fastapi import UploadFile
from app.api.errors import ApiError
from app.config import Settings
from app.data.csv_input import CsvValidationError, parse_csv
from app.data.indicators import unknown_feature_ids
from app.demo_models.registry import get_demo_model

TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,14}$")
MODEL_EXTENSIONS = (".pkl", ".pickle", ".joblib")
MAX_COST_BPS = 100.0


@dataclass
class Submission:
    params: dict
    model_source: str
    demo_entry: dict | None
    model_bytes: bytes | None
    model_filename: str | None
    csv_bytes: bytes | None


def parse_iso_date(value: str | None, field_name: str) -> date:
    if not value:
        raise ApiError(400, "invalid_date", f"{field_name} is required (YYYY-MM-DD).")
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise ApiError(400, "invalid_date", f"{field_name} must be a date in YYYY-MM-DD format.")


def add_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def check_date_range(start: date, end: date, max_years: int) -> None:
    if start >= end:
        raise ApiError(400, "invalid_date_range", "start_date must be before end_date.")
    if end > add_years(start, max_years):
        raise ApiError(
            400,
            "date_range_too_long",
            f"The date range must not exceed {max_years} years.",
            {"max_years": max_years},
        )


def parse_ticker(value: str | None) -> str:
    ticker = (value or "").strip().upper()
    if not TICKER_PATTERN.match(ticker):
        raise ApiError(400, "invalid_ticker", "ticker must be 1 to 15 characters: letters, digits, '.', '-', '^' or '='.")
    return ticker


def parse_feature_ids(raw: str | None, max_features: int) -> list[str]:
    if not raw:
        raise ApiError(400, "missing_features", "feature_ids is required when no csv_file is provided.")
    try:
        feature_ids = json.loads(raw)
    except ValueError:
        raise ApiError(400, "invalid_features", "feature_ids must be a JSON list of strings.")
    if not isinstance(feature_ids, list) or not all(isinstance(item, str) for item in feature_ids):
        raise ApiError(400, "invalid_features", "feature_ids must be a JSON list of strings.")
    if not feature_ids:
        raise ApiError(400, "missing_features", "feature_ids must contain at least one feature.")
    if len(set(feature_ids)) != len(feature_ids):
        raise ApiError(400, "invalid_features", "feature_ids contains duplicates.")
    check_feature_count(len(feature_ids), max_features)
    return feature_ids


def check_feature_count(count: int, max_features: int) -> None:
    if count > max_features:
        raise ApiError(
            400,
            "too_many_features",
            f"At most {max_features} features are allowed.",
            {"max_features": max_features},
        )


def read_capped(upload: UploadFile, max_bytes: int, code: str, label: str) -> bytes:
    content = upload.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ApiError(413, code, f"{label} exceeds the maximum size of {max_bytes} bytes.", {"max_bytes": max_bytes})
    if not content:
        raise ApiError(400, "empty_file", f"{label} is empty.")
    return content


def check_cost(value: float, field_name: str) -> float:
    if not (0.0 <= value <= MAX_COST_BPS):
        raise ApiError(400, "invalid_cost", f"{field_name} must be between 0 and {MAX_COST_BPS:g} basis points.")
    return float(value)


def inspect_csv(csv_bytes: bytes, settings: Settings) -> list[str]:
    try:
        parsed = parse_csv(csv_bytes, settings.max_csv_rows, settings.max_features)
    except CsvValidationError as exc:
        status = 413 if exc.code == "csv_too_many_rows" else 400
        raise ApiError(status, exc.code, str(exc), exc.details)
    return parsed["feature_columns"]


def check_catalog_features(feature_ids: list[str]) -> list[str]:
    unknown = unknown_feature_ids(feature_ids)
    if unknown:
        raise ApiError(400, "unknown_feature", f"Unknown feature ids: {unknown}.", {"unknown": unknown})
    return feature_ids


def utc_day_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def enforce_daily_cap(repository, cap: int) -> None:
    if repository.count_analyses_since(utc_day_start()) >= cap:
        retry_after = int((utc_day_start() + timedelta(days=1) - datetime.now(timezone.utc)).total_seconds()) + 1
        raise ApiError(
            429,
            "daily_cap_reached",
            "The daily number of analyses has been reached. Try again tomorrow.",
            {"daily_cap": cap},
            {"Retry-After": str(retry_after)},
        )


def enforce_rate_limit(rate_limiter, key: str) -> None:
    if not rate_limiter.hit(key):
        retry_after = rate_limiter.retry_after_seconds(key)
        raise ApiError(
            429,
            "rate_limited",
            "Too many analysis requests from this address. Try again later.",
            {"retry_after_seconds": retry_after},
            {"Retry-After": str(retry_after)},
        )


def validate_submission(
    settings: Settings,
    model_file: UploadFile | None,
    demo_model_id: str | None,
    ticker: str | None,
    start_date: str | None,
    end_date: str | None,
    feature_ids: str | None,
    csv_file: UploadFile | None,
    fee_bps: float,
    slippage_bps: float,
) -> Submission:
    demo_id = (demo_model_id or "").strip() or None
    has_upload = demo_id is None and model_file is not None and bool(model_file.filename)
    if not has_upload and not demo_id:
        raise ApiError(400, "missing_model", "Provide model_file or demo_model_id.")

    demo_entry = None
    model_bytes = None
    model_filename = None
    if demo_id:
        demo_entry = get_demo_model(demo_id)
        if demo_entry is None:
            raise ApiError(404, "unknown_demo_model", f"Unknown demo model '{demo_id}'.")
    else:
        if not settings.allow_upload:
            raise ApiError(403, "upload_disabled", "Model uploads are disabled. Choose a demo model.")
        model_filename = os.path.basename(model_file.filename)
        extension = os.path.splitext(model_filename)[1].lower()
        if extension not in MODEL_EXTENSIONS:
            raise ApiError(400, "unsupported_model_file", f"model_file must be one of {list(MODEL_EXTENSIONS)}.")
        model_bytes = read_capped(model_file, settings.max_model_file_bytes, "model_file_too_large", "model_file")

    has_csv = demo_entry is None and csv_file is not None and bool(csv_file.filename)
    params = {
        "fee_bps": check_cost(fee_bps, "fee_bps"),
        "slippage_bps": check_cost(slippage_bps, "slippage_bps"),
    }
    csv_bytes = None
    if has_csv:
        csv_bytes = read_capped(csv_file, settings.max_csv_bytes, "csv_too_large", "csv_file")
        params["data_source_kind"] = "csv"
        params["feature_ids"] = inspect_csv(csv_bytes, settings)
        params["ticker"] = parse_ticker(ticker) if ticker else None
        if start_date or end_date:
            start = parse_iso_date(start_date, "start_date")
            end = parse_iso_date(end_date, "end_date")
            check_date_range(start, end, settings.max_date_range_years)
            params["start_date"], params["end_date"] = start.isoformat(), end.isoformat()
        else:
            params["start_date"], params["end_date"] = None, None
    else:
        start = parse_iso_date(start_date, "start_date")
        end = parse_iso_date(end_date, "end_date")
        check_date_range(start, end, settings.max_date_range_years)
        params["data_source_kind"] = "ticker"
        params["ticker"] = parse_ticker(ticker)
        params["start_date"], params["end_date"] = start.isoformat(), end.isoformat()
        if demo_entry is not None:
            params["feature_ids"] = list(demo_entry["feature_columns"])
        else:
            params["feature_ids"] = check_catalog_features(parse_feature_ids(feature_ids, settings.max_features))

    return Submission(
        params=params,
        model_source="demo" if demo_entry is not None else "upload",
        demo_entry=demo_entry,
        model_bytes=model_bytes,
        model_filename=model_filename,
        csv_bytes=csv_bytes,
    )
