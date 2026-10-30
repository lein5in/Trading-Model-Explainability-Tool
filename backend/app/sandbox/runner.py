import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from app.config import get_sandbox_output_cap_bytes, get_sandbox_runtime

SANDBOX_IMAGE = "trading-explainability-sandbox"
CONTAINER_NAME_PREFIX = "tme-"
DEFAULT_PREDICT_TIMEOUT_SECONDS = 30
DEFAULT_EXPLAIN_TIMEOUT_SECONDS = 180
DOCKER_CLEANUP_TIMEOUT_SECONDS = 30
MEMORY_LIMIT = "512m"
CPU_LIMIT = "1"
PIDS_LIMIT = "128"
TMPFS_SPEC = "/tmp:rw,noexec,nosuid,size=64m"
SANDBOX_USER = "65534:65534"
MODEL_FILE_BASENAME = "model"
ALLOWED_MODEL_EXTENSIONS = (".pkl", ".pickle", ".joblib")
STDERR_TAIL_CHARS = 2000


class SandboxExecutionError(Exception):
    def __init__(self, message: str, code: str = "sandbox_error", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class SandboxTimeoutError(SandboxExecutionError):
    def __init__(self, message: str, container_name: str | None = None):
        super().__init__(message, code="timeout", details={"container_name": container_name})
        self.container_name = container_name


class SandboxOutputTooLargeError(SandboxExecutionError):
    def __init__(self, message: str):
        super().__init__(message, code="sandbox_output_too_large")


def new_container_name() -> str:
    return f"{CONTAINER_NAME_PREFIX}{uuid.uuid4()}"


def build_docker_command(
    container_name: str,
    runtime: str,
    input_dir: str,
    output_dir: str,
    module: str,
) -> list[str]:
    return [
        "docker", "create",
        "--rm",
        "--name", container_name,
        f"--runtime={runtime}",
        "--network=none",
        f"--memory={MEMORY_LIMIT}",
        f"--cpus={CPU_LIMIT}",
        "--cap-drop=ALL",
        "--security-opt", "no-new-privileges",
        f"--pids-limit={PIDS_LIMIT}",
        "--read-only",
        "--tmpfs", TMPFS_SPEC,
        "--user", SANDBOX_USER,
        "-v", f"{input_dir}:/sandbox_input:ro",
        "-v", f"{output_dir}:/sandbox_output",
        SANDBOX_IMAGE,
        "python", "-m", module,
    ]


def force_remove_container(container_name: str) -> None:
    for command in (["docker", "kill", container_name], ["docker", "rm", "-f", container_name]):
        try:
            subprocess.run(command, capture_output=True, text=True, timeout=DOCKER_CLEANUP_TIMEOUT_SECONDS)
        except Exception:
            pass


def model_file_name(model_path: str) -> str:
    extension = os.path.splitext(model_path)[1].lower()
    if extension not in ALLOWED_MODEL_EXTENSIONS:
        extension = ".bin"
    return f"{MODEL_FILE_BASENAME}{extension}"


def read_sandbox_output(output_path: str, cap_bytes: int, stderr: str) -> dict:
    if not os.path.exists(output_path):
        raise SandboxExecutionError(
            "Sandbox produced no output.",
            details={"stderr_tail": (stderr or "")[-STDERR_TAIL_CHARS:]},
        )
    size = os.path.getsize(output_path)
    if size > cap_bytes:
        raise SandboxOutputTooLargeError(
            f"Sandbox output is {size} bytes, above the cap of {cap_bytes} bytes."
        )
    try:
        with open(output_path, "r") as f:
            result = json.load(f)
    except ValueError:
        raise SandboxExecutionError(
            "Sandbox output is not valid JSON.",
            details={"stderr_tail": (stderr or "")[-STDERR_TAIL_CHARS:]},
        )
    if not result.get("success"):
        raise SandboxExecutionError(
            result.get("error") or "Unknown sandbox error.",
            code=result.get("code") or "model_error",
            details=result.get("details") or {},
        )
    return result


def prepare_work_dir(model_path: str, payload: dict, cap_bytes: int) -> tuple[str, str, str]:
    work_dir = tempfile.mkdtemp(prefix="tme_sandbox_")
    input_dir = os.path.join(work_dir, "input")
    output_dir = os.path.join(work_dir, "output")
    os.makedirs(input_dir)
    os.makedirs(output_dir)

    model_name = model_file_name(model_path)
    shutil.copyfile(model_path, os.path.join(input_dir, model_name))

    full_payload = dict(payload)
    full_payload["model_file"] = model_name
    full_payload["output_cap_bytes"] = cap_bytes
    with open(os.path.join(input_dir, "input.json"), "w") as f:
        json.dump(full_payload, f)

    os.chmod(input_dir, 0o755)
    for name in os.listdir(input_dir):
        os.chmod(os.path.join(input_dir, name), 0o644)
    os.chmod(output_dir, 0o777)
    return work_dir, input_dir, output_dir


def run_sandbox(
    module: str,
    model_path: str,
    payload: dict,
    timeout_seconds: float,
    on_container_start=None,
) -> dict:
    runtime = get_sandbox_runtime()
    cap_bytes = get_sandbox_output_cap_bytes()
    if timeout_seconds <= 0:
        raise SandboxTimeoutError("No time left to start the sandbox.")

    work_dir, input_dir, output_dir = prepare_work_dir(model_path, payload, cap_bytes)
    container_name = new_container_name()
    deadline = time.monotonic() + timeout_seconds
    try:
        command = build_docker_command(container_name, runtime, input_dir, output_dir, module)
        if on_container_start is not None:
            on_container_start(container_name)
        try:
            created = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max(deadline - time.monotonic(), 0.001),
            )
            if created.returncode != 0:
                raise SandboxExecutionError(
                    "Sandbox container could not be created.",
                    details={"stderr_tail": (created.stderr or "")[-STDERR_TAIL_CHARS:]},
                )
            completed = subprocess.run(
                ["docker", "start", "-a", container_name],
                capture_output=True,
                text=True,
                timeout=max(deadline - time.monotonic(), 0.001),
            )
        except subprocess.TimeoutExpired:
            force_remove_container(container_name)
            raise SandboxTimeoutError(
                f"Sandbox execution exceeded timeout of {timeout_seconds:g} seconds.",
                container_name=container_name,
            )
        except BaseException:
            force_remove_container(container_name)
            raise
        return read_sandbox_output(os.path.join(output_dir, "output.json"), cap_bytes, completed.stderr)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def run_preflight_in_sandbox(
    model_path: str,
    feature_names: list[str],
    rows: list[list[float]],
    timeout_seconds: float = DEFAULT_PREDICT_TIMEOUT_SECONDS,
) -> dict:
    return run_sandbox(
        module="app.sandbox.predict_entrypoint",
        model_path=model_path,
        payload={"mode": "preflight", "feature_names": feature_names, "rows": rows},
        timeout_seconds=timeout_seconds,
    )


def run_predict_in_sandbox(
    model_path: str,
    feature_names: list[str],
    rows: list[list[float]],
    timeout_seconds: float = DEFAULT_PREDICT_TIMEOUT_SECONDS,
) -> dict:
    result = run_sandbox(
        module="app.sandbox.predict_entrypoint",
        model_path=model_path,
        payload={"mode": "predict", "feature_names": feature_names, "rows": rows},
        timeout_seconds=timeout_seconds,
    )
    return {"outputs": result["outputs"]}


def run_explain_in_sandbox(
    model_path: str,
    payload: dict,
    timeout_seconds: float = DEFAULT_EXPLAIN_TIMEOUT_SECONDS,
) -> dict:
    return run_sandbox(
        module="app.sandbox.explain_entrypoint",
        model_path=model_path,
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
