"""E2E system tests TC-30..TC-36.

Tests cover end-to-end scenarios: full preview+launch cycle WB↔Ozon,
two-step override scenarios, API error handling.
All tests use isolated app: create_app(settings) with tmp_path,
FakeWBClient/FakeOzonClient via register_override, AsyncMock LLM via mocker.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.clients.base import MarketplaceAPIError, MarketplaceClient
from app.config import Settings
from app.main import create_app
from app.schemas import CategoryAttribute, CategoryNode, Marketplace, ProductDetails, ProductSummary


# ---------------------------------------------------------------------------
# Fake clients
# ---------------------------------------------------------------------------


class FakeWBClient(MarketplaceClient):
    """WB client stub that returns a single WB product card."""

    async def list_products(self, credentials, *, limit: int = 50):
        return [
            ProductSummary(
                id="12345678",
                offer_id="ART-001",
                title="Футболка мужская",
                category_id=315,
                category_name="Футболки",
                price="1500",
                images=["https://basket-01.wbbasket.ru/test/1.webp"],
            )
        ]

    async def get_product_details(self, credentials, product_id: str):
        return ProductDetails(
            id=product_id,
            offer_id="ART-001",
            title="Футболка мужская",
            description="Лёгкая хлопковая футболка",
            category_id=315,
            category_name="Футболки",
            price="1500",
            images=["https://basket-01.wbbasket.ru/test/1.webp"],
            attributes={"Цвет": ["Белый"], "Состав": ["Хлопок 100%"]},
            dimensions={"height": 10, "width": 20, "depth": 30, "weight": 400},
            sizes=[{"techSize": "L", "wbSize": "48"}],
            brand="Nike",
        )

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [CategoryNode(id=315, name="Футболки", parent_id=None)]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return []

    async def create_products(self, credentials, items):
        # Capture payload for assertions
        FakeWBClient._last_items = items
        return {"external_task_id": "wb-task-1"}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed"}


class FakeOzonClient(MarketplaceClient):
    """Ozon client stub that returns T-shirts category and 'Nike' brand."""

    async def list_products(self, credentials, *, limit: int = 50):
        return []

    async def get_product_details(self, credentials, product_id: str):
        return ProductDetails(
            id=product_id,
            offer_id="ART-001",
            title="Футболка мужская Ozon",
            description="",
            category_id=17028727,
            category_name="Футболки",
            price="1500",
            images=["https://cdn.ozon.ru/test/1.jpg"],
            attributes={"Бренд": ["Nike"]},
            dimensions={"height": 100, "width": 200, "depth": 300, "weight": 400},
            sizes=[],
            brand="Nike",
            # annotation stored as description field in ProductDetails
        )

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(
                id=17028727,
                name="Футболки",
                parent_id=None,
                raw={
                    "description_category_id": 17028727,
                    "children": [{"type_id": 94765, "type_name": "Футболка", "disabled": False}],
                },
            )
        ]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return [
            CategoryAttribute(id=1, name="Цвет", required=False),
        ]

    async def get_category_attributes_for_node(
        self,
        credentials,
        category: CategoryNode,
        *,
        source_product=None,
        required_only: bool = False,
    ):
        category.raw["_resolved_type_id"] = 94765
        category.raw["_resolved_type_name"] = "Футболка"
        return [
            CategoryAttribute(id=1, name="Цвет", required=False),
        ]

    async def list_brands(self, credentials, query: str, limit: int = 100):
        # Exact match for "Nike"
        return [{"id": 1000, "name": "Nike"}, {"id": 1001, "name": "Adidas"}]

    async def create_products(self, credentials, items):
        # Capture payload for assertions
        FakeOzonClient._last_items = items
        return {"external_task_id": "ozon-task-1", "raw_response": {"result": {"task_id": "ozon-task-1"}}}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed", "errors": []}


class FakeOzonNoBrandClient(FakeOzonClient):
    """Ozon client that returns no brands."""

    async def list_brands(self, credentials, query: str, limit: int = 100):
        return []


class FakeWBNoImagesClient(FakeWBClient):
    """WB client that returns a product with empty images."""

    async def get_product_details(self, credentials, product_id: str):
        details = await super().get_product_details(credentials, product_id)
        return details.model_copy(update={"images": []})


class FakeWBConnectionErrorClient(FakeWBClient):
    """WB client that raises ConnectionError on get_product_details."""

    async def get_product_details(self, credentials, product_id: str):
        raise MarketplaceAPIError("WB API unavailable")


class FakeOzonConnectionErrorClient(FakeOzonClient):
    """Ozon client that raises ConnectionError on list_categories."""

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        raise MarketplaceAPIError("Ozon API unavailable")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_app(tmp_path, *, wb_client=None, ozon_client=None, openrouter_api_key: str = "fake-key"):
    """Create isolated test app with overridden clients."""
    settings = Settings(
        app_name="test-e2e",
        secret_key="test-secret",
        database_path=tmp_path / "test.db",
        session_ttl_hours=24,
        wb_base_url="https://wb.invalid",
        ozon_base_url="https://ozon.invalid",
        http_timeout_seconds=1.0,
        openrouter_api_key=openrouter_api_key,
        llm_model="mistralai/mistral-7b-instruct:free",
    )
    app = create_app(settings)
    app.state.container.client_factory.register_override(Marketplace.WB, wb_client or FakeWBClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, ozon_client or FakeOzonClient())
    return app


def register_and_login(client: TestClient) -> dict[str, str]:
    """Register user, login, return auth headers."""
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "e2e@example.com", "password": "strong-password"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def setup_connections(client: TestClient, headers: dict) -> None:
    """Create WB and Ozon marketplace connections."""
    resp = client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    assert resp.status_code == 200

    resp = client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# TC-30: e2e preview WB→Ozon, LLM confidence >= 0.7, brand found → ready_to_import=true
# ---------------------------------------------------------------------------


def test_tc30_e2e_preview_wb_ozon_happy_path(tmp_path, mocker):
    """TC-30: Full preview cycle WB→Ozon with high LLM confidence and brand found."""
    app = build_app(tmp_path)
    # Patch auto_match_category_llm to return high confidence
    mocker.patch.object(
        app.state.container.mapping_service,
        "auto_match_category_llm",
        new=AsyncMock(return_value=({"id": 17028727, "name": "Футболки"}, 0.92)),
    )
    client = TestClient(app)
    headers = register_and_login(client)
    setup_connections(client, headers)

    resp = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready_to_import"] is True
    item = data["items"][0]
    assert item["category_requires_manual"] is False
    assert item["brand_id_requires_manual"] is False
    assert item["brand_id_suggestion"] == 1000
    assert item["category_confidence"] == pytest.approx(0.92)


# ---------------------------------------------------------------------------
# TC-31: e2e launch WB→Ozon — payload contains annotation/name/offer_id/brand_id/images; no is_visible/status
# ---------------------------------------------------------------------------


def test_tc31_e2e_launch_wb_ozon_payload_fields(tmp_path, mocker):
    """TC-31: Full launch cycle WB→Ozon — verify Ozon payload fields."""
    FakeOzonClient._last_items = None
    app = build_app(tmp_path)
    mocker.patch.object(
        app.state.container.mapping_service,
        "auto_match_category_llm",
        new=AsyncMock(return_value=({"id": 17028727, "name": "Футболки"}, 0.92)),
    )
    client = TestClient(app)
    headers = register_and_login(client)
    setup_connections(client, headers)

    # Launch transfer with overrides to ensure ready_to_import=true
    resp = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] == "submitted"

    # Verify payload passed to Ozon client
    items = FakeOzonClient._last_items
    assert items is not None
    assert len(items) == 1
    payload = items[0]

    assert "annotation" in payload
    assert "name" in payload
    assert "offer_id" in payload
    assert "brand_id" in payload
    assert "images" in payload
    assert payload["brand_id"] == 1000
    assert payload["annotation"] == "Лёгкая хлопковая футболка"
    assert payload["name"] == "Футболка мужская"
    assert payload["offer_id"] == "ART-001"
    assert len(payload["images"]) > 0

    # No is_visible or status fields
    assert "is_visible" not in payload
    assert "status" not in payload


# ---------------------------------------------------------------------------
# TC-32: Two-step scenario — no brand → override brand_id → ready_to_import=true
# ---------------------------------------------------------------------------


def test_tc32_e2e_brand_not_found_then_override(tmp_path, mocker):
    """TC-32: First preview returns brand_id_requires_manual=true; second preview with brand_id override → ready."""
    app = build_app(tmp_path, ozon_client=FakeOzonNoBrandClient())
    mocker.patch.object(
        app.state.container.mapping_service,
        "auto_match_category_llm",
        new=AsyncMock(return_value=({"id": 17028727, "name": "Футболки"}, 0.92)),
    )
    client = TestClient(app)
    headers = register_and_login(client)
    setup_connections(client, headers)

    # Step 1: preview without override → brand not found
    resp1 = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["ready_to_import"] is False
    item1 = data1["items"][0]
    assert item1["brand_id_requires_manual"] is True

    # Step 2: preview with brand_id override
    resp2 = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
            "product_overrides": {"12345678": {"brand_id": 123}},
        },
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["ready_to_import"] is True
    item2 = data2["items"][0]
    assert item2["brand_id_requires_manual"] is False


# ---------------------------------------------------------------------------
# TC-33: Two-step scenario — LLM low confidence → override category_id → ready_to_import=true
# ---------------------------------------------------------------------------


def test_tc33_e2e_low_confidence_then_category_override(tmp_path, mocker):
    """TC-33: First preview with LLM confidence < 0.7 → category_requires_manual=true; then override → ready."""
    app = build_app(tmp_path)
    low_confidence_mock = AsyncMock(return_value=({"id": 17028727, "name": "Футболки"}, 0.45))
    mocker.patch.object(
        app.state.container.mapping_service,
        "auto_match_category_llm",
        new=low_confidence_mock,
    )
    client = TestClient(app)
    headers = register_and_login(client)
    setup_connections(client, headers)

    # Step 1: preview without override → low confidence
    resp1 = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["ready_to_import"] is False
    item1 = data1["items"][0]
    assert item1["category_requires_manual"] is True
    assert item1["category_confidence"] == pytest.approx(0.45)

    # Step 2: preview with category_id override → skip LLM
    resp2 = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
            "product_overrides": {"12345678": {"category_id": 17028727}},
        },
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    item2 = data2["items"][0]
    assert item2["category_requires_manual"] is False


# ---------------------------------------------------------------------------
# TC-34: e2e launch Ozon→WB — payload contains description/title/vendor_code/brand string/images/subjectID
# ---------------------------------------------------------------------------


class FakeOzonSourceClient(FakeOzonClient):
    """Ozon client stub for source (Ozon→WB direction)."""

    async def get_product_details(self, credentials, product_id: str):
        return ProductDetails(
            id=product_id,
            offer_id="ART-001",
            title="Футболка мужская Ozon",
            description="Описание товара из Ozon",
            category_id=17028727,
            category_name="Футболки",
            price="1500",
            images=["https://cdn.ozon.ru/test/1.jpg"],
            attributes={"Бренд": ["Nike"]},
            dimensions={"height": 100, "width": 200, "depth": 300, "weight": 400},
            sizes=[],
            barcode_list=["4607086564781"],
            brand="Nike",
        )

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(
                id=17028727,
                name="Футболки",
                parent_id=None,
                raw={"description_category_id": 17028727},
            )
        ]


class FakeWBTargetClient(FakeWBClient):
    """WB client stub for target in Ozon→WB direction."""

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [CategoryNode(id=315, name="Футболки", parent_id=None)]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return []

    async def get_category_attributes_for_node(
        self,
        credentials,
        category,
        *,
        source_product=None,
        required_only: bool = False,
    ):
        return []

    async def create_products(self, credentials, items):
        FakeWBTargetClient._last_items = items
        return {"external_task_id": "wb-task-1"}


def test_tc34_e2e_launch_ozon_wb_payload_fields(tmp_path, mocker):
    """TC-34: Full launch cycle Ozon→WB — verify WB payload fields."""
    FakeWBTargetClient._last_items = None
    app = build_app(tmp_path, wb_client=FakeWBTargetClient(), ozon_client=FakeOzonSourceClient())
    mocker.patch.object(
        app.state.container.mapping_service,
        "auto_match_category_llm",
        new=AsyncMock(return_value=({"id": 315, "name": "Футболки"}, 0.88)),
    )
    client = TestClient(app)
    headers = register_and_login(client)
    setup_connections(client, headers)

    resp = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_marketplace": "ozon",
            "target_marketplace": "wb",
            "product_ids": ["ART-001"],
        },
    )
    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] == "submitted"

    items = FakeWBTargetClient._last_items
    assert items is not None
    assert len(items) == 1
    payload = items[0]

    # WB payload is {"subjectID": ..., "variants": [...]}
    assert "subjectID" in payload
    assert "variants" in payload
    variant = payload["variants"][0]

    assert "description" in variant
    assert "title" in variant
    assert "vendorCode" in variant
    assert "brand" in variant
    assert isinstance(variant["brand"], str)

    # description from annotation (Ozon product description)
    assert variant["description"] == "Описание товара из Ozon"
    assert variant["title"] == "Футболка мужская Ozon"
    assert variant["vendorCode"] == "ART-001"
    assert variant["brand"] == "Nike"

    # No status publication field
    assert "status" not in payload
    assert "is_visible" not in payload


# ---------------------------------------------------------------------------
# TC-35: preview WB→Ozon with empty mediaFiles → warnings + ready_to_import=false
# ---------------------------------------------------------------------------


def test_tc35_e2e_preview_empty_media_files(tmp_path, mocker):
    """TC-35: Preview WB→Ozon with empty mediaFiles → warnings and ready_to_import=false."""
    app = build_app(tmp_path, wb_client=FakeWBNoImagesClient())
    mocker.patch.object(
        app.state.container.mapping_service,
        "auto_match_category_llm",
        new=AsyncMock(return_value=({"id": 17028727, "name": "Футболки"}, 0.92)),
    )
    client = TestClient(app)
    headers = register_and_login(client)
    setup_connections(client, headers)

    resp = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready_to_import"] is False
    item = data["items"][0]
    # warnings should mention missing images
    assert len(item["warnings"]) > 0
    assert any("изображен" in w.lower() or "фото" in w.lower() or "медиа" in w.lower() for w in item["warnings"])


# ---------------------------------------------------------------------------
# TC-36: API unavailable → 502 WB_API_UNAVAILABLE / OZON_API_UNAVAILABLE
# ---------------------------------------------------------------------------


def test_tc36_e2e_wb_api_unavailable(tmp_path, mocker):
    """TC-36a: WB ConnectionError → 502 with WB_API_UNAVAILABLE code."""
    app = build_app(tmp_path, wb_client=FakeWBConnectionErrorClient())
    mocker.patch.object(
        app.state.container.mapping_service,
        "auto_match_category_llm",
        new=AsyncMock(return_value=({"id": 17028727, "name": "Футболки"}, 0.92)),
    )
    client = TestClient(app)
    headers = register_and_login(client)
    setup_connections(client, headers)

    resp = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["code"] == "WB_API_UNAVAILABLE"


def test_tc36_e2e_ozon_api_unavailable(tmp_path, mocker):
    """TC-36b: Ozon ConnectionError → 502 with OZON_API_UNAVAILABLE code."""
    app = build_app(tmp_path, ozon_client=FakeOzonConnectionErrorClient())
    mocker.patch.object(
        app.state.container.mapping_service,
        "auto_match_category_llm",
        new=AsyncMock(return_value=({"id": 17028727, "name": "Футболки"}, 0.92)),
    )
    client = TestClient(app)
    headers = register_and_login(client)
    setup_connections(client, headers)

    resp = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["code"] == "OZON_API_UNAVAILABLE"
