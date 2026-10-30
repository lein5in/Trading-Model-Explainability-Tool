import pandas as pd
import pandera as pa

OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
PRICE_COLUMNS = ["open", "high", "low", "close"]

OHLCVSchema = pa.DataFrameSchema(
    {
        "date": pa.Column(str, nullable=False),
        "open": pa.Column(float, checks=pa.Check.gt(0), nullable=False),
        "high": pa.Column(float, checks=pa.Check.gt(0), nullable=False),
        "low": pa.Column(float, checks=pa.Check.gt(0), nullable=False),
        "close": pa.Column(float, checks=pa.Check.gt(0), nullable=False),
        "volume": pa.Column(float, checks=pa.Check.ge(0), nullable=False),
    },
    strict=False,
    coerce=False,
)


def format_daily_dates(values) -> pd.Series:
    parsed = pd.to_datetime(pd.Series(values), errors="coerce")
    if getattr(parsed.dt, "tz", None) is not None:
        parsed = parsed.dt.tz_localize(None)
    return parsed.dt.strftime("%Y-%m-%d")


def coerce_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    coerced = df.copy()
    for column in PRICE_COLUMNS + ["volume"]:
        coerced[column] = pd.to_numeric(coerced[column], errors="coerce").astype(float)
    coerced["date"] = coerced["date"].astype(object).where(coerced["date"].notna(), None)
    return coerced


def validate_ohlcv(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    coerced = coerce_ohlcv(df)
    try:
        OHLCVSchema.validate(coerced, lazy=True)
        invalid_mask = pd.Series(False, index=coerced.index)
    except pa.errors.SchemaErrors as exc:
        failing_labels = set(exc.failure_cases["index"].dropna().tolist())
        invalid_mask = coerced.index.to_series().isin(failing_labels)
    invalid_mask = invalid_mask | coerced["date"].isna()
    valid = coerced.loc[~invalid_mask].reset_index(drop=True)
    return valid, int(invalid_mask.sum())
