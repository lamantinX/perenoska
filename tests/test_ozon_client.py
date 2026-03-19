from __future__ import annotations

import pytest

from app.clients.base import MarketplaceAPIError
from app.clients.ozon import OzonClient
from app.schemas import ProductDetails, ProductSummary


class StubOzonClient(OzonClient):
    def __init__(self) -> None:
        super().__init__("https://ozon.invalid", 1.0)
        self.calls: list[tuple[str, str, dict]] = []

    async def _request(self, method: str, path: str, credentials: dict, **kwargs):
        self.calls.append((method, path, kwargs))
        return {
            "result": [
                {"id": 111, "value": "Acme"},
                {"id": 222, "value": "Acme Studio"},
            ]
        }


class StubOzonPagedProductClient(OzonClient):
    def __init__(self) -> None:
        super().__init__("https://ozon.invalid", 1.0)
        self.list_payloads: list[dict] = []

    async def _request(self, method: str, path: str, credentials: dict, **kwargs):
        if path == "/v3/product/list":
            payload = kwargs["json"]
            self.list_payloads.append(payload)
            if payload["last_id"] == "":
                return {
                    "result": {
                        "items": [
                            {"product_id": 1, "offer_id": "SKU-1", "name": "One"},
                            {"product_id": 2, "offer_id": "SKU-2", "name": "Two"},
                        ],
                        "last_id": "cursor-2",
                    }
                }
            if payload["last_id"] == "cursor-2":
                return {
                    "result": {
                        "items": [
                            {"product_id": 3, "offer_id": "SKU-3", "name": "Three"},
                        ],
                        "last_id": "",
                    }
                }
        if path == "/v3/product/info/list":
            ids = kwargs["json"]["product_id"]
            return {
                "result": {
                    "items": [
                        {"id": product_id, "price": str(product_id * 100)}
                        for product_id in ids
                    ]
                }
            }
        raise AssertionError(f"Unexpected request: {path}")


class StubOzonRepeatedCursorClient(OzonClient):
    def __init__(self) -> None:
        super().__init__("https://ozon.invalid", 1.0)
        self.list_payloads: list[dict] = []

    async def _request(self, method: str, path: str, credentials: dict, **kwargs):
        if path == "/v3/product/list":
            payload = kwargs["json"]
            self.list_payloads.append(payload)
            if len(self.list_payloads) == 1:
                return {
                    "result": {
                        "items": [
                            {"product_id": 1, "offer_id": "SKU-1", "name": "One"},
                            {"product_id": 2, "offer_id": "SKU-2", "name": "Two"},
                        ],
                        "last_id": "cursor-2",
                    }
                }
            return {
                "result": {
                    "items": [
                        {"product_id": 3, "offer_id": "SKU-3", "name": "Three"},
                    ],
                    "last_id": "cursor-2",
                }
            }
        if path == "/v3/product/info/list":
            ids = kwargs["json"]["product_id"]
            return {
                "result": {
                    "items": [
                        {"id": product_id, "price": str(product_id * 100)}
                        for product_id in ids
                    ]
                }
            }
        raise AssertionError(f"Unexpected request: {path}")


class StubOzonDetailsFallbackClient(OzonClient):
    def __init__(self) -> None:
        super().__init__("https://ozon.invalid", 1.0)
        self.calls: list[str] = []

    async def _request(self, method: str, path: str, credentials: dict, **kwargs):
        self.calls.append(path)
        if path == "/v3/product/info/list":
            return {
                "result": {
                    "items": [
                        {
                            "id": 2001,
                            "product_id": 2001,
                            "offer_id": "OZ-2001",
                            "name": "Blue hoodie",
                            "description": "Soft blue hoodie",
                            "category_id": 901,
                            "category_name": "Hoodies",
                            "price": "3499",
                            "images": ["https://example.test/hoodie.jpg"],
                            "barcodes": ["4601234567890"],
                            "brand": "Acme",
                        }
                    ]
                }
            }
        if path == "/v4/products/info/attributes":
            raise MarketplaceAPIError("Ozon API error 404: 404 page not found")
        if path == "/v1/product/info/description":
            raise MarketplaceAPIError("Ozon API error 404: 404 page not found")
        raise AssertionError(f"Unexpected request: {path}")


