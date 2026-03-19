from __future__ import annotations

from fastapi.testclient import TestClient

from app.clients.base import MarketplaceClient
from app.config import Settings
from app.main import create_app
from app.schemas import CategoryAttribute, CategoryNode, Marketplace, ProductDetails, ProductSummary


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


class ProbeCatalogClient(MarketplaceClient):
    def __init__(self) -> None:
        self.seen_limits: list[int] = []

    async def list_products(self, credentials, *, limit: int = 50):
        self.seen_limits.append(limit)
        return [
            ProductSummary(
                id=str(index),
                offer_id=f"SKU-{index}",
                title=f"Product {index}",
            )
            for index in range(1, limit + 1)
        ]

    async def get_product_details(self, credentials, product_id: str):
        raise NotImplementedError

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [CategoryNode(id=1, name="Category", parent_id=parent_id)]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return [CategoryAttribute(id=1, name="Name", required=True)]

    async def create_products(self, credentials, items):
        raise NotImplementedError

    async def get_import_status(self, credentials, external_task_id: str | None):
        raise NotImplementedError


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
    assert connections["yandex_market"]["is_configured"] is False

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    assert login_response.status_code == 200


def test_catalog_products_accepts_limit_above_100(tmp_path):
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
    probe = ProbeCatalogClient()
    app.state.container.client_factory.register_override(Marketplace.WB, probe)
    client = TestClient(app)

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    token = register_response.json()["access_token"]

    client.put(
        "/api/v1/connections/wb",
        headers={"Authorization": f"Bearer {token}"},
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )

    response = client.get(
        "/api/v1/catalog/products?marketplace=wb&limit=250",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 250
    assert probe.seen_limits == [250]


def test_save_and_list_yandex_market_connection(tmp_path):
    client = build_client(tmp_path)

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    token = register_response.json()["access_token"]

    save_response = client.put(
        "/api/v1/connections/yandex_market",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "marketplace": "yandex_market",
            "token": "ym-secret-token",
            "business_id": 321,
            "campaign_id": 654,
        },
    )

    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["marketplace"] == "yandex_market"
    assert payload["is_configured"] is True
    assert payload["masked_fields"]["token"].startswith("ym")
    assert payload["masked_fields"]["business_id"] == "***"
    assert payload["masked_fields"]["campaign_id"] == "***"

    connections_response = client.get("/api/v1/connections", headers={"Authorization": f"Bearer {token}"})
    assert connections_response.status_code == 200
    connections = {item["marketplace"]: item for item in connections_response.json()}
    assert connections["wb"]["is_configured"] is False
    assert connections["ozon"]["is_configured"] is False
    assert connections["yandex_market"]["is_configured"] is True
    assert connections["yandex_market"]["masked_fields"]["business_id"] == "***"
    assert connections["yandex_market"]["masked_fields"]["campaign_id"] == "***"
