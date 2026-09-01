import os
import json
import shutil
import subprocess
import tempfile
import uuid
from app.config import SANDBOX_DOCKER_RUNTIME

SANDBOX_IMAGE = "trading-explainability-sandbox"
DEFAULT_PREDICT_TIMEOUT_SECONDS = 30
DEFAULT_EXPLAIN_TIMEOUT_SECONDS = 180
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_CPU_LIMIT = "1"


def _resolve_runtime() -> str:
    return SANDBOX_DOCKER_RUNTIME


class SandboxExecutionError(Exception):
    pass


class SandboxTimeoutError(SandboxExecutionError):
    pass


def _run_sandbox(
    entrypoint_script: str,
    model_storage_path: str,
    payload: dict,
    timeout_seconds: int,
) -> dict:
    run_id = str(uuid.uuid4())
    work_dir = tempfile.mkdtemp(prefix=f"sandbox_{run_id}_")
    input_dir = os.path.join(work_dir, "input")
    output_dir = os.path.join(work_dir, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    try:
        model_dest = os.path.join(input_dir, "model.pkl")
        shutil.copyfile(model_storage_path, model_dest)

        input_json_path = os.path.join(input_dir, "input.json")
        with open(input_json_path, "w") as f:
            json.dump(payload, f)

        runtime = _resolve_runtime()

        docker_cmd = [
            "docker", "run",
            "--rm",
            f"--runtime={runtime}",
            "--network=none",
            f"--memory={DEFAULT_MEMORY_LIMIT}",
            f"--cpus={DEFAULT_CPU_LIMIT}",
            "-v", f"{input_dir}:/sandbox_input:ro",
            "-v", f"{output_dir}:/sandbox_output",
            SANDBOX_IMAGE,
            "python", entrypoint_script,
        ]

        try:
            completed = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            raise SandboxTimeoutError(
                f"Sandbox execution exceeded timeout of {timeout_seconds} seconds."
            )

        output_json_path = os.path.join(output_dir, "output.json")
        if not os.path.exists(output_json_path):
            raise SandboxExecutionError(
                f"Sandbox produced no output. stderr: {completed.stderr}"
            )

        with open(output_json_path, "r") as f:
            result = json.load(f)

        if not result.get("success"):
            raise SandboxExecutionError(result.get("error", "Unknown sandbox error."))

        return result

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def run_predict_in_sandbox(
    model_storage_path: str,
    records: list[dict],
    signal_type: str,
    timeout_seconds: int = DEFAULT_PREDICT_TIMEOUT_SECONDS,
) -> dict:
    result = _run_sandbox(
        entrypoint_script="predict_entrypoint.py",
        model_storage_path=model_storage_path,
        payload={"records": records, "signal_type": signal_type},
        timeout_seconds=timeout_seconds,
    )
    return {"predictions": result["predictions"]}


def run_explain_in_sandbox(
    model_storage_path: str,
    records: list[dict],
    background_records: list[dict] = None,
    timeout_seconds: int = DEFAULT_EXPLAIN_TIMEOUT_SECONDS,
) -> dict:
    payload = {"records": records}
    if background_records is not None:
        payload["background_records"] = background_records

    result = _run_sandbox(
        entrypoint_script="explain_entrypoint.py",
        model_storage_path=model_storage_path,
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    return {
        "explainer_type": result["explainer_type"],
        "shap_values": result["shap_values"],
        "base_value": result["base_value"],
        "feature_names": result["feature_names"],
        "additivity_error": result["additivity_error"],
    }