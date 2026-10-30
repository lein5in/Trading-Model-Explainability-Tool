import json
import os

INPUT_DIR = "/sandbox_input"
OUTPUT_DIR = "/sandbox_output"
INPUT_FILE_NAME = "input.json"
OUTPUT_FILE_NAME = "output.json"
DEFAULT_OUTPUT_CAP_BYTES = 20 * 1024 * 1024


class SandboxTaskError(Exception):
    def __init__(self, message: str, code: str = "model_error", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def apply_output_limit(cap_bytes: int) -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_FSIZE, (cap_bytes, cap_bytes))


def read_payload(input_dir: str = INPUT_DIR) -> dict:
    with open(os.path.join(input_dir, INPUT_FILE_NAME), "r") as f:
        return json.load(f)


def load_model(payload: dict, input_dir: str = INPUT_DIR):
    import joblib

    return joblib.load(os.path.join(input_dir, payload["model_file"]))


def write_output(result: dict, output_dir: str = OUTPUT_DIR) -> None:
    with open(os.path.join(output_dir, OUTPUT_FILE_NAME), "w") as f:
        json.dump(result, f)


def run_entrypoint(handler) -> None:
    try:
        payload = read_payload()
        apply_output_limit(int(payload.get("output_cap_bytes", DEFAULT_OUTPUT_CAP_BYTES)))
        model = load_model(payload)
        result = {"success": True, "error": None}
        result.update(handler(model, payload))
    except SandboxTaskError as exc:
        result = {"success": False, "error": str(exc), "code": exc.code, "details": exc.details}
    except Exception as exc:
        result = {"success": False, "error": f"{type(exc).__name__}: {exc}", "code": "model_error"}
    write_output(result)
