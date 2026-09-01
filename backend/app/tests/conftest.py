import subprocess
import uuid
import pytest
from supabase import create_client
from app.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY


def _docker_daemon_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


DOCKER_DAEMON_AVAILABLE = _docker_daemon_available()

requires_docker = pytest.mark.skipif(
    not DOCKER_DAEMON_AVAILABLE,
    reason="Docker daemon is not running or not reachable.",
)


def create_test_user_and_get_token() -> str:
    admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    unique_id = uuid.uuid4().hex[:12]
    email = f"pytest_{unique_id}@example.com"
    password = f"Pytest_{unique_id}!"

    admin_client.auth.admin.create_user(
        {"email": email, "password": password, "email_confirm": True}
    )

    signin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    signin_response = signin_client.auth.sign_in_with_password(
        {"email": email, "password": password}
    )

    return signin_response.session.access_token


@pytest.fixture(scope="session")
def auth_headers():
    try:
        access_token = create_test_user_and_get_token()
    except Exception as exc:
        pytest.skip(f"Could not create Supabase test user: {exc}")

    return {"Authorization": f"Bearer {access_token}"}