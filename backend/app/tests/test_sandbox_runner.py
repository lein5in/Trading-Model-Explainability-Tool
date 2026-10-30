import json
import os
import pickle
import subprocess
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.tree import DecisionTreeClassifier
from app.config import ConfigurationError, validate_sandbox_runtime
from app.sandbox import runner
from app.tests.conftest import requires_docker

SLEEPING_PICKLE = b"ctime\nsleep\n(I999\ntR."

EXPECTED_FLAGS = [
    "--network=none",
    "--memory=512m",
    "--cpus=1",
    "--cap-drop=ALL",
    "--pids-limit=128",
    "--read-only",
]


def write_dummy_model(tmp_path, name="model.pkl") -> str:
    path = tmp_path / name
    path.write_bytes(b"not a real model")
    return str(path)


class RecordingRun:
    def __init__(self, behaviour=None):
        self.calls = []
        self.behaviour = behaviour
        self.create_command = None

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if command[:2] == ["docker", "create"]:
            self.create_command = command
        if command[:2] == ["docker", "start"] and self.behaviour is not None:
            return self.behaviour(self.create_command, **kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")


def output_dir_from_command(command: list[str]) -> str:
    for index, part in enumerate(command):
        if part == "-v" and command[index + 1].endswith(":/sandbox_output"):
            return command[index + 1][: -len(":/sandbox_output")]
    raise AssertionError("output mount not found")


def input_dir_from_command(command: list[str]) -> str:
    for index, part in enumerate(command):
        if part == "-v" and command[index + 1].endswith(":/sandbox_input:ro"):
            return command[index + 1][: -len(":/sandbox_input:ro")]
    raise AssertionError("input mount not found")


def write_success_output(command, **kwargs):
    with open(os.path.join(output_dir_from_command(command), "output.json"), "w") as f:
        json.dump({"success": True, "error": None, "predictions": [1]}, f)
    return subprocess.CompletedProcess(command, 0, "", "")


def test_docker_command_contains_every_hardening_flag_and_the_name(tmp_path, monkeypatch):
    recorder = RecordingRun(write_success_output)
    monkeypatch.setattr(runner.subprocess, "run", recorder)

    runner.run_sandbox("app.sandbox.predict_entrypoint", write_dummy_model(tmp_path), {"records": []}, 10)

    command = recorder.calls[0]
    assert command[:2] == ["docker", "create"]
    assert recorder.calls[1] == ["docker", "start", "-a", command[command.index("--name") + 1]]
    for flag in EXPECTED_FLAGS:
        assert flag in command
    assert command[command.index("--security-opt") + 1] == "no-new-privileges"
    assert command[command.index("--tmpfs") + 1] == "/tmp:rw,noexec,nosuid,size=64m"
    assert command[command.index("--user") + 1] == "65534:65534"
    assert "--runtime=runc" in command
    name = command[command.index("--name") + 1]
    assert name.startswith("tme-")
    assert any(part.endswith(":/sandbox_input:ro") for part in command)


def test_timeout_kills_and_removes_the_same_container(tmp_path, monkeypatch):
    def raise_timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))

    recorder = RecordingRun(raise_timeout)
    monkeypatch.setattr(runner.subprocess, "run", recorder)

    with pytest.raises(runner.SandboxTimeoutError):
        runner.run_sandbox("app.sandbox.predict_entrypoint", write_dummy_model(tmp_path), {"records": []}, 3)

    name = recorder.calls[0][recorder.calls[0].index("--name") + 1]
    assert recorder.calls[1] == ["docker", "start", "-a", name]
    assert recorder.calls[2] == ["docker", "kill", name]
    assert recorder.calls[3] == ["docker", "rm", "-f", name]


def test_any_exception_also_kills_and_removes_the_container(tmp_path, monkeypatch):
    def raise_interrupt(command, **kwargs):
        raise KeyboardInterrupt()

    recorder = RecordingRun(raise_interrupt)
    monkeypatch.setattr(runner.subprocess, "run", recorder)

    with pytest.raises(KeyboardInterrupt):
        runner.run_sandbox("app.sandbox.predict_entrypoint", write_dummy_model(tmp_path), {"records": []}, 3)

    name = recorder.calls[0][recorder.calls[0].index("--name") + 1]
    assert recorder.calls[1:] == [
        ["docker", "start", "-a", name],
        ["docker", "kill", name],
        ["docker", "rm", "-f", name],
    ]


def test_work_dir_is_removed_after_the_run(tmp_path, monkeypatch):
    recorder = RecordingRun(write_success_output)
    monkeypatch.setattr(runner.subprocess, "run", recorder)

    runner.run_sandbox("app.sandbox.predict_entrypoint", write_dummy_model(tmp_path), {"records": []}, 10)

    assert not os.path.exists(input_dir_from_command(recorder.calls[0]))


