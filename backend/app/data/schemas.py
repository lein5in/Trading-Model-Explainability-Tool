import pandera as pa 
from pandera.typing import Series 
import pandas as pd 

class OHLCVSchema(pa.DataFrameModel) :
    timestamp: Series[pd.Timestamp] = pa.Field(coerce=True)
    open: Series[float] = pa.Field(gt=0)
    high: Series[float] = pa.Field(gt=0)
    low: Series[float] = pa.Field(gt=0)
    close: Series[float] = pa.Field(gt=0)
    volume: Series[float] = pa.Field(ge=0)

    class Config : 
        strict = False 
        coerce = True

def validate_ohlcv(df : pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame] : 
    try : 
        validated = OHLCVSchema.validate(df, lazy=True)
        return validated, pd.DataFrame()
    except pa.errors.SchemaErrors as e : 
        failure_cases = exc.failure_cases
        invalid_indices = failure_cases["index"].dropna().unique()
        invalid_rows = df.loc[df.index.isin(invalid_indices)]
        valid_rows = df.loc[~df.index.isin(invalid_indices)]
        return valid_rows, invalid_rows
    