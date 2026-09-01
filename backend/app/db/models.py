from datetime import datetime
from pydantic import BaseModel
from app.models.wrapper import SignalType


class RegisteredModelRecord(BaseModel):
    id: str
    user_id: str
    name: str
    signal_type: SignalType
    expected_columns: list[str]
    file_path: str
    status: str
    created_at: datetime


class RegisteredModelInsert(BaseModel):
    user_id: str
    name: str
    signal_type: SignalType
    expected_columns: list[str]
    file_path: str
    status: str


class AnalysisResultRecord(BaseModel):
    id: str
    model_id: str
    user_id: str
    ticker: str
    date_range: dict
    backtest_metrics: dict | None
    shap_summary: dict | None
    regime_labels: dict | None
    report_text: str | None
    ohlcv_data: list | None
    predictions: list | None
    status: str
    created_at: datetime


class AnalysisResultInsert(BaseModel):
    model_id: str
    user_id: str
    ticker: str
    date_range: dict
    backtest_metrics: dict | None = None
    shap_summary: dict | None = None
    regime_labels: dict | None = None
    report_text: str | None = None
    status: str = "pending"