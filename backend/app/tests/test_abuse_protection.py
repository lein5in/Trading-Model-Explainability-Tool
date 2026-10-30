import io
import json
import os
from datetime import datetime, timedelta, timezone
import pytest
from app.api import submission as submission_module
from app.db.repository import InMemoryRepository
from app.security.client_ip import hash_client_ip
from app.security.rate_limit import SlidingWindowRateLimiter

FORWARDED_IP = "198.51.100.23"
FAKE_DEMO_ENTRY = {
    "id": "demo_tree",
    "name": "Decision tree",
    "file": "demo_tree.joblib",
    "feature_columns": ["rsi_14", "vol_20d"],
}


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def ticker_form(**overrides) -> dict:
    form = {
        "ticker": "SPY",
        "start_date": "2020-01-01",
        "end_date": "2022-01-01",
        "feature_ids": json.dumps(["rsi_14", "vol_20d"]),
    }
    form.update(overrides)
    return form


def model_upload(size: int = 64, name: str = "model.pkl") -> dict:
    return {"model_file": (name, io.BytesIO(b"x" * size), "application/octet-stream")}


def csv_upload(content: str) -> dict:
    return {"csv_file": ("data.csv", io.BytesIO(content.encode("utf-8")), "text/csv")}


def post_run(client, data=None, files=None, headers=None):
    return client.post("/analysis/run", data=data or ticker_form(), files=files or model_upload(), headers=headers)


def test_rate_limiter_blocks_the_next_event_and_resets_after_the_window():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_events=3, window_seconds=60, clock=clock)

    assert [limiter.hit("ip") for _ in range(3)] == [True, True, True]
    assert limiter.hit("ip") is False
    assert limiter.hit("other-ip") is True

    clock.now += 60.5
    assert limiter.hit("ip") is True


def test_rate_limit_blocks_the_n_plus_first_run_and_resets(make_api, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_RUNS", "2")
    client, services = make_api()
    clock = FakeClock()
    services.rate_limiter = SlidingWindowRateLimiter(2, 3600, clock=clock)

    assert post_run(client).status_code == 202
    assert post_run(client).status_code == 202
    blocked = post_run(client)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"
    assert "Retry-After" in blocked.headers

    clock.now += 3601
    assert post_run(client).status_code == 202


def test_default_rate_limit_is_five_per_hour(make_api):
    client, services = make_api()
    assert services.rate_limiter.max_events == 5
    assert services.rate_limiter.window_seconds == 3600
    codes = [post_run(client).status_code for _ in range(6)]
    assert codes == [202, 202, 202, 202, 202, 429]


def test_daily_cap_counts_only_today(make_api, monkeypatch):
    monkeypatch.setenv("DAILY_ANALYSIS_CAP", "2")
    repository = InMemoryRepository()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1, hours=1)).isoformat()
    repository.create_analysis({"status": "completed", "created_at": yesterday})
    client, _ = make_api(repository=repository)

    assert post_run(client).status_code == 202
    assert post_run(client).status_code == 202
    capped = post_run(client)
    assert capped.status_code == 429
    assert capped.json()["code"] == "daily_cap_reached"


def test_date_range_cap(make_api):
    client, _ = make_api()
    response = post_run(client, data=ticker_form(start_date="2010-01-01", end_date="2020-01-02"))
    assert response.status_code == 400
    assert response.json()["code"] == "date_range_too_long"
    assert post_run(client, data=ticker_form(start_date="2010-01-01", end_date="2020-01-01")).status_code == 202


def test_model_file_size_cap(make_api, monkeypatch):
    monkeypatch.setenv("MAX_MODEL_FILE_BYTES", "100")
    client, _ = make_api()
    response = post_run(client, files=model_upload(size=101))
    assert response.status_code == 413
    assert response.json()["code"] == "model_file_too_large"
    assert post_run(client, files=model_upload(size=100)).status_code == 202


def test_default_model_file_cap_is_ten_megabytes(make_api):
    client, _ = make_api()
    response = post_run(client, files=model_upload(size=10 * 1024 * 1024 + 1))
    assert response.status_code == 413
    assert response.json()["code"] == "model_file_too_large"


def test_feature_count_cap(make_api):
    client, _ = make_api()
    too_many = json.dumps([f"feature_{i}" for i in range(31)])
    response = post_run(client, data=ticker_form(feature_ids=too_many))
    assert response.status_code == 400
    assert response.json()["code"] == "too_many_features"


def test_csv_size_cap(make_api, monkeypatch):
    monkeypatch.setenv("MAX_CSV_BYTES", "200")
    client, _ = make_api()
    content = "date,open,high,low,close,volume,f1\n" + "2020-01-01,1,1,1,1,1,0.5\n" * 20
    files = {**model_upload(), **csv_upload(content)}
    response = client.post("/analysis/run", data={}, files=files)
    assert response.status_code == 413
    assert response.json()["code"] == "csv_too_large"