class StubOzonRichDetailsClient(OzonClient):
    def __init__(self) -> None:
        super().__init__("https://ozon.invalid", 1.0)
        self.calls: list[str] = []

    async def _request(self, method: str, path: str, credentials: dict, **kwargs):
        self.calls.append(path)
        if path == "/v3/product/info/list":
            return {
                "result": {
                    "items": [
                        {
                            "id": 2001,
                            "product_id": 2001,
                            "offer_id": "OZ-2001",
                            "name": "Blue hoodie",
                            "description": "",
                            "category_id": 901,
                            "category_name": "Hoodies",
                            "price": "3499",
                            "images": ["https://example.test/list-image.jpg"],
                            "barcodes": [],
                            "stocks": {
                                "present": 7,
                            },
                        }
                    ]
                }
            }
        if path == "/v4/products/info/attributes":
            return {
                "result": [
                    {
                        "id": 2001,
                        "barcode": "4601234567890",
                        "images": [
                            {"file_name": "https://example.test/attr-1.jpg", "index": 0},
                            {"file_name": "https://example.test/attr-2.jpg", "index": 1},
                        ],
                        "attributes": [
                            {
                                "attribute_id": 85,
                                "values": [{"dictionary_value_id": 111, "value": "Acme"}],
                            },
                            {
                                "attribute_id": 10096,
                                "values": [{"dictionary_value_id": 0, "value": "Blue"}],
                            },
                        ],
                        "height": 250,
                        "depth": 10,
                        "width": 150,
                        "dimension_unit": "mm",
                        "weight": 100,
                        "weight_unit": "g",
                    }
                ]
            }
        if path == "/v1/product/info/description":
            return {
                "result": {
                    "id": 2001,
                    "offer_id": "OZ-2001",
                    "name": "Blue hoodie",
                    "description": "Soft blue hoodie for everyday wear",
                }
            }
        raise AssertionError(f"Unexpected request: {path}")


class StubOzonNamedAttributeDetailsClient(OzonClient):
    def __init__(self) -> None:
        super().__init__("https://ozon.invalid", 1.0)

    async def _request(self, method: str, path: str, credentials: dict, **kwargs):
        if path == "/v3/product/info/list":
            return {
                "result": {
                    "items": [
                        {
                            "id": 2001,
                            "product_id": 2001,
                            "offer_id": "OZ-2001",
                            "name": "Blue hoodie",
                            "category_id": 901,
                            "category_name": "Hoodies",
                            "price": "3499",
                            "images": ["https://example.test/list-image.jpg"],
                        }
                    ]
                }
            }
        if path == "/v4/products/info/attributes":
            return {
                "result": [
                    {
                        "id": 2001,
                        "images": [
                            "https://example.test/attr-1.jpg",
                            {"src": "https://example.test/attr-2.jpg", "index": 1},
                        ],
                        "attributes": [
                            {
                                "attribute_id": 10096,
                                "name": "Color",
                                "values": [{"value": "Blue"}],
                            },
                            {
                                "attribute_id": 8050,
                                "name": "Material",
                                "values": [{"value": "Cotton"}],
                            },
                        ],
                    }
                ]
            }
        if path == "/v1/product/info/description":
            return {"result": {"description": "Soft blue hoodie for everyday wear"}}
        raise AssertionError(f"Unexpected request: {path}")


