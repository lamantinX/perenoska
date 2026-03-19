from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.clients.yandex_market import YandexMarketClient
from app.config import Settings
from app.main import create_app
from app.schemas import Marketplace, ProductDetails


class StubYandexMarketClient(YandexMarketClient):
    def __init__(self) -> None:
        super().__init__("https://market.invalid", 1.0)
        self.calls: list[tuple[str, str, dict]] = []

    async def _request(self, method: str, path: str, credentials: dict, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/v2/campaigns/654/offer-mapping-entries.json":
            payload = kwargs["json"]
            if payload.get("offerIds") == ["SKU-1"]:
                return {
                    "result": {
                        "offerMappingEntries": [
                            {
                                "offer": {
                                    "shopSku": "SKU-1",
                                    "name": "Blue mug",
                                    "description": "Large ceramic mug",
                                    "pictures": ["https://example.test/mug.jpg"],
                                    "price": 990,
                                    "stock": 7,
                                    "vendor": "Acme",
                                    "barcodes": ["460000000001"],
                                    "parameters": [{"name": "Color", "values": ["Blue"]}],
                                },
                                "mapping": {"marketCategory": {"id": 77, "name": "Mugs"}},
                            }
                        ]
                    }
                }
            return {
                "result": {
                    "offerMappingEntries": [
                        {
                            "offer": {
                                "shopSku": "SKU-1",
                                "name": "Blue mug",
                                "pictures": ["https://example.test/mug.jpg"],
                                "price": 990,
                                "stock": 7,
                            },
                            "mapping": {"marketCategory": {"id": 77, "name": "Mugs"}},
                        },
                        {
                            "offer": {
                                "shopSku": "SKU-2",
                                "name": "Red mug",
                                "pictures": ["https://example.test/mug-red.jpg"],
                                "price": 1090,
                                "stock": 3,
                            },
                            "mapping": {"marketCategory": {"id": 77, "name": "Mugs"}},
                        },
                    ]
                }
            }
        if path == "/v2/categories/tree":
            return {
                "result": {
                    "children": [
                        {
                            "id": 10,
                            "name": "Kitchen",
                            "children": [{"id": 77, "name": "Mugs", "children": []}],
                        }
                    ]
                }
            }
        if path == "/v2/category/77/parameters":
            assert kwargs["json"] == {"businessId": 321}
            return {
                "result": {
                    "parameters": [
                        {
                            "id": 501,
                            "name": "Brand",
                            "required": True,
                            "type": "ENUM",
                            "multivalue": False,
                            "allowCustomValues": False,
                            "values": [
                                {"id": 11, "value": "Acme"},
                                {"id": 12, "value": "Contoso"},
                            ],
                        },
                        {
                            "id": 502,
                            "name": "Length",
                            "required": False,
                            "type": "NUMERIC",
                            "multivalue": False,
                            "allowCustomValues": True,
                            "unit": {"name": "cm", "defaultUnitId": 99},
                            "constraints": {"minValue": 1, "maxValue": 200},
                        },
                    ]
                }
            }
        if path == "/businesses/321/offer-mappings/update":
            payload = kwargs["json"]
            assert payload == {
                "offerMappingEntries": [
                    {
                        "marketCategoryId": 77,
                        "offer": {
                            "shopSku": "SKU-1",
                            "name": "Blue mug",
                            "description": "Large ceramic mug",
                            "vendor": "Acme",
                            "pictures": ["https://example.test/mug.jpg"],
                        },
                        "parameterValues": [
                            {
                                "parameterId": 501,
                                "values": [{"value": "Acme", "optionId": 11}],
                            }
                        ],
                    }
                ]
            }
            return {"status": "OK"}
        if path == "/businesses/321/offer-mappings":
            payload = kwargs["json"]
            assert payload == {"offerIds": ["SKU-1"]}
            return {
                "result": {
                    "offerMappingEntries": [
                        {
                            "offer": {"shopSku": "SKU-1", "name": "Blue mug"},
                            "mapping": {"marketCategory": {"id": 77, "name": "Mugs"}},
                            "processingState": {
                                "status": "READY",
                                "notes": [],
                            },
                        }
                    ]
                }
            }
        raise AssertionError(f"Unexpected request: {path}")


@pytest.mark.anyio
async def test_list_products_uses_campaign_context_and_normalizes_response():
    client = StubYandexMarketClient()

    result = await client.list_products(
        {"token": "ym-token", "business_id": 321, "campaign_id": 654},
        limit=2,
    )

    assert [item.id for item in result] == ["SKU-1", "SKU-2"]
    assert result[0].category_id == 77
    assert result[0].category_name == "Mugs"
    assert result[0].images == ["https://example.test/mug.jpg"]
    assert client.calls == [
        (
            "POST",
            "/v2/campaigns/654/offer-mapping-entries.json",
            {"json": {"limit": 2}},
        )
    ]


@pytest.mark.anyio
async def test_get_product_details_returns_preview_ready_core_fields():
    client = StubYandexMarketClient()

    result = await client.get_product_details(
        {"token": "ym-token", "business_id": 321, "campaign_id": 654},
        "SKU-1",
    )

    assert isinstance(result, ProductDetails)
    assert result.id == "SKU-1"
    assert result.offer_id == "SKU-1"
    assert result.title == "Blue mug"
    assert result.description == "Large ceramic mug"
    assert result.category_id == 77
    assert result.images == ["https://example.test/mug.jpg"]
    assert result.brand == "Acme"
    assert result.attributes == {"Color": ["Blue"]}


@pytest.mark.anyio
async def test_list_categories_flattens_tree():
    client = StubYandexMarketClient()

    result = await client.list_categories(
        {"token": "ym-token", "business_id": 321, "campaign_id": 654},
    )

    assert [(item.id, item.name, item.parent_id) for item in result] == [
        (10, "Kitchen", None),
        (77, "Mugs", 10),
    ]


@pytest.mark.anyio
async def test_get_category_attributes_returns_import_leaning_metadata():
    client = StubYandexMarketClient()

    result = await client.get_category_attributes(
        {"token": "ym-token", "business_id": 321, "campaign_id": 654},
        77,
        required_only=True,
    )

    assert len(result) == 1
    assert result[0].id == 501
    assert result[0].name == "Brand"
    assert result[0].required is True
    assert result[0].type == "ENUM"
    assert result[0].dictionary_values == [{"id": 11, "value": "Acme"}, {"id": 12, "value": "Contoso"}]
    assert result[0].raw["allowCustomValues"] is False
    assert result[0].raw["multivalue"] is False


@pytest.mark.anyio
async def test_create_products_uses_business_offer_mappings_update_endpoint():
    client = StubYandexMarketClient()

    result = await client.create_products(
        {"token": "ym-token", "business_id": 321, "campaign_id": 654},
        [
            {
                "marketCategoryId": 77,
                "offer": {
                    "shopSku": "SKU-1",
                    "name": "Blue mug",
                    "description": "Large ceramic mug",
                    "vendor": "Acme",
                    "pictures": ["https://example.test/mug.jpg"],
                },
                "parameterValues": [
                    {
                        "parameterId": 501,
                        "values": [{"value": "Acme", "optionId": 11}],
                    }
                ],
            }
        ],
    )

    assert result["status"] == "submitted"
    assert result["external_task_id"] == "SKU-1"
    assert result["submitted_count"] == 1


@pytest.mark.anyio
async def test_get_import_status_aggregates_offer_processing_state():
    client = StubYandexMarketClient()

    result = await client.get_import_status(
        {"token": "ym-token", "business_id": 321, "campaign_id": 654},
        "SKU-1",
    )

    assert result["status"] == "completed"
    assert result["processed_count"] == 1
    assert result["completed_count"] == 1
    assert result["errors"] == []
    assert result["items"] == [
        {
            "offer_id": "SKU-1",
            "status": "ready",
            "notes": [],
        }
    ]


def test_catalog_api_serves_yandex_market_products_details_and_categories(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, StubYandexMarketClient())
    client = TestClient(app)

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    token = register_response.json()["access_token"]

    client.put(
        "/api/v1/connections/yandex_market",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "marketplace": "yandex_market",
            "token": "ym-token",
            "business_id": 321,
            "campaign_id": 654,
        },
    )

    products_response = client.get(
        "/api/v1/catalog/products?marketplace=yandex_market",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert products_response.status_code == 200
    assert products_response.json()[0]["id"] == "SKU-1"

    details_response = client.get(
        "/api/v1/catalog/products/SKU-1?marketplace=yandex_market",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert details_response.status_code == 200
    assert details_response.json()["category_name"] == "Mugs"

    categories_response = client.get(
        "/api/v1/catalog/categories?marketplace=yandex_market",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert categories_response.status_code == 200
    assert [item["id"] for item in categories_response.json()] == [10, 77]

    attributes_response = client.get(
        "/api/v1/catalog/categories/77/attributes?marketplace=yandex_market&required_only=True",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert attributes_response.status_code == 200
    assert attributes_response.json() == [
        {
            "id": 501,
            "name": "Brand",
            "required": True,
            "type": "ENUM",
            "dictionary_values": [
                {"id": 11, "value": "Acme"},
                {"id": 12, "value": "Contoso"},
            ],
            "raw": {
                "id": 501,
                "name": "Brand",
                "required": True,
                "type": "ENUM",
                "multivalue": False,
                "allowCustomValues": False,
                "values": [
                    {"id": 11, "value": "Acme"},
                    {"id": 12, "value": "Contoso"},
                ],
            },
        }
    ]