def test_csv_row_cap(make_api, monkeypatch):
    monkeypatch.setenv("MAX_CSV_ROWS", "3")
    client, _ = make_api()
    rows = "".join(f"2020-01-0{day},1,1,1,1,1,0.5\n" for day in range(1, 5))
    files = {**model_upload(), **csv_upload("date,open,high,low,close,volume,f1\n" + rows)}
    response = client.post("/analysis/run", data={}, files=files)
    assert response.status_code == 413
    assert response.json()["code"] == "csv_too_many_rows"


def test_default_csv_caps_are_five_megabytes_and_twenty_thousand_rows():
    from app.config import get_settings

    settings = get_settings()
    assert settings.max_csv_bytes == 5 * 1024 * 1024
    assert settings.max_csv_rows == 20000
    assert settings.max_features == 30
    assert settings.max_date_range_years == 10
    assert settings.daily_analysis_cap == 200
    assert settings.allow_upload is True
    assert settings.trust_proxy is False


def test_allow_upload_false_rejects_upload_and_accepts_demo(make_api, monkeypatch):
    monkeypatch.setenv("ALLOW_UPLOAD", "false")
    monkeypatch.setattr(submission_module, "get_demo_model", lambda demo_id: FAKE_DEMO_ENTRY if demo_id == "demo_tree" else None)
    client, services = make_api()

    rejected = post_run(client)
    assert rejected.status_code == 403
    assert rejected.json()["code"] == "upload_disabled"

    accepted = client.post("/analysis/run", data=ticker_form(demo_model_id="demo_tree"))
    assert accepted.status_code == 202
    row = services.repository.get_analysis(accepted.json()["analysis_id"])
    assert row["model_meta"]["source"] == "demo"
    assert row["params"]["feature_ids"] == FAKE_DEMO_ENTRY["feature_columns"]


def test_temp_dir_is_removed_after_success(make_api):
    seen = {}

    def run_job(job):
        seen["work_dir"] = job.work_dir
        seen["model_existed"] = os.path.exists(job.model_path)

    client, services = make_api(run_job=run_job)
    response = post_run(client)
    services.job_manager.wait(response.json()["analysis_id"], timeout=30)

    assert seen["model_existed"] is True
    assert not os.path.exists(seen["work_dir"])


def test_temp_dir_is_removed_after_failure(make_api):
    seen = {}

    def run_job(job):
        seen["work_dir"] = job.work_dir
        raise RuntimeError("injected failure")

    client, services = make_api(run_job=run_job)
    response = post_run(client)
    services.job_manager.wait(response.json()["analysis_id"], timeout=30)

    assert os.path.isdir(os.path.dirname(seen["work_dir"]))
    assert not os.path.exists(seen["work_dir"])


def test_raw_ip_is_never_stored(make_api, monkeypatch):
    monkeypatch.setenv("TRUST_PROXY", "true")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    client, services = make_api()

    response = post_run(client, headers={"X-Forwarded-For": FORWARDED_IP})
    row = services.repository.get_analysis(response.json()["analysis_id"])

    assert FORWARDED_IP not in json.dumps(row)
    assert row["client_ip_hash"] == hash_client_ip(FORWARDED_IP, "test-salt")


def test_forwarded_header_is_ignored_without_trust_proxy(make_api, monkeypatch):
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    client, services = make_api()

    response = post_run(client, headers={"X-Forwarded-For": FORWARDED_IP})
    row = services.repository.get_analysis(response.json()["analysis_id"])

    assert row["client_ip_hash"] != hash_client_ip(FORWARDED_IP, "test-salt")
    assert row["client_ip_hash"] == hash_client_ip("testclient", "test-salt")


@pytest.mark.parametrize(
    "form,code",
    [
        (ticker_form(ticker="bad ticker!"), "invalid_ticker"),
        (ticker_form(start_date="2020-13-01"), "invalid_date"),
        (ticker_form(start_date="2022-01-01", end_date="2021-01-01"), "invalid_date_range"),
        (ticker_form(feature_ids="not json"), "invalid_features"),
        (ticker_form(fee_bps="-1"), "invalid_cost"),
    ],
)
def test_invalid_inputs_return_a_stable_code(make_api, form, code):
    client, _ = make_api()
    response = post_run(client, data=form)
    assert response.status_code == 400
    assert response.json()["code"] == code


def test_missing_model_and_unsupported_extension(make_api):
    client, _ = make_api()
    missing = client.post("/analysis/run", data=ticker_form())
    assert missing.status_code == 400
    assert missing.json()["code"] == "missing_model"
    wrong = post_run(client, files=model_upload(name="model.exe"))
    assert wrong.json()["code"] == "unsupported_model_file"


def test_stored_row_has_the_expected_shape(make_api):
    client, services = make_api()
    response = post_run(client)
    row = services.repository.get_analysis(response.json()["analysis_id"])
    assert row["status"] == "queued"
    assert row["model_meta"]["source"] == "upload"
    assert row["model_meta"]["filename"] == "model.pkl"
    assert row["model_meta"]["size"] == 64
    assert "user_id" not in row
