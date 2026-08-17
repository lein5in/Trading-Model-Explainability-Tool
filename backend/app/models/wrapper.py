from enum import Enum
from pydantic import BaseModel, Field


class SignalType(str, Enum):
    DISCRETE = "discrete"
    CONTINUOUS = "continuous"


class ModelMetadata(BaseModel):
    name: str
    signal_type: SignalType
    expected_columns: list[str] = Field(min_length=1)


class RegisteredModel(BaseModel):
    id: str
    name: str
    signal_type: SignalType
    expected_columns: list[str]
    storage_path: str
    status: str