import io
import pickle
import pytest
import pandas as pd
from fastapi.testclient import TestClient
from sklearn.tree import DecisionTreeClassifier
from app.main import app
from app.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
from app.tests.conftest import requires_docker

requires_supabase = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY,
    reason="SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured.",
)

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@requires_supabase
def test_health_db_endpoint():
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json()["status"] == "connected"


@requires_supabase
def test_upload_model_without_auth_is_rejected():
    response = client.post(
        "/models/upload",
        data={
            "name": "unauthorized_model",
            "signal_type": "discrete",
            "expected_columns": "open,close",
        },
        files={"file": ("unauthorized_model.pkl", io.BytesIO(b"fake"), "application/octet-stream")},
    )
    assert response.status_code == 401


@requires_supabase
def test_upload_model_endpoint_persists_to_supabase(auth_headers):
    X_train = pd.DataFrame({
        "open": [100.0, 100.0, 50.0, 80.0],
        "close": [105.0, 95.0, 50.0, 85.0],
    })
    y_train = [1, -1, -1, 1]

    model = DecisionTreeClassifier(max_depth=2, random_state=0)
    model.fit(X_train, y_train)
    model_bytes = pickle.dumps(model)

    response = client.post(
        "/models/upload",
        data={
            "name": "smoke_test_model",
            "signal_type": "discrete",
            "expected_columns": "open,close",
        },
        files={"file": ("smoke_test_model.pkl", io.BytesIO(model_bytes), "application/octet-stream")},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "smoke_test_model"
    assert body["status"] == "uploaded_unvalidated"
    assert "id" in body


@requires_supabase
def test_get_analysis_returns_404_for_unknown_id(auth_headers):
    response = client.get(
        "/analysis/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


@requires_supabase
@requires_docker
def test_run_analysis_end_to_end_and_get_analysis_after_restart_semantics(auth_headers):
    X_train = pd.DataFrame({
        "open": [100.0, 100.0, 50.0, 80.0, 90.0, 60.0],
        "close": [105.0, 95.0, 50.0, 85.0, 92.0, 55.0],
    })
    y_train = [1, -1, -1, 1, 1, -1]

    model = DecisionTreeClassifier(max_depth=2, random_state=0)
    model.fit(X_train, y_train)
    model_bytes = pickle.dumps(model)

    upload_response = client.post(
        "/models/upload",
        data={
            "name": "smoke_test_e2e_model",
            "signal_type": "discrete",
            "expected_columns": "open,close",
        },
        files={"file": ("smoke_test_e2e_model.pkl", io.BytesIO(model_bytes), "application/octet-stream")},
        headers=auth_headers,
    )
    assert upload_response.status_code == 200
    model_id = upload_response.json()["id"]

    run_response = client.post(
        "/analysis/run",
        json={
            "model_id": model_id,
            "ticker": "AAPL",
            "start": "2024-01-01",
            "end": "2024-06-01",
            "signal_type": "discrete",
            "feature_columns": ["open", "close"],
        },
        headers=auth_headers,
    )
    assert run_response.status_code == 200
    analysis_id = run_response.json()["analysis_id"]

    get_response = client.get(f"/analysis/{analysis_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["analysis_id"] == analysis_id
    assert get_response.json()["ohlcv"] is not None
    assert get_response.json()["predictions"] is not None


@requires_supabase
@requires_docker
def test_analysis_isolated_between_different_users(auth_headers):
    from app.tests.conftest import create_test_user_and_get_token

    other_access_token = create_test_user_and_get_token()
    other_headers = {"Authorization": f"Bearer {other_access_token}"}

    X_train = pd.DataFrame({
        "open": [100.0, 100.0, 50.0, 80.0],
        "close": [105.0, 95.0, 50.0, 85.0],
    })
    y_train = [1, -1, -1, 1]
    model = DecisionTreeClassifier(max_depth=2, random_state=0)
    model.fit(X_train, y_train)
    model_bytes = pickle.dumps(model)

    upload_response = client.post(
        "/models/upload",
        data={
            "name": "isolation_test_model",
            "signal_type": "discrete",
            "expected_columns": "open,close",
        },
        files={"file": ("isolation_test_model.pkl", io.BytesIO(model_bytes), "application/octet-stream")},
        headers=auth_headers,
    )
    model_id = upload_response.json()["id"]

    cross_user_response = client.post(
        "/analysis/run",
        json={
            "model_id": model_id,
            "ticker": "AAPL",
            "start": "2024-01-01",
            "end": "2024-06-01",
            "signal_type": "discrete",
            "feature_columns": ["open", "close"],
        },
        headers=other_headers,
    )
    assert cross_user_response.status_code == 404