@pytest.mark.anyio
async def test_get_dictionary_values_uses_ozon_attribute_values_endpoint():
    client = StubOzonClient()

    result = await client.get_dictionary_values(
        {"client_id": "cid", "api_key": "key"},
        attribute_id=85,
        description_category_id=501,
        type_id=601,
        search="acme",
        limit=25,
    )

    assert result == [
        {"id": 111, "value": "Acme"},
        {"id": 222, "value": "Acme Studio"},
    ]
    assert client.calls == [
        (
            "POST",
            "/v1/description-category/attribute/values",
            {
                "json": {
                    "description_category_id": 501,
                    "type_id": 601,
                    "attribute_id": 85,
                    "language": "DEFAULT",
                    "limit": 25,
                    "last_value_id": 0,
                    "value": "acme",
                }
            },
        )
    ]


@pytest.mark.anyio
async def test_list_products_fetches_multiple_ozon_pages_until_limit():
    client = StubOzonPagedProductClient()

    result = await client.list_products({"client_id": "cid", "api_key": "key"}, limit=3)

    assert [item.id for item in result] == ["1", "2", "3"]
    assert [item.price for item in result] == ["100", "200", "300"]
    assert client.list_payloads == [
        {
            "filter": {"visibility": "ALL"},
            "last_id": "",
            "limit": 3,
        },
        {
            "filter": {"visibility": "ALL"},
            "last_id": "cursor-2",
            "limit": 1,
        },
    ]


@pytest.mark.anyio
async def test_list_products_stops_when_ozon_cursor_repeats():
    client = StubOzonRepeatedCursorClient()

    result = await client.list_products({"client_id": "cid", "api_key": "key"}, limit=10)

    assert [item.id for item in result] == ["1", "2", "3"]
    assert client.list_payloads == [
        {
            "filter": {"visibility": "ALL"},
            "last_id": "",
            "limit": 10,
        },
        {
            "filter": {"visibility": "ALL"},
            "last_id": "cursor-2",
            "limit": 8,
        },
    ]


@pytest.mark.anyio
async def test_get_product_details_tolerates_missing_attributes_endpoint():
    client = StubOzonDetailsFallbackClient()

    result = await client.get_product_details({"client_id": "cid", "api_key": "key"}, "2001")

    assert isinstance(result, ProductDetails)
    assert result.id == "2001"
    assert result.offer_id == "OZ-2001"
    assert result.title == "Blue hoodie"
    assert result.attributes == {}
    assert client.calls == ["/v3/product/info/list", "/v4/products/info/attributes", "/v1/product/info/description"]


@pytest.mark.anyio
async def test_get_product_details_enriches_brand_barcodes_images_and_description():
    client = StubOzonRichDetailsClient()

    result = await client.get_product_details({"client_id": "cid", "api_key": "key"}, "2001")

    assert isinstance(result, ProductDetails)
    assert result.id == "2001"
    assert result.offer_id == "OZ-2001"
    assert result.title == "Blue hoodie"
    assert result.description == "Soft blue hoodie for everyday wear"
    assert result.brand == "Acme"
    assert result.barcode_list == ["4601234567890"]
    assert result.images == ["https://example.test/attr-1.jpg", "https://example.test/attr-2.jpg"]
    assert result.stock == 7
    assert result.dimensions == {
        "height": 250,
        "width": 150,
        "depth": 10,
        "weight": 100,
        "dimension_unit": "mm",
        "weight_unit": "g",
    }
    assert result.attributes == {
        "85": ["Acme"],
        "10096": ["Blue"],
    }
    assert client.calls == [
        "/v3/product/info/list",
        "/v4/products/info/attributes",
        "/v1/product/info/description",
    ]


@pytest.mark.anyio
async def test_get_product_details_prefers_attribute_names_and_string_images():
    client = StubOzonNamedAttributeDetailsClient()

    result = await client.get_product_details({"client_id": "cid", "api_key": "key"}, "2001")

    assert isinstance(result, ProductDetails)
    assert result.description == "Soft blue hoodie for everyday wear"
    assert result.images == ["https://example.test/attr-1.jpg", "https://example.test/attr-2.jpg"]
    assert result.attributes == {
        "Color": ["Blue"],
        "Material": ["Cotton"],
    }
