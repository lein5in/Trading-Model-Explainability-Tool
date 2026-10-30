import io
import json
import math
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest
from app.data import ingestion
from app.data.schemas import validate_ohlcv
from app.db.repository import InMemoryRepository
from app.pipeline import stages
from app.pipeline.jobs import AnalysisJob, JobManager
from app.pipeline.recovery import recover_interrupted
from app.pipeline.sandbox_client import SandboxClient
from app.pipeline.sanitize import sanitize_json
from app.sandbox import runner
from app.sandbox.runner import SandboxExecutionError

FEATURES = ["rsi_14", "vol_20d"]
NAN_EVERY = 7
WAIT_SECONDS = 60


def bundled_fetch(ticker, start, end, repository=None, now=None):
    frame = ingestion.load_fallback("SPY", start, end)
    valid, invalid_count = validate_ohlcv(frame)
    return {"data": valid, "invalid_count": invalid_count, "data_source": "bundled", "cached": False}


@pytest.fixture(autouse=True)
def offline_market_data(monkeypatch):
    monkeypatch.setattr(stages, "fetch_ohlcv", bundled_fetch)


def ok_report(state):
    return {"status": "ok", "model": "fake", "sections": [], "verification": {}}


class FakeSandbox:
    def __init__(self, nan_outputs=False, preflight_error=None, explain_error=None, predict_gate=None, predict_delay=0.0):
        self.calls = []
        self.nan_outputs = nan_outputs
        self.preflight_error = preflight_error
        self.explain_error = explain_error
        self.predict_gate = predict_gate
        self.predict_delay = predict_delay

    def preflight(self, model_path, feature_names, rows, timeout_seconds):
        self.calls.append("preflight")
        if self.preflight_error is not None:
            raise self.preflight_error
        return {
            "column_order": list(feature_names),
            "reordered": False,
            "signal_type": "discrete",
            "explained_output": "P(buy)",
            "explained_class": 1,
            "model_class": "sklearn.tree._classes.DecisionTreeClassifier",
            "family": "DecisionTreeClassifier",
            "sample_outputs": [0.5] * len(rows),
        }

    def predict(self, model_path, feature_names, rows, timeout_seconds):
        self.calls.append("predict")
        if self.predict_gate is not None:
            self.predict_gate.wait(WAIT_SECONDS)
        if self.predict_delay:
            time.sleep(self.predict_delay)
        outputs = [0.5 + 0.4 * math.sin(i / 9.0) for i in range(len(rows))]
        if self.nan_outputs:
            outputs = [float("nan") if i % NAN_EVERY == 0 else value for i, value in enumerate(outputs)]
        return {"outputs": outputs}

    def explain(self, model_path, payload, timeout_seconds):
        self.calls.append("explain")
        if self.explain_error is not None:
            raise self.explain_error
        width = len(payload["feature_names"])
        global_rows = np.asarray(payload["global_rows"]).reshape(-1, width)
        trade_rows = np.asarray(payload["trade_rows"]).reshape(-1, width)
        return {
            "explainer": "tree",
            "explained_output": "P(buy)",
            "explained_class": 1,
            "base_value": 0.5,
            "max_additivity_gap": 0.0,
            "global_values": (global_rows * 0.001).tolist(),
            "global_outputs": [0.5] * len(global_rows),
            "trade_values": (trade_rows * 0.001).tolist(),
            "trade_outputs": [0.5] * len(trade_rows),
        }


def submit(client, start="2015-01-01", end="2017-12-31"):
    return client.post(
        "/analysis/run",
        data={"ticker": "SPY", "start_date": start, "end_date": end, "feature_ids": json.dumps(FEATURES)},
        files={"model_file": ("model.pkl", io.BytesIO(b"model-bytes"), "application/octet-stream")},
    )


def run_to_end(make_api, sandbox, report_generator=ok_report, repository=None):
    client, services = make_api(run_job=None, sandbox=sandbox, report_generator=report_generator, repository=repository)
    response = submit(client)
    analysis_id = response.json()["analysis_id"]
    services.job_manager.wait(analysis_id, timeout=WAIT_SECONDS)
    return client, services, analysis_id


def stored(services, analysis_id):
    return services.repository.get_analysis(analysis_id)


