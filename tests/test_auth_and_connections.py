from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def build_client(tmp_path):
    settings = Settings(
        app_name="test-app",
        secret_key="test-secret",
        database_path=tmp_path / "test.db",
        session_ttl_hours=24,
        wb_base_url="https://wb.invalid",
        ozon_base_url="https://ozon.invalid",
        http_timeout_seconds=1.0,
    )
    app = create_app(settings)
    return TestClient(app)


def test_register_login_and_save_connection(tmp_path):
    client = build_client(tmp_path)

    root_response = client.get("/")
    assert root_response.status_code == 200
    assert "text/html" in root_response.headers["content-type"]

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    assert register_response.status_code == 200
    token = register_response.json()["access_token"]

    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"

    save_connection = client.put(
        "/api/v1/connections/wb",
        headers={"Authorization": f"Bearer {token}"},
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    assert save_connection.status_code == 200
    assert save_connection.json()["masked_fields"]["token"].startswith("wb")

    connections_response = client.get("/api/v1/connections", headers={"Authorization": f"Bearer {token}"})
    assert connections_response.status_code == 200
    connections = {item["marketplace"]: item for item in connections_response.json()}
    assert connections["wb"]["is_configured"] is True
    assert connections["ozon"]["is_configured"] is False

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    assert login_response.status_code == 200
