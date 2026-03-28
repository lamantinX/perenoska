"""Integration tests for TransferService.preview() and launch() — TC-18..TC-29, TC-37."""
from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.clients.base import MarketplaceAPIError, MarketplaceClient
from app.config import Settings
from app.main import create_app
from app.schemas import CategoryNode, Marketplace, ProductDetails, ProductSummary


# ---------------------------------------------------------------------------
# Fake clients
# ---------------------------------------------------------------------------

WB_CARD = ProductDetails(
    id="12345678",
    offer_id="ART-001",
    title="Футболка мужская",
    description="Лёгкая хлопковая футболка",
    category_id=50,
    category_name="Футболки",
    price="1500",
    images=["https://basket-01.wbbasket.ru/test/1.webp"],
    attributes={},
    dimensions={"height": 10, "width": 20, "depth": 5, "weight": 300},
    sizes=[{"techSize": "L", "wbSize": "48", "price": "1500", "skus": ["123456789"]}],
    brand="Nike",
    barcode_list=["123456789"],
)

OZON_CARD = ProductDetails(
    id="111222333",
    offer_id="OZON-ART-001",
    title="Футболка мужская Ozon",
    description="Описание для Ozon",
    category_id=17028726,
    category_name="Футболки",
    price="1600",
    images=["https://cdn.ozon.ru/test/1.jpg"],
    attributes={},
    dimensions={"height": 10, "width": 20, "depth": 5, "weight": 300},
    sizes=[{"techSize": "L", "wbSize": "48", "price": "1600", "skus": ["987654321"]}],
    brand="Adidas",
    barcode_list=["987654321"],
)


class FakeWBClient(MarketplaceClient):
    def __init__(self, card: ProductDetails = WB_CARD):
        self._card = card

    async def list_products(self, credentials, *, limit: int = 50):
        return [ProductSummary(
            id=self._card.id,
            offer_id=self._card.offer_id,
            title=self._card.title,
            category_id=self._card.category_id,
            category_name=self._card.category_name,
            price=self._card.price,
            images=self._card.images,
        )]

    async def get_product_details(self, credentials, product_id: str):
        return self._card

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [CategoryNode(id=315, name="Футболки", parent_id=None)]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return []

    async def create_products(self, credentials, items):
        return {"external_task_id": "wb-task-001"}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed"}


class FakeWBConnectionErrorClient(FakeWBClient):
    async def get_product_details(self, credentials, product_id: str):
        raise MarketplaceAPIError("Connection refused to WB")


class FakeOzonClient(MarketplaceClient):
    def __init__(self, brands: list | None = None):
        self._brands = brands if brands is not None else [{"id": 1000, "name": "Nike"}]

    async def list_products(self, credentials, *, limit: int = 50):
        return []

    async def get_product_details(self, credentials, product_id: str):
        return OZON_CARD

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(
                id=17028726,
                name="Футболки",
                parent_id=None,
                raw={
                    "description_category_id": 17028726,
                    "children": [{"type_id": 90648, "type_name": "Футболка", "disabled": False}],
                },
            )
        ]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return []

    async def get_category_attributes_for_node(
        self,
        credentials,
        category: CategoryNode,
        *,
        source_product: ProductDetails | None = None,
        required_only: bool = False,
    ):
        category.raw["_resolved_type_id"] = 90648
        category.raw["_resolved_type_name"] = "Футболка"
        return []

    async def list_brands(self, credentials, query: str, limit: int = 100):
        return self._brands

    async def create_products(self, credentials, items):
        return {"external_task_id": "ozon-task-001"}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed"}


class FakeOzonConnectionErrorClient(FakeOzonClient):
    async def list_categories(self, credentials, *, parent_id: int | None = None):
        raise MarketplaceAPIError("Connection refused to Ozon")

    async def list_brands(self, credentials, query: str, limit: int = 100):
        raise MarketplaceAPIError("Connection refused to Ozon")