def test_submission_returns_202_immediately_and_status_moves_through_stages(make_api):
    gate = threading.Event()
    sandbox = FakeSandbox(predict_gate=gate)
    client, services = make_api(run_job=None, sandbox=sandbox, report_generator=ok_report)

    started = time.monotonic()
    response = submit(client)
    assert response.status_code == 202
    assert time.monotonic() - started < 5
    analysis_id = response.json()["analysis_id"]

    status = None
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        status = client.get(f"/analysis/{analysis_id}/status").json()
        if status["stage"] == "predict":
            break
        time.sleep(0.05)
    assert status["status"] == "running"
    assert status["stages"]["validate"]["state"] == "done"
    assert status["stages"]["predict"]["state"] == "running"
    assert status["stages"]["backtest"]["state"] == "pending"

    gate.set()
    services.job_manager.wait(analysis_id, timeout=WAIT_SECONDS)
    final = client.get(f"/analysis/{analysis_id}/status").json()
    assert final["status"] == "completed"
    assert final["stage"] == "done"
    assert all(item["state"] == "done" for item in final["stages"].values())
    assert all(isinstance(item["duration_ms"], int) for item in final["stages"].values())
    assert final["error"] is None


def test_completed_analysis_contains_every_stage_output(make_api):
    client, services, analysis_id = run_to_end(make_api, FakeSandbox())
    body = client.get(f"/analysis/{analysis_id}").json()
    result = body["result"]
    assert body["status"] == "completed"
    assert set(result) >= {"data", "bars", "predictions", "backtest", "regimes", "shap", "stages"}
    assert body["model_meta"]["signal_type"] == "discrete"
    assert body["model_meta"]["feature_columns"] == FEATURES
    assert result["data"]["data_source"] == "bundled"
    assert result["data"]["effective_start"] == "2015-01-02"
    assert result["predictions"]["rule"].startswith("P(buy) >= 0.50")
    assert "client_ip_hash" not in body
    trades = result["backtest"]["trades"]
    regime_labels = result["regimes"]["regime_per_bar"]
    assert trades
    for trade in trades:
        assert trade["regime"] == regime_labels[trade["signal_bar_index"]]
        if trade["shap_row_index"] is not None:
            assert result["shap"]["trade_rows"][trade["shap_row_index"]]["trade_id"] == trade["id"]


def test_probability_threshold_gives_the_signals(make_api):
    client, services, analysis_id = run_to_end(make_api, FakeSandbox())
    predictions = stored(services, analysis_id)["result"]["predictions"]
    for output, signal in zip(predictions["output"], predictions["signal"]):
        assert signal == (1 if output >= 0.5 else -1)


def test_nan_signals_do_not_crash_and_are_counted(make_api):
    client, services, analysis_id = run_to_end(make_api, FakeSandbox(nan_outputs=True))
    response = client.get(f"/analysis/{analysis_id}")
    assert response.status_code == 200
    body = response.json()
    predictions = body["result"]["predictions"]
    expected_nan = sum(1 for i in range(body["result"]["data"]["n_bars"]) if i % NAN_EVERY == 0)
    assert body["status"] == "completed"
    assert predictions["nan_outputs"] == expected_nan
    assert body["result"]["backtest"]["ignored_bar_count"] == expected_nan
    assert predictions["output"][0] is None and predictions["signal"][0] is None
    json.dumps(stored(services, analysis_id), allow_nan=False)
    json.dumps(body, allow_nan=False)


def test_sanitizer_converts_nan_and_infinity_at_every_level():
    raw = {
        "a": [1.0, float("nan"), {"b": float("inf"), "c": [-float("inf"), np.float64("nan"), np.float32(2.5)]}],
        "d": np.int64(3),
        "e": (np.array([np.nan, 1.0]), {"f": {"g": np.inf}}),
        "h": pd.Timestamp("2024-01-02"),
        "i": np.bool_(True),
    }
    clean = sanitize_json(raw)
    assert clean == {
        "a": [1.0, None, {"b": None, "c": [None, None, 2.5]}],
        "d": 3,
        "e": [[None, 1.0], {"f": {"g": None}}],
        "h": "2024-01-02T00:00:00",
        "i": True,
    }
    json.dumps(clean, allow_nan=False)


