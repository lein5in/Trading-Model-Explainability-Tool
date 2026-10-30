import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_DEMO_MODEL_ID = "demo_xgboost"
TICKER = "SPY"
START_DATE = "2018-01-02"
END_DATE = "2024-12-31"
POLL_INTERVAL_SECONDS = 2.0
MAX_WAIT_SECONDS = 400.0
REQUEST_TIMEOUT_SECONDS = 30.0
TERMINAL_STATUSES = ("completed", "partial", "failed")
STAGE_ORDER = ("validate", "predict", "backtest", "regimes", "shap", "report")


class SmokeError(Exception):
    pass


def request_json(method: str, url: str, form: dict | None = None) -> dict:
    data = urllib.parse.urlencode(form).encode("utf-8") if form is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SmokeError(f"{method} {url} returned HTTP {exc.code}: {body}")
    except urllib.error.URLError as exc:
        raise SmokeError(f"{method} {url} failed: {exc.reason}")


def wait_for_completion(base_url: str, analysis_id: str, sleep, clock, out) -> dict | None:
    deadline = clock() + MAX_WAIT_SECONDS
    while True:
        status = request_json("GET", f"{base_url}/analysis/{analysis_id}/status")
        print(f"  ... status={status.get('status')} stage={status.get('stage')}", file=out)
        if status.get("status") in TERMINAL_STATUSES:
            return status
        if clock() + POLL_INTERVAL_SECONDS > deadline:
            return None
        sleep(POLL_INTERVAL_SECONDS)


def print_summary(analysis: dict, out) -> None:
    result = analysis.get("result") or {}
    stages = result.get("stages") or {}
    trades = (result.get("backtest") or {}).get("trades")
    regimes = result.get("regimes") or {}
    shap = result.get("shap") or {}
    verification = (analysis.get("report") or {}).get("verification") or {}
    print(f"status: {analysis.get('status')}", file=out)
    for name in STAGE_ORDER:
        stage = stages.get(name) or {}
        print(f"  {name}: {stage.get('state')} ({stage.get('duration_ms')} ms)", file=out)
    print(f"trades: {len(trades) if trades is not None else None}", file=out)
    print(f"regimes_available: {regimes.get('regimes_available')}", file=out)
    print(f"explained_output: {shap.get('explained_output')}", file=out)
    print(f"report verification: {verification.get('numbers_verified')}/{verification.get('numbers_total')}", file=out)
    if analysis.get("error"):
        print(f"error: {json.dumps(analysis['error'])}", file=out)


def run(base_url: str, demo_model_id: str, sleep=time.sleep, clock=time.monotonic, out=sys.stdout) -> int:
    base = base_url.rstrip("/")
    try:
        submitted = request_json("POST", f"{base}/analysis/run", {
            "demo_model_id": demo_model_id,
            "ticker": TICKER,
            "start_date": START_DATE,
            "end_date": END_DATE,
        })
        analysis_id = submitted["analysis_id"]
        print(f"analysis_id: {analysis_id}", file=out)
        final = wait_for_completion(base, analysis_id, sleep, clock, out)
        if final is None:
            print(f"timed out after {MAX_WAIT_SECONDS:g} seconds", file=out)
            return 1
        analysis = request_json("GET", f"{base}/analysis/{analysis_id}")
    except (SmokeError, KeyError, ValueError) as exc:
        print(f"smoke test failed: {exc}", file=out)
        return 1
    print_summary(analysis, out)
    return 0 if analysis.get("status") == "completed" else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one demo analysis against a running API and print a summary.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--demo-model-id", default=DEFAULT_DEMO_MODEL_ID)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args.base_url, args.demo_model_id)


if __name__ == "__main__":
    sys.exit(main())