class FakeOzonNoBrandsClient(FakeOzonClient):
    """Returns empty brands list — brand not found."""
    async def list_brands(self, credentials, query: str, limit: int = 100):
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_app(tmp_path, wb_client=None, ozon_client=None, llm_mock=None):
    settings = Settings(
        app_name="test-app",
        secret_key="test-secret",
        database_path=tmp_path / "test.db",
        session_ttl_hours=24,
        wb_base_url="https://wb.invalid",
        ozon_base_url="https://ozon.invalid",
        http_timeout_seconds=1.0,
        openrouter_api_key="fake-key-for-tests" if llm_mock else "",
    )
    app = create_app(settings)
    app.state.container.client_factory.register_override(Marketplace.WB, wb_client or FakeWBClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, ozon_client or FakeOzonClient())
    if llm_mock is not None:
        app.state.container.mapping_service.llm_client = llm_mock
    return app


def auth_and_connect(client: TestClient) -> dict[str, str]:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "user@test.com", "password": "strong-pass"},
    )
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-token"},
    )
    client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )
    return headers


def make_llm_mock(category_id: int, confidence: float) -> AsyncMock:
    mock = AsyncMock()
    mock.chat = AsyncMock()
    mock.chat.completions = AsyncMock()
    mock.chat.completions.create = AsyncMock(return_value=AsyncMock(
        choices=[AsyncMock(message=AsyncMock(
            content=f'{{"category_id": {category_id}, "confidence": {confidence}}}'
        ))]
    ))
    return mock


# ---------------------------------------------------------------------------
# TC-18: preview пустой mediaFiles → warnings, ready_to_import=false
# ---------------------------------------------------------------------------

def test_tc18_preview_empty_media_files(tmp_path):
    card_no_images = WB_CARD.model_copy(update={"images": []})
    app = build_app(tmp_path, wb_client=FakeWBClient(card=card_no_images))
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
            "product_overrides": {"12345678": {"category_id": 17028726, "brand_id": 1000}},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ready_to_import"] is False
    item = data["items"][0]
    assert any("изображен" in w.lower() for w in item["warnings"])


# ---------------------------------------------------------------------------
# TC-19: preview бренд не найден → brand_id_requires_manual=true
# ---------------------------------------------------------------------------

def test_tc19_preview_brand_not_found(tmp_path):
    llm = make_llm_mock(17028726, 0.9)
    app = build_app(tmp_path, ozon_client=FakeOzonNoBrandsClient(), llm_mock=llm)
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    item = data["items"][0]
    assert item["brand_id_requires_manual"] is True
    assert data["ready_to_import"] is False


# ---------------------------------------------------------------------------
# TC-20: preview LLM low confidence → category_requires_manual=true
# ---------------------------------------------------------------------------

def test_tc20_preview_llm_low_confidence(tmp_path):
    llm = make_llm_mock(17028726, 0.4)
    app = build_app(tmp_path, llm_mock=llm)
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    item = data["items"][0]
    assert item["category_requires_manual"] is True
    assert item["category_confidence"] == 0.4
    assert data["ready_to_import"] is False


# ---------------------------------------------------------------------------
# TC-21: preview с category_id override → LLM не вызывается
# ---------------------------------------------------------------------------

def test_tc21_preview_category_override_skips_llm(tmp_path):
    llm = AsyncMock()
    llm.chat = AsyncMock()
    llm.chat.completions = AsyncMock()
    llm.chat.completions.create = AsyncMock()

    app = build_app(tmp_path, llm_mock=llm)
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
            "product_overrides": {"12345678": {"category_id": 17028726}},
        },
    )
    assert r.status_code == 200
    # LLM should NOT be called when category_id override is provided
    llm.chat.completions.create.assert_not_called()
    item = r.json()["items"][0]
    assert item["category_requires_manual"] is False
    assert item["target_category_id"] == 17028726


# ---------------------------------------------------------------------------
# TC-22: preview с brand_id override → brand_id_requires_manual=false
# ---------------------------------------------------------------------------

def test_tc22_preview_brand_id_override(tmp_path):
    llm = make_llm_mock(17028726, 0.9)
    app = build_app(tmp_path, ozon_client=FakeOzonNoBrandsClient(), llm_mock=llm)
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
            "product_overrides": {"12345678": {"brand_id": 9999}},
        },
    )
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["brand_id_requires_manual"] is False
    assert item["brand_id_suggestion"] == 9999