def test_preflight_failure_fails_immediately_without_predicting(make_api):
    error = SandboxExecutionError("names differ", code="feature_mismatch", details={"missing": ["x"], "unexpected": ["rsi_14"]})
    sandbox = FakeSandbox(preflight_error=error)
    client, services, analysis_id = run_to_end(make_api, sandbox)
    status = client.get(f"/analysis/{analysis_id}/status").json()
    assert status["status"] == "failed"
    assert status["stage"] == "validate"
    assert status["error"]["code"] == "preflight_failed"
    assert status["error"]["details"]["reason"] == "feature_mismatch"
    assert status["error"]["details"]["missing"] == ["x"]
    assert sandbox.calls == ["preflight"]


def test_shap_failure_gives_partial_with_backtest_and_regimes_kept(make_api):
    error = SandboxExecutionError("gap", code="shap_additivity_failed", details={"max_gap": 0.3})
    client, services, analysis_id = run_to_end(make_api, FakeSandbox(explain_error=error))
    row = stored(services, analysis_id)
    assert row["status"] == "partial"
    assert row["result"]["backtest"]["equity_curve"]
    assert row["result"]["regimes"]["regimes_available"] is True
    assert "shap" not in row["result"]
    assert row["result"]["stages"]["shap"]["state"] == "failed"
    assert row["result"]["stages"]["report"]["state"] == "done"
    error_body = client.get(f"/analysis/{analysis_id}/status").json()["error"]
    assert error_body["code"] == "shap_additivity_failed"
    assert error_body["details"]["max_gap"] == 0.3
    assert error_body["details"]["epsilon"] == 0.01


def test_report_failure_gives_partial(make_api):
    def failing_report(state):
        return {"status": "failed", "error": {"code": "report_truncated", "message": "cut"}}

    client, services, analysis_id = run_to_end(make_api, FakeSandbox(), report_generator=failing_report)
    row = stored(services, analysis_id)
    assert row["status"] == "partial"
    assert row["report"]["status"] == "failed"
    assert json.loads(row["error"])["code"] == "report_truncated"


def test_backtest_failure_gives_failed(make_api, monkeypatch):
    def broken_backtest(*args, **kwargs):
        raise ValueError("injected")

    monkeypatch.setattr(stages, "run_backtest", broken_backtest)
    client, services, analysis_id = run_to_end(make_api, FakeSandbox())
    row = stored(services, analysis_id)
    assert row["status"] == "failed"
    assert row["stage"] == "backtest"
    assert json.loads(row["error"])["code"] == "backtest_failed"
    assert "regimes" not in row["result"]
    assert row["result"]["predictions"]["signal"]


