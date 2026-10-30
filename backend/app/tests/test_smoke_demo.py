import importlib.util
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "smoke_demo.py"
ANALYSIS_ID = "7b0e4c58-7c4b-4a39-9a49-3f2f7c0b1a11"
STAGE_NAMES = ["validate", "predict", "backtest", "regimes", "shap", "report"]


def load_script():
    spec = importlib.util.spec_from_file_location("smoke_demo", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def status_body(status: str, stage: str) -> dict:
    return {
        "analysis_id": ANALYSIS_ID,
        "status": status,
        "stage": stage,
        "stages": {name: {"state": "done", "duration_ms": 10 * (i + 1)} for i, name in enumerate(STAGE_NAMES)},
        "error": None,
    }


def analysis_body(status: str) -> dict:
    return {
        "id": ANALYSIS_ID,
        "status": status,
        "result": {
            "stages": {name: {"state": "done", "duration_ms": 10 * (i + 1)} for i, name in enumerate(STAGE_NAMES)},
            "backtest": {"trades": [{"id": 1}, {"id": 2}, {"id": 3}]},
            "regimes": {"regimes_available": True},
            "shap": {"explained_output": "P(buy)"},
        },
        "report": {"status": "ok", "verification": {"numbers_total": 31, "numbers_verified": 30}},
        "error": None,
    }


class FakeApi:
    def __init__(self, statuses: list[str], run_status: int = 202, final_status: str | None = None):
        self.statuses = list(statuses)
        self.run_status = run_status
        self.final_status = final_status or (statuses[-1] if statuses else "running")
        self.status_polls = 0
        self.posted = None

    def handler(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send_json(self, code: int, body: dict):
                payload = json.dumps(body).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                api.posted = {"path": self.path, "form": parse_qs(self.rfile.read(length).decode("utf-8"))}
                if api.run_status != 202:
                    self.send_json(api.run_status, {"code": "rate_limited", "message": "Too many requests."})
                    return
                self.send_json(202, {"analysis_id": ANALYSIS_ID})

            def do_GET(self):
                if self.path == f"/analysis/{ANALYSIS_ID}/status":
                    index = min(api.status_polls, len(api.statuses) - 1)
                    api.status_polls += 1
                    status = api.statuses[index]
                    self.send_json(200, status_body(status, "done" if status != "running" else "predict"))
                elif self.path == f"/analysis/{ANALYSIS_ID}":
                    self.send_json(200, analysis_body(api.final_status))
                else:
                    self.send_json(404, {"code": "analysis_not_found", "message": "Analysis not found."})

        return Handler


@pytest.fixture
def serve():
    servers = []

    def start(api: FakeApi) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), api.handler())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def run(module, base_url, clock, demo_model_id="demo_xgboost"):
    out = io.StringIO()
    code = module.run(base_url, demo_model_id, sleep=clock.sleep, clock=clock.time, out=out)
    return code, out.getvalue()


def test_polls_every_two_seconds_until_completed_and_exits_zero(serve):
    module = load_script()
    api = FakeApi(["running", "running", "completed"])
    clock = FakeClock()

    code, output = run(module, serve(api), clock)

    assert code == 0
    assert api.status_polls == 3
    assert clock.sleeps == [2.0, 2.0]
    assert api.posted["path"] == "/analysis/run"
    assert api.posted["form"] == {
        "demo_model_id": ["demo_xgboost"],
        "ticker": ["SPY"],
        "start_date": ["2018-01-02"],
        "end_date": ["2024-12-31"],
    }
    assert "status: completed" in output
    assert "validate: done (10 ms)" in output
    assert "report: done (60 ms)" in output
    assert "trades: 3" in output
    assert "regimes_available: True" in output
    assert "explained_output: P(buy)" in output
    assert "report verification: 30/31" in output


def test_partial_or_failed_final_status_exits_non_zero(serve):
    module = load_script()
    for final in ("partial", "failed"):
        code, output = run(module, serve(FakeApi(["running", final])), FakeClock())
        assert code == 1
        assert f"status: {final}" in output


def test_stops_after_400_seconds_and_exits_non_zero(serve):
    module = load_script()
    api = FakeApi(["running"])
    clock = FakeClock()

    code, output = run(module, serve(api), clock)

    assert code == 1
    assert clock.now <= 400.0 + 2.0
    assert api.status_polls == 201
    assert "timed out" in output


def test_rejected_submission_exits_non_zero(serve):
    module = load_script()
    code, output = run(module, serve(FakeApi(["completed"], run_status=429)), FakeClock())
    assert code == 1
    assert "429" in output


def test_demo_model_id_argument_is_sent(serve):
    module = load_script()
    api = FakeApi(["completed"])
    run(module, serve(api), FakeClock(), demo_model_id="demo_mlp")
    assert api.posted["form"]["demo_model_id"] == ["demo_mlp"]


def test_command_line_defaults():
    module = load_script()
    args = module.parse_args(["--base-url", "http://localhost:8000"])
    assert args.base_url == "http://localhost:8000"
    assert args.demo_model_id == "demo_xgboost"
