import os
import uuid
from app.models.wrapper import ModelMetadata, RegisteredModel

ALLOWED_EXTENSIONS = {".pkl", ".joblib"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
STORAGE_DIR = "storage/models"


class ModelValidationError(Exception):
    pass


def validate_upload_constraints(filename: str, file_size: int) -> None:
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise ModelValidationError(
            f"Unsupported file extension '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )
    if file_size <= 0:
        raise ModelValidationError("Uploaded file is empty.")
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ModelValidationError(
            f"File size {file_size} bytes exceeds maximum allowed {MAX_FILE_SIZE_BYTES} bytes."
        )


def validate_metadata(metadata: ModelMetadata) -> None:
    if not metadata.name.strip():
        raise ModelValidationError("Model name cannot be empty.")
    if len(set(metadata.expected_columns)) != len(metadata.expected_columns):
        raise ModelValidationError("expected_columns contains duplicate entries.")


def store_model_file(file_bytes: bytes, original_filename: str) -> tuple[str, str]:
    os.makedirs(STORAGE_DIR, exist_ok=True)
    _, ext = os.path.splitext(original_filename)
    model_id = str(uuid.uuid4())
    storage_path = os.path.join(STORAGE_DIR, f"{model_id}{ext}")
    with open(storage_path, "wb") as f:
        f.write(file_bytes)
    return model_id, storage_path


def register_model(metadata: ModelMetadata, file_bytes: bytes, original_filename: str) -> RegisteredModel:
    validate_upload_constraints(original_filename, len(file_bytes))
    validate_metadata(metadata)
    model_id, storage_path = store_model_file(file_bytes, original_filename)
    return RegisteredModel(
        id=model_id,
        name=metadata.name,
        signal_type=metadata.signal_type,
        expected_columns=metadata.expected_columns,
        storage_path=storage_path,
        status="uploaded_unvalidated",
    )