def test_model_keeps_its_original_extension(tmp_path, monkeypatch):
    seen = {}

    def inspect_input(command, **kwargs):
        input_dir = input_dir_from_command(command)
        seen["files"] = sorted(os.listdir(input_dir))
        with open(os.path.join(input_dir, "input.json")) as f:
            seen["payload"] = json.load(f)
        return write_success_output(command, **kwargs)

    monkeypatch.setattr(runner.subprocess, "run", RecordingRun(inspect_input))

    runner.run_sandbox("app.sandbox.predict_entrypoint", write_dummy_model(tmp_path, "clf.joblib"), {"records": []}, 10)

    assert seen["files"] == ["input.json", "model.joblib"]
    assert seen["payload"]["model_file"] == "model.joblib"
    assert seen["payload"]["output_cap_bytes"] == 20 * 1024 * 1024


@pytest.mark.parametrize(
    "environment,runtime",
    [("production", "runsc"), ("development", "runc"), ("development", "runsc"), ("test", "runc")],
)
def test_runtime_validation_accepts(environment, runtime):
    assert validate_sandbox_runtime(environment, runtime) == runtime


@pytest.mark.parametrize(
    "environment,runtime",
    [
        ("production", "runc"),
        ("production", ""),
        ("production", None),
        ("production", "kata-runtime-value"),
        ("development", ""),
        ("development", None),
        ("development", "kata-runtime-value"),
    ],
)
def test_runtime_validation_fails_closed(environment, runtime):
    with pytest.raises(ConfigurationError) as excinfo:
        validate_sandbox_runtime(environment, runtime)
    assert "kata-runtime-value" not in str(excinfo.value)


def test_run_refuses_to_start_with_an_invalid_runtime(tmp_path, monkeypatch):
    recorder = RecordingRun(write_success_output)
    monkeypatch.setattr(runner.subprocess, "run", recorder)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SANDBOX_DOCKER_RUNTIME", "runc")

    with pytest.raises(ConfigurationError):
        runner.run_sandbox("app.sandbox.predict_entrypoint", write_dummy_model(tmp_path), {"records": []}, 10)

    assert recorder.calls == []


def test_application_startup_fails_with_a_missing_runtime(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setenv("SANDBOX_DOCKER_RUNTIME", "")
    with pytest.raises(ConfigurationError):
        with TestClient(app):
            pass


def test_oversized_output_file_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_OUTPUT_CAP_BYTES", "100")

    def write_large_output(command, **kwargs):
        with open(os.path.join(output_dir_from_command(command), "output.json"), "w") as f:
            json.dump({"success": True, "predictions": [1.0] * 200}, f)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(runner.subprocess, "run", RecordingRun(write_large_output))

    with pytest.raises(runner.SandboxOutputTooLargeError):
        runner.run_sandbox("app.sandbox.predict_entrypoint", write_dummy_model(tmp_path), {"records": []}, 10)


def build_records_and_labels() -> tuple[pd.DataFrame, list[int]]:
    X = pd.DataFrame({
        "feature_a": [0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6],
        "feature_b": [1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0],
    })
    y = [-1, 1, -1, 1, -1, 1, -1, 1]
    return X, y


def list_tme_containers() -> list[str]:
    completed = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=tme-", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return [line for line in completed.stdout.splitlines() if line.startswith("tme-")]


@requires_docker
def test_joblib_model_predicts_end_to_end(tmp_path):
    X, y = build_records_and_labels()
    model = DecisionTreeClassifier(max_depth=2, random_state=0).fit(X, y)
    path = tmp_path / "tree.joblib"
    joblib.dump(model, path)

    result = runner.run_predict_in_sandbox(str(path), list(X.columns), X.to_numpy().tolist())

    assert result["outputs"] == pytest.approx(list(model.predict_proba(X)[:, 1]))


@requires_docker
@pytest.mark.parametrize("library", ["xgboost", "lightgbm"])
def test_boosting_models_predict_inside_the_image(tmp_path, library):
    X, y = build_records_and_labels()
    labels = np.array([0 if value < 0 else 1 for value in y])
    if library == "xgboost":
        from xgboost import XGBClassifier
        model = XGBClassifier(n_estimators=5, max_depth=2, random_state=0).fit(X, labels)
    else:
        from lightgbm import LGBMClassifier
        model = LGBMClassifier(n_estimators=5, max_depth=2, min_child_samples=1, random_state=0, verbose=-1).fit(X, labels)
    path = tmp_path / f"{library}.pkl"
    path.write_bytes(pickle.dumps(model))

    result = runner.run_predict_in_sandbox(str(path), list(X.columns), X.to_numpy().tolist())

    assert result["outputs"] == pytest.approx(list(model.predict_proba(X)[:, 1]), rel=1e-6)


@requires_docker
def test_sleeping_pickle_is_killed_and_leaves_no_container(tmp_path):
    path = tmp_path / "sleep.pkl"
    path.write_bytes(SLEEPING_PICKLE)

    with pytest.raises(runner.SandboxTimeoutError):
        runner.run_predict_in_sandbox(str(path), ["a"], [[1.0]], timeout_seconds=3)

    assert list_tme_containers() == []