def test_sandbox_timeout_kills_the_container_and_marks_failed(make_api, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["docker", "start"]:
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    client, services, analysis_id = run_to_end(make_api, SandboxClient())
    name = calls[0][calls[0].index("--name") + 1]
    assert ["docker", "kill", name] in calls
    assert ["docker", "rm", "-f", name] in calls
    status = client.get(f"/analysis/{analysis_id}/status").json()
    assert status["status"] == "failed"
    assert status["error"]["code"] == "timeout"


def test_job_deadline_marks_failed_timeout_and_keeps_earlier_results(make_api, monkeypatch):
    monkeypatch.setenv("JOB_TIMEOUT_SECONDS", "1.5")
    client, services, analysis_id = run_to_end(make_api, FakeSandbox(predict_delay=1.6))
    row = stored(services, analysis_id)
    assert row["status"] == "failed"
    assert json.loads(row["error"])["code"] == "timeout"
    assert row["stage"] == "backtest"
    assert row["result"]["predictions"]["output"]
    assert row["result"]["stages"]["predict"]["state"] == "done"


def test_startup_recovery_marks_stale_analyses_failed(make_api):
    repository = InMemoryRepository()
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    stale_running = repository.create_analysis({"status": "running", "stage": "shap", "created_at": old})
    stale_queued = repository.create_analysis({"status": "queued", "stage": "validate", "created_at": old})
    fresh = repository.create_analysis({"status": "running", "stage": "predict"})
    done = repository.create_analysis({"status": "completed", "stage": "done", "created_at": old})

    client, _ = make_api(repository=repository)
    with client:
        pass

    assert repository.get_analysis(stale_running["id"])["status"] == "failed"
    assert json.loads(repository.get_analysis(stale_running["id"])["error"])["code"] == "interrupted"
    assert repository.get_analysis(stale_queued["id"])["status"] == "failed"
    assert repository.get_analysis(fresh["id"])["status"] == "running"
    assert repository.get_analysis(done["id"])["status"] == "completed"
    assert recover_interrupted(repository, 300) == 0


def test_semaphore_never_runs_more_than_two_jobs():
    lock = threading.Lock()
    active = {"now": 0, "max": 0}

    def slow_job(job):
        with lock:
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
        time.sleep(0.2)
        with lock:
            active["now"] -= 1

    manager = JobManager(slow_job, max_concurrent_jobs=2)
    jobs = [AnalysisJob(analysis_id=str(i), params={}, model_meta={}, model_path="") for i in range(6)]
    for job in jobs:
        manager.submit(job)
    for job in jobs:
        manager.wait(job.analysis_id, timeout=WAIT_SECONDS)
    manager.shutdown()
    assert active["max"] == 2


def test_waiting_jobs_stay_queued(make_api, monkeypatch):
    monkeypatch.setenv("MAX_CONCURRENT_JOBS", "1")
    gate = threading.Event()
    client, services = make_api(run_job=None, sandbox=FakeSandbox(predict_gate=gate), report_generator=ok_report)
    first = submit(client).json()["analysis_id"]
    second = submit(client).json()["analysis_id"]
    deadline = time.monotonic() + WAIT_SECONDS
    while client.get(f"/analysis/{first}/status").json()["stage"] != "predict" and time.monotonic() < deadline:
        time.sleep(0.05)
    assert client.get(f"/analysis/{second}/status").json()["status"] == "queued"
    gate.set()
    services.job_manager.wait(first, timeout=WAIT_SECONDS)
    services.job_manager.wait(second, timeout=WAIT_SECONDS)
    assert client.get(f"/analysis/{second}/status").json()["status"] == "completed"


def test_unknown_id_gives_404_on_every_read_endpoint(make_api):
    client, _ = make_api()
    for path in ["/analysis/7b0e4c58-7c4b-4a39-9a49-3f2f7c0b1a11", "/analysis/7b0e4c58-7c4b-4a39-9a49-3f2f7c0b1a11/status", "/analysis/not-a-uuid"]:
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["code"] == "analysis_not_found"


def regressor_preflight(self, model_path, feature_names, rows, timeout_seconds):
    result = FakeSandbox.preflight(self, model_path, feature_names, rows, timeout_seconds)
    result.update({"signal_type": "continuous", "explained_output": "prediction", "explained_class": None, "family": "GradientBoostingRegressor"})
    return result


class ReturnRegressorSandbox(FakeSandbox):
    preflight = regressor_preflight

    def predict(self, model_path, feature_names, rows, timeout_seconds):
        return {"outputs": [0.004 if i % 2 == 0 else -0.004 for i in range(len(rows))]}


def test_default_dead_zone_turns_small_predicted_returns_into_long_and_short(make_api):
    from app.config import get_settings
    from app.pipeline.signals import outputs_to_signals

    assert get_settings().continuous_signal_dead_zone == 0.0
    assert outputs_to_signals([0.004, -0.004, 0.0, None], "continuous", 0.0) == [1, -1, 0, None]
    client, services, analysis_id = run_to_end(make_api, ReturnRegressorSandbox())
    predictions = stored(services, analysis_id)["result"]["predictions"]
    assert set(predictions["signal"]) == {1, -1}
    assert predictions["threshold"] == 0.0


def test_explicit_dead_zone_keeps_the_same_predictions_flat(make_api, monkeypatch):
    from app.pipeline.signals import outputs_to_signals

    monkeypatch.setenv("CONTINUOUS_SIGNAL_DEAD_ZONE", "0.1")
    assert outputs_to_signals([0.004, -0.004], "continuous", 0.1) == [0, 0]
    client, services, analysis_id = run_to_end(make_api, ReturnRegressorSandbox())
    row = stored(services, analysis_id)
    assert set(row["result"]["predictions"]["signal"]) == {0}
    assert row["result"]["backtest"]["trades"] == []
