from __future__ import annotations

from fastapi.testclient import TestClient

from app.clients.base import MarketplaceClient
from app.clients.wb import WBClient
from app.config import Settings
from app.main import create_app
from app.schemas import CategoryAttribute, CategoryNode, Marketplace, ProductDetails, ProductSummary


class FakeWBClient(MarketplaceClient):
    async def list_products(self, credentials, *, limit: int = 50):
        return [
            ProductSummary(
                id="1001",
                offer_id="SKU-1001",
                title="Red t-shirt",
                category_id=10,
                category_name="T-shirts",
                price="1999",
                images=["https://example.test/image-1.jpg"],
            )
        ]

    async def get_product_details(self, credentials, product_id: str):
        return ProductDetails(
            id=product_id,
            offer_id="SKU-1001",
            title="Red t-shirt",
            description="Basic cotton t-shirt",
            category_id=10,
            category_name="T-shirts",
            price="1999",
            images=["https://example.test/image-1.jpg"],
            attributes={"Color": ["Red"], "Material": ["Cotton"]},
            dimensions={"height": 10, "width": 20, "depth": 30, "weight": 400},
            sizes=[{"techSize": "L", "wbSize": "48"}],
            brand="Acme",
        )

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [CategoryNode(id=10, name="T-shirts", parent_id=None)]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return []

    async def create_products(self, credentials, items):
        return {"external_task_id": "wb-task"}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed"}


class FakeOzonClient(MarketplaceClient):
    async def list_products(self, credentials, *, limit: int = 50):
        return []

    async def get_product_details(self, credentials, product_id: str):
        raise NotImplementedError

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(
                id=501,
                name="T-shirts",
                parent_id=None,
                raw={
                    "description_category_id": 501,
                    "children": [{"type_id": 601, "type_name": "T-shirt", "disabled": False}],
                },
            ),
            CategoryNode(
                id=502,
                name="Jeans",
                parent_id=None,
                raw={
                    "description_category_id": 502,
                    "children": [{"type_id": 701, "type_name": "Jeans", "disabled": False}],
                },
            ),
        ]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return [
            CategoryAttribute(id=1, name="Color", required=True, dictionary_values=[{"id": 99, "value": "Red"}]),
            CategoryAttribute(id=2, name="Material", required=False),
        ]

    async def create_products(self, credentials, items):
        return {"external_task_id": "ozon-task-1", "raw_response": {"result": {"task_id": "ozon-task-1"}}}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed", "errors": []}


class FakeOzonCategoryClient(FakeOzonClient):
    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(
                id=501,
                name="T-shirts",
                parent_id=None,
                raw={
                    "description_category_id": 501,
                    "children": [
                        {"type_id": 601, "type_name": "T-shirt", "disabled": False},
                        {"type_id": 602, "type_name": "Jumper", "disabled": False},
                    ],
                },
            )
        ]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        raise AssertionError("preview should use get_category_attributes_for_node for Ozon category types")

    async def get_category_attributes_for_node(
        self,
        credentials,
        category: CategoryNode,
        *,
        source_product: ProductDetails | None = None,
        required_only: bool = False,
    ):
        assert category.id == 501
        assert source_product is not None
        category.raw["_resolved_type_id"] = 601
        category.raw["_resolved_type_name"] = "T-shirt"
        return [
            CategoryAttribute(id=1, name="Type", required=True),
            CategoryAttribute(id=2, name="Model name", required=True),
        ]


class FakeOzonStrictBrandClient(FakeOzonClient):
    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return [
            CategoryAttribute(
                id=85,
                name="Brand",
                required=True,
                raw={"dictionary_id": 28732849},
            )
        ]


class FakeOzonFailedStatusClient(FakeOzonClient):
    async def get_import_status(self, credentials, external_task_id: str | None):
        return {
            "status": "failed",
            "errors": [
                {
                    "message": "Brand dictionary value not found",
                    "code": "error_attribute_values_out_of_range",
                }
            ],
        }


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
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonClient())
    return TestClient(app)


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_preview_launch_and_sync_transfer(tmp_path):
    client = build_client(tmp_path)
    headers = auth_headers(client)

    wb_connection = client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    assert wb_connection.status_code == 200

    ozon_connection = client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )
    assert ozon_connection.status_code == 200

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={"source_marketplace": "wb", "target_marketplace": "ozon", "product_ids": ["1001"], "target_category_id": 501},
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is True
    assert preview_data["items"][0]["target_category_id"] == 501
    assert preview_data["items"][0]["missing_required_attributes"] == []
    assert preview_data["items"][0]["payload"]["type_id"] == 601

    launch_response = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={"source_marketplace": "wb", "target_marketplace": "ozon", "product_ids": ["1001"]},
    )
    assert launch_response.status_code == 200
    job = launch_response.json()
    assert job["status"] == "submitted"
    assert job["external_task_id"] == "ozon-task-1"

    jobs_response = client.get("/api/v1/transfers", headers=headers)
    assert jobs_response.status_code == 200
    assert len(jobs_response.json()) == 1

    sync_response = client.post(f"/api/v1/transfers/{job['id']}/sync", headers=headers)
    assert sync_response.status_code == 200
    assert sync_response.json()["status"] == "completed"


def test_preview_uses_ozon_category_type_context(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonCategoryClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["1001"],
            "target_category_id": 501,
        },
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["items"][0]["target_category_id"] == 501
    assert preview_data["items"][0]["payload"]["type_id"] == 601


class FakeWBMissingPriceClient(FakeWBClient):
    async def list_products(self, credentials, *, limit: int = 50):
        items = await super().list_products(credentials, limit=limit)
        return [items[0].model_copy(update={"price": None})]

    async def get_product_details(self, credentials, product_id: str):
        details = await super().get_product_details(credentials, product_id)
        return details.model_copy(update={"price": None})


def test_preview_accepts_manual_price_override(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBMissingPriceClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["1001"],
            "product_overrides": {"1001": {"price": "2499"}},
        },
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is True
    assert preview_data["items"][0]["payload"]["price"] == "2499"
    assert preview_data["items"][0]["payload"]["type_id"] == 601
    assert preview_data["items"][0]["missing_critical_fields"] == []


def test_preview_blocks_unresolved_required_ozon_brand_dictionary(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonStrictBrandClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["1001"],
        },
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is False
    assert "Brand" in preview_data["items"][0]["missing_required_attributes"]


def test_sync_transfer_persists_item_level_error_message(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonFailedStatusClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )

    launch_response = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={"source_marketplace": "wb", "target_marketplace": "ozon", "product_ids": ["1001"]},
    )
    assert launch_response.status_code == 200
    job = launch_response.json()

    sync_response = client.post(f"/api/v1/transfers/{job['id']}/sync", headers=headers)
    assert sync_response.status_code == 200
    sync_data = sync_response.json()
    assert sync_data["status"] == "failed"
    assert sync_data["error_message"] == "Brand dictionary value not found"


def test_wb_price_prefers_seller_prices_api_payload():
    price = WBClient._extract_price(
        card={},
        size={},
        public_detail={},
        seller_price={"sizes": [{"discountedPrice": 3490}]},
    )
    assert price == "3490"
