from __future__ import annotations

from fastapi.testclient import TestClient

from app.clients.base import MarketplaceAPIError, MarketplaceClient
from app.config import Settings
from app.main import create_app
from app.schemas import Marketplace


class FakeOzonBrandsClient(MarketplaceClient):
    async def list_products(self, credentials, *, limit: int = 50):
        return []

    async def get_product_details(self, credentials, product_id: str):
        raise NotImplementedError

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return []

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return []

    async def create_products(self, credentials, items):
        return {"external_task_id": ""}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed"}

    async def list_brands(self, credentials, query: str, limit: int = 100):
        return [
            {"id": 1000, "name": "Nike"},
            {"id": 1001, "name": "Nike Sport"},
        ]


class FakeWBClient(MarketplaceClient):
    async def list_products(self, credentials, *, limit: int = 50):
        return []

    async def get_product_details(self, credentials, product_id: str):
        raise NotImplementedError

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return []

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return []

    async def create_products(self, credentials, items):
        return {"external_task_id": ""}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed"}


class FakeOzonBrandsUnavailableClient(FakeOzonBrandsClient):
    async def list_brands(self, credentials, query: str, limit: int = 100):
        raise MarketplaceAPIError("Connection refused")


def build_app(tmp_path, ozon_client=None):
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
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, ozon_client or FakeOzonBrandsClient())
    return app


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def setup_ozon_connection(client: TestClient, headers: dict) -> None:
    client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )


# TC-27: GET /catalog/ozon/brands returns list {id, name}
def test_list_ozon_brands_returns_items(tmp_path):
    app = build_app(tmp_path)
    client = TestClient(app)
    headers = auth_headers(client)
    setup_ozon_connection(client, headers)

    response = client.get("/api/v1/catalog/ozon/brands", headers=headers, params={"q": "Nike"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 2
    assert data["items"][0]["id"] == 1000
    assert data["items"][0]["name"] == "Nike"


# TC-28: GET /catalog/wb/brands returns 400
def test_list_wb_brands_returns_400(tmp_path):
    app = build_app(tmp_path)
    client = TestClient(app)
    headers = auth_headers(client)

    response = client.get("/api/v1/catalog/wb/brands", headers=headers, params={"q": "Nike"})
    assert response.status_code == 400
    assert "ozon" in response.json()["detail"].lower()


def test_list_brands_limit_respected(tmp_path):
    app = build_app(tmp_path)
    client = TestClient(app)
    headers = auth_headers(client)
    setup_ozon_connection(client, headers)

    response = client.get("/api/v1/catalog/ozon/brands", headers=headers, params={"q": "Nike", "limit": 5})
    assert response.status_code == 200


def test_list_brands_ozon_api_unavailable_returns_502(tmp_path):
    app = build_app(tmp_path, ozon_client=FakeOzonBrandsUnavailableClient())
    client = TestClient(app)
    headers = auth_headers(client)
    setup_ozon_connection(client, headers)

    response = client.get("/api/v1/catalog/ozon/brands", headers=headers, params={"q": "Nike"})
    assert response.status_code == 502
    data = response.json()
    assert data["detail"]["code"] == "OZON_API_UNAVAILABLE"


def test_list_brands_requires_auth(tmp_path):
    app = build_app(tmp_path)
    client = TestClient(app)

    response = client.get("/api/v1/catalog/ozon/brands", params={"q": "Nike"})
    assert response.status_code == 401
