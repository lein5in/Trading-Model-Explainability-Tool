from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from app.models.wrapper import ModelMetadata, SignalType, RegisteredModel
from app.models.validation import register_model, ModelValidationError
from app.db.client import get_supabase_client
from app.db.models import RegisteredModelInsert
from app.auth.dependencies import get_current_user_id

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/upload")
async def upload_model(
    name: str = Form(...),
    signal_type: SignalType = Form(...),
    expected_columns: str = Form(...),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    columns_list = [c.strip() for c in expected_columns.split(",") if c.strip()]
    metadata = ModelMetadata(name=name, signal_type=signal_type, expected_columns=columns_list)
    file_bytes = await file.read()

    try:
        registered = register_model(metadata, file_bytes, file.filename)
    except ModelValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    insert_payload = RegisteredModelInsert(
        user_id=user_id,
        name=registered.name,
        signal_type=registered.signal_type,
        expected_columns=registered.expected_columns,
        file_path=registered.storage_path,
        status=registered.status,
    )

    client = get_supabase_client()
    response = (
        client.table("registered_models")
        .insert(insert_payload.model_dump(mode="json"))
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to persist registered model.")

    row = response.data[0]

    return RegisteredModel(
        id=row["id"],
        name=row["name"],
        signal_type=row["signal_type"],
        expected_columns=row["expected_columns"],
        storage_path=row["file_path"],
        status=row["status"],
    )