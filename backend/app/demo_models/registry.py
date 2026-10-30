import json
from pathlib import Path

DEMO_MODELS_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = DEMO_MODELS_DIR / "manifest.json"


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["models"]


def get_demo_model(demo_model_id: str) -> dict | None:
    for entry in load_manifest():
        if entry["id"] == demo_model_id:
            return entry
    return None


def demo_model_path(entry: dict) -> str:
    return str(DEMO_MODELS_DIR / entry["file"])
