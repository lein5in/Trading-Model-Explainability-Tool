import io
import pandas as pd
from app.data.schemas import OHLCV_COLUMNS, validate_ohlcv

MAX_REPORTED_ROWS = 5


class CsvValidationError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def first_rows(mask: pd.Series) -> list[int]:
    return [int(position) + 2 for position in mask[mask].index[:MAX_REPORTED_ROWS]]


def parse_csv(content: bytes, max_rows: int, max_features: int) -> dict:
    try:
        text = content.decode("utf-8-sig")
        raw = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, skipinitialspace=True)
    except (UnicodeDecodeError, ValueError, pd.errors.ParserError) as exc:
        raise CsvValidationError("csv_unreadable", f"csv_file could not be parsed: {exc}")

    raw.columns = [str(column).strip().lower() for column in raw.columns]
    if len(set(raw.columns)) != len(raw.columns):
        raise CsvValidationError("csv_duplicate_columns", "csv_file has duplicate column names.")
    missing = [column for column in OHLCV_COLUMNS if column not in raw.columns]
    if missing:
        raise CsvValidationError("csv_missing_columns", f"csv_file is missing required columns: {missing}.", {"missing": missing})
    feature_columns = [column for column in raw.columns if column not in OHLCV_COLUMNS]
    if not feature_columns:
        raise CsvValidationError("csv_no_features", "csv_file must contain at least one feature column.")
    if len(feature_columns) > max_features:
        raise CsvValidationError("too_many_features", f"At most {max_features} features are allowed.", {"max_features": max_features})
    if len(raw) == 0:
        raise CsvValidationError("csv_empty", "csv_file has no data rows.")
    if len(raw) > max_rows:
        raise CsvValidationError("csv_too_many_rows", f"csv_file has more than {max_rows} rows.", {"max_rows": max_rows})

    raw = raw.apply(lambda column: column.str.strip())
    parsed_dates = pd.to_datetime(raw["date"], format="%Y-%m-%d", errors="coerce")
    bad_dates = parsed_dates.isna()
    if bad_dates.any():
        raise CsvValidationError("csv_invalid_dates", "Every date must be in YYYY-MM-DD format.", {"rows": first_rows(bad_dates)})
    duplicated = parsed_dates.duplicated(keep=False)
    if duplicated.any():
        raise CsvValidationError("csv_duplicate_dates", "Dates must be unique.", {"rows": first_rows(duplicated)})
    not_increasing = parsed_dates.diff().dt.total_seconds().fillna(1) <= 0
    if not_increasing.any():
        raise CsvValidationError("csv_dates_not_increasing", "Dates must be strictly increasing.", {"rows": first_rows(not_increasing)})

    numeric = pd.DataFrame(index=raw.index)
    for column in [c for c in raw.columns if c != "date"]:
        values = pd.to_numeric(raw[column].replace("", None), errors="coerce")
        non_numeric = values.isna() & (raw[column] != "")
        if non_numeric.any():
            raise CsvValidationError(
                "csv_non_numeric",
                f"Column '{column}' contains non-numeric values.",
                {"column": column, "rows": first_rows(non_numeric)},
            )
        numeric[column] = values.astype(float)

    frame = pd.concat([parsed_dates.dt.strftime("%Y-%m-%d").rename("date"), numeric], axis=1)
    ohlcv, invalid_count = validate_ohlcv(frame[OHLCV_COLUMNS])
    valid_dates = set(ohlcv["date"])
    features = frame.loc[frame["date"].isin(valid_dates), ["date"] + feature_columns].reset_index(drop=True)
    merged = ohlcv.merge(features, on="date", how="left")
    if merged.empty:
        raise CsvValidationError("csv_no_valid_rows", "csv_file has no valid OHLCV row.")
    return {"frame": merged, "feature_columns": feature_columns, "invalid_count": invalid_count}
