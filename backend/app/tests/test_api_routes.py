from app.main import app


class FailingRepository:
    def ping(self):
        raise RuntimeError("database down")


def test_health_endpoint(make_api):
    client, _ = make_api()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_queries_the_repository(make_api):
    client, _ = make_api()
    assert client.get("/health/db").json() == {"status": "ok", "database": "reachable"}


def test_health_db_reports_an_unreachable_database(make_api):
    client, _ = make_api(repository=FailingRepository())
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json()["code"] == "database_unavailable"


def test_unknown_analysis_returns_404(make_api):
    client, _ = make_api()
    response = client.get("/analysis/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["code"] == "analysis_not_found"


def test_no_auth_or_model_registry_routes_remain():
    paths = {route.path for route in app.routes}
    assert not any(path.startswith("/auth") or path.startswith("/models") for path in paths)


def test_cors_origins_come_from_configuration(make_api, monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://tme.example.org, http://localhost:5173")
    client, _ = make_api()
    allowed = client.options(
        "/health",
        headers={"Origin": "https://tme.example.org", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "https://tme.example.org"
    refused = client.options(
        "/health",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in refused.headers