# ---------------------------------------------------------------------------
# TC-23: launch без category override → 400
# ---------------------------------------------------------------------------

def test_tc23_launch_blocks_without_category_override(tmp_path):
    llm = make_llm_mock(17028726, 0.3)  # low confidence → category_requires_manual=True
    app = build_app(tmp_path, llm_mock=llm)
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert r.status_code == 400
    assert "категория" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TC-24: launch без brand_id override → 400
# ---------------------------------------------------------------------------

def test_tc24_launch_blocks_without_brand_override(tmp_path):
    llm = make_llm_mock(17028726, 0.9)  # high confidence → category ok
    app = build_app(tmp_path, ozon_client=FakeOzonNoBrandsClient(), llm_mock=llm)
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert r.status_code == 400
    assert "бренд" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TC-25: launch WB-Ozon → annotation/offer_id/brand_id в payload
# ---------------------------------------------------------------------------

def test_tc25_launch_wb_ozon_payload_fields(tmp_path):
    llm = make_llm_mock(17028726, 0.9)
    app = build_app(tmp_path, llm_mock=llm)
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert r.status_code == 200
    job = r.json()
    assert job["status"] == "submitted"
    # Check payload contains expected fields in preview items
    preview_items = job["payload"]["items"]
    assert len(preview_items) == 1
    item_payload = preview_items[0]["payload"]
    assert "annotation" in item_payload
    assert "offer_id" in item_payload
    assert "brand_id" in item_payload
    assert "is_visible" not in item_payload
    assert "status" not in item_payload


# ---------------------------------------------------------------------------
# TC-26: launch Ozon-WB → description из annotation, brand строкой
# ---------------------------------------------------------------------------

def test_tc26_launch_ozon_wb_payload_fields(tmp_path):
    app = build_app(tmp_path)
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_marketplace": "ozon",
            "target_marketplace": "wb",
            "product_ids": ["111222333"],
            "product_overrides": {"111222333": {"category_id": 315}},
        },
    )
    assert r.status_code == 200
    job = r.json()
    assert job["status"] == "submitted"
    preview_items = job["payload"]["items"]
    item_payload = preview_items[0]["payload"]
    # WB payload should have 'variants' with description field
    assert "variants" in item_payload
    variant = item_payload["variants"][0]
    assert "description" in variant
    # brand should be a string, not a dict
    assert isinstance(variant.get("brand"), str)
    # No status field
    assert "status" not in item_payload


# ---------------------------------------------------------------------------
# TC-29: preview без auth → 401
# ---------------------------------------------------------------------------

def test_tc29_preview_requires_auth(tmp_path):
    app = build_app(tmp_path)
    client = TestClient(app)

    r = client.post(
        "/api/v1/transfers/preview",
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# TC-37: list_categories вызывается ровно 1 раз при preview
# ---------------------------------------------------------------------------

def test_tc37_list_categories_called_once(tmp_path, mocker):
    ozon_client = FakeOzonClient()
    app = build_app(tmp_path, ozon_client=ozon_client)
    spy = mocker.spy(ozon_client, "list_categories")
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
            "product_overrides": {"12345678": {"category_id": 17028726, "brand_id": 1000}},
        },
    )
    assert r.status_code == 200
    assert spy.call_count == 1, f"list_categories should be called once, got {spy.call_count}"


# ---------------------------------------------------------------------------
# TC-36: 502 on WB API error / Ozon API error
# ---------------------------------------------------------------------------

def test_tc36_wb_api_unavailable_returns_502(tmp_path):
    app = build_app(tmp_path, wb_client=FakeWBConnectionErrorClient())
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "WB_API_UNAVAILABLE"


def test_tc36_ozon_api_unavailable_returns_502(tmp_path):
    app = build_app(tmp_path, ozon_client=FakeOzonConnectionErrorClient())
    client = TestClient(app)
    headers = auth_and_connect(client)

    r = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["12345678"],
        },
    )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "OZON_API_UNAVAILABLE"
