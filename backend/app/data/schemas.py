import pandera as pa
import pandas as pd

OHLCVSchema = pa.DataFrameSchema(
    {
        "timestamp": pa.Column("datetime64[ns, UTC]", coerce=True),
        "open": pa.Column(float, checks=pa.Check.gt(0)),
        "high": pa.Column(float, checks=pa.Check.gt(0)),
        "low": pa.Column(float, checks=pa.Check.gt(0)),
        "close": pa.Column(float, checks=pa.Check.gt(0)),
        "volume": pa.Column(float, checks=pa.Check.ge(0)),
    },
    strict=False,
    coerce=True,
)


def validate_ohlcv(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        validated = OHLCVSchema.validate(df, lazy=True)
        return validated, pd.DataFrame()
    except pa.errors.SchemaErrors as e:
        failure_cases = e.failure_cases
        invalid_indices = failure_cases["index"].dropna().unique()
        invalid_rows = df.loc[df.index.isin(invalid_indices)]
        valid_rows = df.loc[~df.index.isin(invalid_indices)]
        return valid_rows, invalid_rows