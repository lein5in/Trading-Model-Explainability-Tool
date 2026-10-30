import os
import subprocess
import pytest
from fastapi.testclient import TestClient

DOCKER_SKIP_REASON = "requires_docker: the Docker daemon is not running or not reachable (docker info failed)."

ISOLATED_ENV_VARS = (
    "CORS_ORIGINS",
    "ALLOW_UPLOAD",
    "TRUST_PROXY",
    "IP_HASH_SALT",
    "RATE_LIMIT_RUNS",
    "RATE_LIMIT_WINDOW_SECONDS",
    "DAILY_ANALYSIS_CAP",
    "MAX_DATE_RANGE_YEARS",
    "MAX_MODEL_FILE_BYTES",
    "MAX_FEATURES",
    "MAX_CSV_BYTES",
    "MAX_CSV_ROWS",
    "SANDBOX_OUTPUT_CAP_BYTES",
    "SHAP_SAMPLE_SIZE",
    "SHAP_MIN_ROWS_PER_REGIME",
    "SHAP_LOW_SAMPLE_THRESHOLD",
    "SHAP_MAX_TRADE_ROWS",
    "SHAP_BACKGROUND_ROWS",
    "SHAP_KERNEL_NSAMPLES",
    "SHAP_KERNEL_BACKGROUND_SIZE",
    "JOB_TIMEOUT_SECONDS",
    "MAX_CONCURRENT_JOBS",
    "CONTINUOUS_SIGNAL_DEAD_ZONE",
    "PREFLIGHT_ROWS",
    "REPORT_MAX_TOKENS",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
)


def _docker_daemon_available() -> bool:
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=15)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


DOCKER_DAEMON_AVAILABLE = _docker_daemon_available()

requires_docker = pytest.mark.requires_docker


def pytest_configure(config):
    os.environ["ENVIRONMENT"] = "test"
    os.environ["SANDBOX_DOCKER_RUNTIME"] = "runc"


def pytest_collection_modifyitems(config, items):
    if DOCKER_DAEMON_AVAILABLE:
        return
    skip_marker = pytest.mark.skip(reason=DOCKER_SKIP_REASON)
    for item in items:
        if "requires_docker" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in ISOLATED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("SANDBOX_DOCKER_RUNTIME", "runc")


@pytest.fixture
def make_api():
    from app.db.repository import InMemoryRepository
    from app.main import build_services, create_app

    created = []

    def factory(run_job="noop", repository=None, **service_overrides):
        repo = repository if repository is not None else InMemoryRepository()
        job = (lambda analysis_job: None) if run_job == "noop" else run_job
        services = build_services(repository=repo, run_job=job, **service_overrides)
        client = TestClient(create_app(services))
        created.append(services)
        return client, services

    yield factory
    for services in created:
        services.job_manager.shutdown()
