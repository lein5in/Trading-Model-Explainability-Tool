from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.models.wrapper import ModelMetadata, SignalType
from app.models.validation import register_model, ModelValidationError

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/upload")
async def upload_model(
    name: str = Form(...),
    signal_type: SignalType = Form(...),
    expected_columns: str = Form(...),
    file: UploadFile = File(...),
):
    columns_list = [c.strip() for c in expected_columns.split(",") if c.strip()]
    metadata = ModelMetadata(name=name, signal_type=signal_type, expected_columns=columns_list)
    file_bytes = await file.read()

    try:
        registered = register_model(metadata, file_bytes, file.filename)
    except ModelValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return registered