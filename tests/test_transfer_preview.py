from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.clients.base import MarketplaceClient
from app.clients.ozon import OzonClient
from app.clients.wb import WBClient
from app.config import Settings
from app.db import Database
from app.main import create_app
from app.schemas import CategoryAttribute, CategoryNode, Marketplace, ProductDetails, ProductSummary
from app.services.transfer import TransferTraceContext, mask_trace_payload


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


class FakeWBMultiProductClient(FakeWBClient):
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
            ),
            ProductSummary(
                id="1002",
                offer_id="SKU-1002",
                title="Blue t-shirt",
                category_id=10,
                category_name="T-shirts",
                price="2099",
                images=["https://example.test/image-2.jpg"],
            ),
        ]

    async def get_product_details(self, credentials, product_id: str):
        if product_id == "1002":
            return ProductDetails(
                id=product_id,
                offer_id="SKU-1002",
                title="Blue t-shirt",
                description="Basic blue cotton t-shirt",
                category_id=10,
                category_name="T-shirts",
                price="2099",
                images=["https://example.test/image-2.jpg"],
                attributes={"Color": ["Blue"], "Material": ["Cotton"]},
                dimensions={"height": 10, "width": 20, "depth": 30, "weight": 400},
                sizes=[{"techSize": "M", "wbSize": "46"}],
                brand="Acme",
            )
        return await super().get_product_details(credentials, product_id)


class StubPagedWBClient(WBClient):
    def __init__(self) -> None:
        super().__init__("https://wb.invalid", 1.0)
        self.calls: list[dict] = []

    async def _request(
        self,
        method: str,
        path: str,
        credentials: dict[str, str],
        **kwargs,
    ) -> dict:
        if path != "/content/v2/get/cards/list":
            raise AssertionError(f"Unexpected request: {path}")
        payload = kwargs["json"]
        self.calls.append(payload)
        cursor = payload["settings"]["cursor"]
        if len(self.calls) == 1:
            return {
                "cards": [
                    {"nmID": 1001, "vendorCode": "SKU-1001", "title": "One"},
                    {"nmID": 1002, "vendorCode": "SKU-1002", "title": "Two"},
                ],
                "cursor": {"updatedAt": "2024-01-01T00:00:00Z", "nmID": 1002},
            }
        return {
            "cards": [
                {"nmID": 1003, "vendorCode": "SKU-1003", "title": "Three"},
            ],
            "cursor": {"updatedAt": cursor["updatedAt"], "nmID": 1003},
        }

    async def _fetch_public_details(self, nm_ids):
        return {}

    async def _fetch_seller_prices(self, credentials, nm_ids):
        return {}


class StubWBLimitCappedClient(WBClient):
    def __init__(self) -> None:
        super().__init__("https://wb.invalid", 1.0)
        self.calls: list[dict] = []

    async def _request(
        self,
        method: str,
        path: str,
        credentials: dict[str, str],
        **kwargs,
    ) -> dict:
        payload = kwargs["json"]
        self.calls.append(payload)
        cursor = payload["settings"]["cursor"]
        if len(self.calls) == 1:
            assert cursor["limit"] == 100
            return {
                "cards": [{"nmID": index, "vendorCode": f"SKU-{index}", "title": f"Item {index}"} for index in range(1, 101)],
                "cursor": {"updatedAt": "2024-01-01T00:00:00Z", "nmID": 100},
            }
        assert cursor["limit"] == 20
        return {
            "cards": [{"nmID": index, "vendorCode": f"SKU-{index}", "title": f"Item {index}"} for index in range(101, 121)],
            "cursor": {"updatedAt": "2024-01-01T00:00:00Z", "nmID": 120},
        }

    async def _fetch_public_details(self, nm_ids):
        return {}

    async def _fetch_seller_prices(self, credentials, nm_ids):
        return {}


class StubWBRepeatedCursorClient(WBClient):
    def __init__(self) -> None:
        super().__init__("https://wb.invalid", 1.0)
        self.calls: list[dict] = []

    async def _request(
        self,
        method: str,
        path: str,
        credentials: dict[str, str],
        **kwargs,
    ) -> dict:
        payload = kwargs["json"]
        self.calls.append(payload)
        if len(self.calls) == 1:
            return {
                "cards": [
                    {"nmID": 1001, "vendorCode": "SKU-1001", "title": "One"},
                    {"nmID": 1002, "vendorCode": "SKU-1002", "title": "Two"},
                ],
                "cursor": {"updatedAt": "2024-01-01T00:00:00Z", "nmID": 1002},
            }
        return {
            "cards": [
                {"nmID": 1003, "vendorCode": "SKU-1003", "title": "Three"},
            ],
            "cursor": {"updatedAt": "2024-01-01T00:00:00Z", "nmID": 1002},
        }

    async def _fetch_public_details(self, nm_ids):
        return {}

    async def _fetch_seller_prices(self, credentials, nm_ids):
        return {}


class StubWBCharacteristicFormatClient(WBClient):
    def __init__(self) -> None:
        super().__init__("https://wb.invalid", 1.0)

    async def _request(
        self,
        method: str,
        path: str,
        credentials: dict[str, str],
        **kwargs,
    ) -> dict:
        if path != "/content/v2/get/cards/list":
            raise AssertionError(f"Unexpected request: {path}")
        return {
            "cards": [
                {
                    "nmID": 1001,
                    "vendorCode": "SKU-1001",
                    "title": "Red t-shirt",
                    "subjectID": 10,
                    "subjectName": "T-shirts",
                    "sizes": [{"skus": ["4601234567890"]}],
                    "characteristics": [
                        {
                            "charcID": 1,
                            "charcName": "Color",
                            "charcValues": [{"value": "Red"}],
                        },
                        {
                            "charcID": 2,
                            "charcName": "Material",
                            "charcValues": ["Cotton"],
                        },
                    ],
                }
            ]
        }

    async def _fetch_public_details(self, nm_ids):
        return {}

    async def _fetch_seller_prices(self, credentials, nm_ids):
        return {}

    async def _fetch_public_card_json(self, card):
        return {}

    async def _fetch_public_seller_info(self, card):
        return {}


class StubWBVariantPayloadClient(WBClient):
    def __init__(self) -> None:
        super().__init__("https://wb.invalid", 1.0)

    async def _request(
        self,
        method: str,
        path: str,
        credentials: dict[str, str],
        **kwargs,
    ) -> dict:
        if path != "/content/v2/get/cards/list":
            raise AssertionError(f"Unexpected request: {path}")
        return {
            "cards": [
                {
                    "nmID": 1001,
                    "subjectID": 10,
                    "subjectName": "Аппарат для маникюра",
                    "variants": [
                        {
                            "vendorCode": "SKU-1001",
                            "title": "Аппарат для маникюра и педикюра",
                            "description": "Описание из variant",
                            "brand": "Acme",
                            "mediaFiles": ["https://example.test/device-1.jpg"],
                            "sizes": [{"skus": ["4601234567890"], "price": 1999}],
                        }
                    ],
                }
            ]
        }

    async def _fetch_public_details(self, nm_ids):
        return {}

    async def _fetch_seller_prices(self, credentials, nm_ids):
        return {}

    async def _fetch_public_card_json(self, card):
        return {}

    async def _fetch_public_seller_info(self, card):
        return {}


class FakeOzonClient(MarketplaceClient):
    def __init__(self) -> None:
        self.created_payloads: list[list[dict]] = []

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
        self.created_payloads.append(items)
        return {"external_task_id": "ozon-task-1", "raw_response": {"result": {"task_id": "ozon-task-1"}}}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed", "errors": []}


class FakeOzonCachingProbeClient(FakeOzonClient):
    def __init__(self) -> None:
        self.category_attributes_calls = 0

    async def get_category_attributes_for_node(
        self,
        credentials,
        category: CategoryNode,
        *,
        source_product: ProductDetails | None = None,
        required_only: bool = False,
    ):
        self.category_attributes_calls += 1
        category.raw["_resolved_type_id"] = 601
        category.raw["_resolved_type_name"] = "T-shirt"
        return [
            CategoryAttribute(id=1, name="Color", required=True, dictionary_values=[{"id": 99, "value": "Red"}]),
            CategoryAttribute(id=2, name="Material", required=False),
        ]


class FakeWBMixedTypeProductsClient(FakeWBClient):
    async def list_products(self, credentials, *, limit: int = 50):
        return [
            ProductSummary(
                id="1001",
                offer_id="SKU-1001",
                title="Red t-shirt",
                category_id=10,
                category_name="Upper wear",
                price="1999",
                images=["https://example.test/image-1.jpg"],
            ),
            ProductSummary(
                id="1002",
                offer_id="SKU-1002",
                title="Blue jumper",
                category_id=10,
                category_name="Upper wear",
                price="2099",
                images=["https://example.test/image-2.jpg"],
            ),
        ]

    async def get_product_details(self, credentials, product_id: str):
        if product_id == "1002":
            return ProductDetails(
                id=product_id,
                offer_id="SKU-1002",
                title="Blue jumper",
                description="Warm jumper",
                category_id=10,
                category_name="Upper wear",
                price="2099",
                images=["https://example.test/image-2.jpg"],
                attributes={"Color": ["Blue"]},
                brand="Acme",
            )
        return ProductDetails(
            id=product_id,
            offer_id="SKU-1001",
            title="Red t-shirt",
            description="Basic t-shirt",
            category_id=10,
            category_name="Upper wear",
            price="1999",
            images=["https://example.test/image-1.jpg"],
            attributes={"Color": ["Red"]},
            brand="Acme",
        )


class FakeOzonMixedTypeCategoryClient(FakeOzonClient):
    def __init__(self) -> None:
        self.category_attributes_calls: list[tuple[str, int]] = []

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(
                id=501,
                name="Upper wear",
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

    def resolve_category_context(
        self,
        category: CategoryNode,
        *,
        source_product: ProductDetails | None = None,
    ) -> dict[str, int | str | None]:
        assert source_product is not None
        if "jumper" in source_product.title.lower():
            return {
                "description_category_id": category.id,
                "type_id": 602,
                "type_name": "Jumper",
            }
        return {
            "description_category_id": category.id,
            "type_id": 601,
            "type_name": "T-shirt",
        }

    async def get_category_attributes_for_node(
        self,
        credentials,
        category: CategoryNode,
        *,
        source_product: ProductDetails | None = None,
        required_only: bool = False,
    ):
        context = self.resolve_category_context(category, source_product=source_product)
        self.category_attributes_calls.append((source_product.id, int(context["type_id"] or 0)))
        return [CategoryAttribute(id=1, name="Color", required=True)]


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

    async def get_dictionary_values(
        self,
        credentials,
        *,
        attribute_id: int,
        description_category_id: int,
        type_id: int,
        search: str | None = None,
        limit: int = 50,
    ):
        items = [
            {"id": 111, "value": "Acme"},
            {"id": 222, "value": "Acme Studio"},
        ]
        if search:
            return [item for item in items if search.lower() in item["value"].lower()][:limit]
        return items[:limit]


class FakeOzonBrandValidationClient(FakeOzonStrictBrandClient):
    async def get_dictionary_values(
        self,
        credentials,
        *,
        attribute_id: int,
        description_category_id: int,
        type_id: int,
        search: str | None = None,
        limit: int = 50,
    ):
        if search:
            return [{"id": 111, "value": "ACME"}]
        return await super().get_dictionary_values(
            credentials,
            attribute_id=attribute_id,
            description_category_id=description_category_id,
            type_id=type_id,
            search=search,
            limit=limit,
        )


class FakeOzonBrandValidationFallbackClient(FakeOzonStrictBrandClient):
    async def get_dictionary_values(
        self,
        credentials,
        *,
        attribute_id: int,
        description_category_id: int,
        type_id: int,
        search: str | None = None,
        limit: int = 50,
    ):
        if search:
            return []
        return [{"id": 111, "value": "Acme"}]


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


def build_client_with_ozon_client(tmp_path, ozon_client: MarketplaceClient):
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
    app.state.container.client_factory.register_override(Marketplace.OZON, ozon_client)
    return TestClient(app)


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_transfer_log_storage_roundtrip(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()

    database.create_transfer_log(
        created_at="2026-03-18T10:00:00+00:00",
        base_token="tracebase",
        sequence_no=1,
        token="tracebase_1",
        event_type="function",
        operation="preview.start",
        request_url="function://transfer/preview",
        request_headers={"x-test": "1"},
        request_body={"product_ids": ["1001"]},
        response_headers={},
        response_body={"ready": True},
        source_marketplace="wb",
        target_marketplace="ozon",
        job_id=None,
        status_code=None,
        duration_ms=12,
        error_text=None,
    )

    logs = database.list_transfer_logs(base_token="tracebase")
    assert len(logs) == 1
    assert logs[0]["token"] == "tracebase_1"
    assert logs[0]["base_token"] == "tracebase"
    assert logs[0]["sequence_no"] == 1
    assert logs[0]["request_body"] == {"product_ids": ["1001"]}
    assert logs[0]["response_body"] == {"ready": True}


def test_trace_context_generates_sequential_tokens_and_masks_secrets(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()

    trace = TransferTraceContext(
        database=database,
        base_token="tracebase",
        source_marketplace="wb",
        target_marketplace="ozon",
    )

    first_token = trace.next_token()
    second_token = trace.next_token()

    masked = mask_trace_payload(
        {
            "Authorization": "Bearer secret-token",
            "nested": {"api_key": "very-secret"},
            "items": [{"token": "abc123"}],
        }
    )

    assert first_token == "tracebase_1"
    assert second_token == "tracebase_2"
    assert masked["Authorization"] == "***"
    assert masked["nested"]["api_key"] == "***"
    assert masked["items"][0]["token"] == "***"


def test_preview_launch_and_sync_transfer(tmp_path):
    ozon_client = FakeOzonClient()
    client = build_client_with_ozon_client(tmp_path, ozon_client)
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
    assert ozon_client.created_payloads == [
        [
                {
                    "offer_id": "SKU-1001",
                    "name": "Red t-shirt",
                    "annotation": "Basic cotton t-shirt",
                    "description": "Basic cotton t-shirt",
                    "description_category_id": 501,
                    "type_id": 601,
                    "attributes": [
                        {"id": 1, "complex_id": 0, "values": [{"value": "Red", "dictionary_value_id": 99}]},
                        {"id": 2, "complex_id": 0, "values": [{"value": "Cotton"}]},
                    ],
                    "images": ["https://example.test/image-1.jpg"],
                    "price": "1999",
                    "old_price": "1999",
                    "stock": 0,
                    "barcode": "",
                    "vat": "0",
                    "height": 100,
                    "width": 200,
                    "depth": 300,
                    "weight": 400,
                    "dimension_unit": "mm",
                    "weight_unit": "g",
                }
            ]
        ]

    jobs_response = client.get("/api/v1/transfers", headers=headers)
    assert jobs_response.status_code == 200
    assert len(jobs_response.json()) == 1

    sync_response = client.post(f"/api/v1/transfers/{job['id']}/sync", headers=headers)
    assert sync_response.status_code == 200
    assert sync_response.json()["status"] == "completed"


def test_preview_persists_function_logs_with_sequential_tokens(tmp_path):
    client = build_client(tmp_path)
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
        json={"source_marketplace": "wb", "target_marketplace": "ozon", "product_ids": ["1001"], "target_category_id": 501},
    )
    assert preview_response.status_code == 200

    logs = client.app.state.container.database.list_transfer_logs()
    assert len(logs) >= 3
    base_tokens = {log["base_token"] for log in logs}
    assert len(base_tokens) == 1
    assert [log["token"] for log in logs] == [f"{logs[0]['base_token']}_{index}" for index in range(1, len(logs) + 1)]
    assert logs[0]["operation"] == "transfer.preview.start"
    assert any(log["operation"] == "mapping.build_import_payload" for log in logs)
    assert logs[-1]["operation"] == "transfer.preview.result"


def test_launch_uses_new_base_token_for_its_own_logs(tmp_path):
    client = build_client(tmp_path)
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
        json={"source_marketplace": "wb", "target_marketplace": "ozon", "product_ids": ["1001"], "target_category_id": 501},
    )
    assert preview_response.status_code == 200
    preview_logs = client.app.state.container.database.list_transfer_logs()
    preview_base_token = preview_logs[0]["base_token"]

    launch_response = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={"source_marketplace": "wb", "target_marketplace": "ozon", "product_ids": ["1001"], "target_category_id": 501},
    )
    assert launch_response.status_code == 200

    all_logs = client.app.state.container.database.list_transfer_logs()
    launch_logs = [log for log in all_logs if log["base_token"] != preview_base_token]
    assert launch_logs
    assert launch_logs[0]["operation"] == "transfer.launch.start"
    assert launch_logs[-1]["operation"] == "transfer.launch.result"
    assert launch_logs[0]["token"].endswith("_1")


@pytest.mark.anyio
async def test_wb_list_products_fetches_multiple_pages_until_limit():
    client = StubPagedWBClient()

    result = await client.list_products({"token": "wb-token"}, limit=3)

    assert [item.id for item in result] == ["1001", "1002", "1003"]
    assert client.calls == [
        {
            "settings": {
                "cursor": {
                    "limit": 3,
                },
                "filter": {
                    "withPhoto": -1,
                },
            }
        },
        {
            "settings": {
                "cursor": {
                    "limit": 1,
                    "updatedAt": "2024-01-01T00:00:00Z",
                    "nmID": 1002,
                },
                "filter": {
                    "withPhoto": -1,
                },
            }
        },
    ]


@pytest.mark.anyio
async def test_wb_get_product_details_reads_charc_name_and_values():
    client = StubWBCharacteristicFormatClient()

    result = await client.get_product_details({"token": "wb-token"}, "1001")

    assert isinstance(result, ProductDetails)
    assert result.attributes == {
        "Color": ["Red"],
        "Material": ["Cotton"],
    }


@pytest.mark.anyio
async def test_wb_get_product_details_reads_media_and_description_from_variant():
    client = StubWBVariantPayloadClient()

    result = await client.get_product_details({"token": "wb-token"}, "1001")

    assert result.title == "Аппарат для маникюра и педикюра"
    assert result.description == "Описание из variant"
    assert result.brand == "Acme"
    assert result.price == "1999"
    assert result.images == ["https://example.test/device-1.jpg"]
    assert result.barcode_list == ["4601234567890"]


@pytest.mark.anyio
async def test_wb_list_products_caps_request_limit_to_100():
    client = StubWBLimitCappedClient()

    result = await client.list_products({"token": "wb-token"}, limit=120)

    assert len(result) == 120
    assert client.calls == [
        {
            "settings": {
                "cursor": {
                    "limit": 100,
                },
                "filter": {
                    "withPhoto": -1,
                },
            }
        },
        {
            "settings": {
                "cursor": {
                    "limit": 20,
                    "updatedAt": "2024-01-01T00:00:00Z",
                    "nmID": 100,
                },
                "filter": {
                    "withPhoto": -1,
                },
            }
        },
    ]


@pytest.mark.anyio
async def test_wb_list_products_stops_when_cursor_repeats():
    client = StubWBRepeatedCursorClient()

    result = await client.list_products({"token": "wb-token"}, limit=10)

    assert [item.id for item in result] == ["1001", "1002", "1003"]
    assert client.calls == [
        {
            "settings": {
                "cursor": {
                    "limit": 10,
                },
                "filter": {
                    "withPhoto": -1,
                },
            }
        },
        {
            "settings": {
                "cursor": {
                    "limit": 8,
                    "updatedAt": "2024-01-01T00:00:00Z",
                    "nmID": 1002,
                },
                "filter": {
                    "withPhoto": -1,
                },
            }
        },
    ]


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


def test_preview_reuses_target_category_attributes_for_same_category(tmp_path):
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
    ozon_client = FakeOzonCachingProbeClient()
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBMultiProductClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, ozon_client)
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
            "product_ids": ["1001", "1002"],
            "target_category_id": 501,
        },
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert len(preview_data["items"]) == 2
    assert ozon_client.category_attributes_calls == 1


def test_preview_uses_separate_ozon_type_context_per_product(tmp_path):
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
    ozon_client = FakeOzonMixedTypeCategoryClient()
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBMixedTypeProductsClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, ozon_client)
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
            "product_ids": ["1001", "1002"],
            "target_category_id": 501,
        },
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert [item["payload"]["type_id"] for item in preview_data["items"]] == [601, 602]
    assert ozon_client.category_attributes_calls == [("1001", 601), ("1002", 602)]


def test_ozon_token_stems_handles_cyrillic_words():
    stems = OzonClient._token_stems("Игрушками и наборами")

    assert "игрушк" in stems
    assert "набор" in stems


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
    assert preview_data["dictionary_issues"] == [
        {
            "type": "brand",
            "product_id": "1001",
            "source_value": "Acme",
            "source_value_normalized": "acme",
            "target_category_id": 501,
            "target_attribute_id": 85,
            "target_attribute_name": "Brand",
            "options": [
                {"id": 111, "value": "Acme"},
                {"id": 222, "value": "Acme Studio"},
            ],
        }
    ]


def test_saved_brand_mapping_resolves_preview_issue(tmp_path):
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

    save_response = client.post(
        "/api/v1/mappings/dictionary",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "items": [
                {
                    "type": "brand",
                    "source_value": "Acme",
                    "target_category_id": 501,
                    "target_attribute_id": 85,
                    "target_dictionary_value_id": 111,
                    "target_dictionary_value": "Acme",
                }
            ],
        },
    )
    assert save_response.status_code == 200

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
    assert preview_data["ready_to_import"] is True
    assert preview_data["dictionary_issues"] == []
    assert preview_data["brand_mappings"] == [
        {
            "type": "brand",
            "product_id": "1001",
            "source_value": "Acme",
            "source_value_normalized": "acme",
            "target_category_id": 501,
            "target_attribute_id": 85,
            "target_attribute_name": "Brand",
            "selected_dictionary_value_id": 111,
            "selected_dictionary_value": "Acme",
            "options": [
                {"id": 111, "value": "Acme"},
                {"id": 222, "value": "Acme Studio"},
            ],
        }
    ]
    assert preview_data["items"][0]["missing_required_attributes"] == []
    assert preview_data["items"][0]["payload"]["attributes"][0]["values"][0]["dictionary_value_id"] == 111


def test_save_brand_mapping_accepts_matching_ozon_value_id_even_if_label_differs(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonBrandValidationClient())
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

    save_response = client.post(
        "/api/v1/mappings/dictionary",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "items": [
                {
                    "type": "brand",
                    "source_value": "Acme",
                    "target_category_id": 501,
                    "target_attribute_id": 85,
                    "target_dictionary_value_id": 111,
                    "target_dictionary_value": "Acme",
                }
            ],
        },
    )
    assert save_response.status_code == 200


def test_save_brand_mapping_falls_back_to_unfiltered_ozon_lookup_when_search_misses(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonBrandValidationFallbackClient())
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

    save_response = client.post(
        "/api/v1/mappings/dictionary",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "items": [
                {
                    "type": "brand",
                    "source_value": "Acme",
                    "target_category_id": 501,
                    "target_attribute_id": 85,
                    "target_dictionary_value_id": 111,
                    "target_dictionary_value": "Acme",
                }
            ],
        },
    )
    assert save_response.status_code == 200


def test_launch_transfer_blocks_on_unresolved_brand_mapping(tmp_path):
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

    launch_response = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "product_ids": ["1001"],
        },
    )
    assert launch_response.status_code == 400
    detail = launch_response.json()["detail"].lower()
    assert "ozon" in detail
    assert detail

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


class FakeOzonNoAutoCategoryClient(FakeOzonClient):
    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(
                id=701,
                name="Jeans",
                parent_id=None,
                raw={
                    "description_category_id": 701,
                    "children": [{"type_id": 801, "type_name": "Jeans", "disabled": False}],
                },
            ),
            CategoryNode(
                id=501,
                name="T-shirts",
                parent_id=None,
                raw={
                    "description_category_id": 501,
                    "children": [
                        {"type_id": 601, "type_name": "T-shirt", "disabled": False},
                        {"type_id": 602, "type_name": "Longsleeve", "disabled": False},
                    ],
                },
            ),
        ]


class FakeWBUnmappedCategoryClient(FakeWBClient):
    async def list_products(self, credentials, *, limit: int = 50):
        items = await super().list_products(credentials, limit=limit)
        return [items[0].model_copy(update={"category_name": "Upper wear"})]

    async def get_product_details(self, credentials, product_id: str):
        details = await super().get_product_details(credentials, product_id)
        return details.model_copy(
            update={
                "title": "Аппарат для маникюра и педикюра",
                "description": "Компактный аппарат для маникюра",
                "category_name": "Upper wear",
                "price": "2499",
                "images": ["https://example.test/device-1.jpg"],
            }
        )


class FakeOzonRichProductClient(FakeOzonClient):
    async def list_products(self, credentials, *, limit: int = 50):
        return [
            ProductSummary(
                id="2001",
                offer_id="OZ-2001",
                title="Blue hoodie",
                description="Soft blue hoodie for everyday wear",
                category_id=901,
                category_name="Hoodies",
                price="3499",
                images=[
                    "https://example.test/hoodie-1.jpg",
                    "https://example.test/hoodie-2.jpg",
                ],
            )
        ]

    async def get_product_details(self, credentials, product_id: str):
        return ProductDetails(
            id=product_id,
            offer_id="OZ-2001",
            title="Blue hoodie",
            description="Soft blue hoodie for everyday wear",
            category_id=901,
            category_name="Hoodies",
            price="3499",
            images=[
                "https://example.test/hoodie-1.jpg",
                "https://example.test/hoodie-2.jpg",
            ],
            attributes={
                "Color": ["Blue"],
                "Material": ["Cotton"],
                "Country": ["Turkey"],
                "Composition": ["95% cotton, 5% elastane"],
            },
            dimensions={"height": 12, "width": 25, "depth": 30, "weight": 0.7},
            sizes=[
                {
                    "techSize": "L",
                    "name": "50",
                    "skus": ["4601234567890"],
                    "price": "3499",
                }
            ],
            barcode_list=["4601234567890"],
            brand="Acme",
        )


class FakeOzonRichProductMissingDescriptionClient(FakeOzonRichProductClient):
    async def get_product_details(self, credentials, product_id: str):
        details = await super().get_product_details(credentials, product_id)
        return details.model_copy(update={"description": None})


class FakeWBRichTargetClient(FakeWBClient):
    def __init__(self) -> None:
        self.created_payloads: list[list[dict]] = []

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [CategoryNode(id=77, name="Hoodies", parent_id=None)]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        attributes = [
            CategoryAttribute(id=10, name="Color", required=True),
            CategoryAttribute(id=11, name="Material", required=False),
            CategoryAttribute(id=12, name="Country", required=False),
            CategoryAttribute(id=13, name="Composition", required=False),
        ]
        if required_only:
            return [item for item in attributes if item.required]
        return attributes

    async def create_products(self, credentials, items):
        self.created_payloads.append(items)
        return {"external_task_id": "wb-import-77", "raw_response": {"taskId": "wb-import-77"}}


class FakeWBCategoryOptionsClient(FakeWBClient):
    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(id=77, name="Hoodies", parent_id=None),
            CategoryNode(id=88, name="Tops", parent_id=None),
        ]


class FakeOzonUnmappedCategoryByIdClient(FakeOzonClient):
    async def list_products(self, credentials, *, limit: int = 50):
        return [
            ProductSummary(
                id="2001",
                offer_id="OZ-2001",
                title="Аппарат для маникюра и педикюра",
                category_id=59968946,
                category_name="59968946",
                price="3499",
                images=["https://example.test/device.jpg"],
            )
        ]

    async def get_product_details(self, credentials, product_id: str):
        return ProductDetails(
            id=product_id,
            offer_id="OZ-2001",
            title="Аппарат для маникюра и педикюра",
            description="Профессиональный аппарат",
            category_id=59968946,
            category_name="59968946",
            price="3499",
            images=["https://example.test/device.jpg"],
            attributes={},
            brand="Acme",
        )

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(id=59968946, name="Аппараты для маникюра и педикюра", parent_id=None),
        ]


def test_preview_returns_grouped_category_issues(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBUnmappedCategoryClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonNoAutoCategoryClient())
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
        json={"source_marketplace": "wb", "target_marketplace": "ozon", "product_ids": ["1001"]},
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is False
    assert preview_data["dictionary_issues"] == []
    assert preview_data["category_issues"] == [
        {
            "type": "category",
            "source_key": "wb:10",
            "source_label": "Upper wear",
            "target_marketplace": "ozon",
            "product_ids": ["1001"],
            "products": [{"id": "1001", "title": "Аппарат для маникюра и педикюра"}],
            "options": [
                {
                    "key": "ozon:701",
                    "label": "Jeans",
                    "path": "Jeans",
                    "context": {
                        "description_category_id": 701,
                        "types": [{"id": 801, "name": "Jeans"}],
                    },
                },
                {
                    "key": "ozon:501",
                    "label": "T-shirts",
                    "path": "T-shirts",
                    "context": {
                        "description_category_id": 501,
                        "types": [
                            {"id": 601, "name": "T-shirt"},
                            {"id": 602, "name": "Longsleeve"},
                        ],
                    },
                },
            ],
        }
    ]
    assert preview_data["items"][0]["payload"] == {
        "name": "Аппарат для маникюра и педикюра",
        "description": "Компактный аппарат для маникюра",
        "price": "2499",
        "images": ["https://example.test/device-1.jpg"],
        "offer_id": "SKU-1001",
        "attributes": [
            {
                "name": "Бренд",
                "value": ["Acme"],
            }
        ],
    }


def test_saved_category_mapping_resolves_preview_before_brand_checks(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBUnmappedCategoryClient())
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

    save_response = client.post(
        "/api/v1/mappings/categories",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "ozon",
            "items": [
                {
                    "type": "category",
                    "source_key": "wb:10",
                    "source_label": "Upper wear",
                    "target_key": "ozon:501",
                    "target_label": "T-shirts",
                    "target_context": {
                        "description_category_id": 501,
                        "type_id": 601,
                        "type_name": "T-shirt",
                    },
                }
            ],
        },
    )
    assert save_response.status_code == 200

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={"source_marketplace": "wb", "target_marketplace": "ozon", "product_ids": ["1001"]},
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["category_issues"] == []
    assert preview_data["items"][0]["target_category_id"] == 501
    assert preview_data["items"][0]["payload"]["type_id"] == 601
    assert preview_data["dictionary_issues"][0]["type"] == "brand"


def test_preview_builds_rich_wb_payload_from_ozon_source(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBRichTargetClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonRichProductClient())
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
            "source_marketplace": "ozon",
            "target_marketplace": "wb",
            "product_ids": ["2001"],
            "target_category_id": 77,
        },
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is True
    item = preview_data["items"][0]
    assert item["target_category_id"] == 77
    assert item["missing_required_attributes"] == []
    assert item["missing_critical_fields"] == []
    assert item["warnings"] == []
    assert item["payload"] == {
        "subjectID": 77,
        "variants": [
            {
                "vendorCode": "OZ-2001",
                "title": "Blue hoodie",
                "description": "Soft blue hoodie for everyday wear",
                "brand": "Acme",
                "mediaFiles": ["https://example.test/hoodie-1.jpg", "https://example.test/hoodie-2.jpg"],
                "characteristics": [
                    {"id": 10, "name": "Color", "value": ["Blue"]},
                    {"id": 11, "name": "Material", "value": ["Cotton"]},
                    {"id": 12, "name": "Country", "value": ["Turkey"]},
                    {"id": 13, "name": "Composition", "value": ["95% cotton, 5% elastane"]},
                ],
                "sizes": [
                    {
                        "techSize": "L",
                        "wbSize": "50",
                        "price": "3499",
                        "skus": ["4601234567890"],
                    }
                ],
            }
        ],
    }


def test_preview_warns_for_missing_wb_description_without_blocking_import(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBRichTargetClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonRichProductMissingDescriptionClient())
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
            "source_marketplace": "ozon",
            "target_marketplace": "wb",
            "product_ids": ["2001"],
            "target_category_id": 77,
        },
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is True
    assert preview_data["items"][0]["missing_critical_fields"] == []
    assert any("description" in warning.lower() for warning in preview_data["items"][0]["warnings"])


def test_preview_returns_wb_category_options_for_manual_mapping(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBCategoryOptionsClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonUnmappedCategoryByIdClient())
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
        json={"source_marketplace": "ozon", "target_marketplace": "wb", "product_ids": ["2001"]},
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is False
    assert preview_data["category_issues"] == [
        {
            "type": "category",
            "source_key": "ozon:59968946",
            "source_label": "Аппараты для маникюра и педикюра",
            "target_marketplace": "wb",
            "product_ids": ["2001"],
            "products": [{"id": "2001", "title": "Аппарат для маникюра и педикюра"}],
            "options": [
                {
                    "key": "wb:77",
                    "label": "Hoodies",
                    "path": "Hoodies",
                    "context": {"subject_id": 77},
                },
                {
                    "key": "wb:88",
                    "label": "Tops",
                    "path": "Tops",
                    "context": {"subject_id": 88},
                },
            ],
        }
    ]
    assert preview_data["items"][0]["payload"] == {
        "subjectID": 0,
        "variants": [
            {
                "vendorCode": "OZ-2001",
                "title": "Аппарат для маникюра и педикюра",
                "description": "Профессиональный аппарат",
                "brand": "Acme",
                "mediaFiles": ["https://example.test/device.jpg"],
                "characteristics": [],
                "sizes": [
                    {
                        "techSize": "0",
                        "wbSize": "",
                        "price": "3499",
                        "skus": [],
                    }
                ],
            }
        ],
    }


def test_launch_transfer_sends_wb_payload_for_ozon_source(tmp_path):
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
    wb_client = FakeWBRichTargetClient()
    app.state.container.client_factory.register_override(Marketplace.WB, wb_client)
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonRichProductClient())
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
        json={
            "source_marketplace": "ozon",
            "target_marketplace": "wb",
            "product_ids": ["2001"],
            "target_category_id": 77,
        },
    )
    assert launch_response.status_code == 200
    assert launch_response.json()["status"] == "submitted"
    assert wb_client.created_payloads == [
        [
            {
                "subjectID": 77,
                "variants": [
                    {
                        "vendorCode": "OZ-2001",
                        "title": "Blue hoodie",
                        "description": "Soft blue hoodie for everyday wear",
                        "brand": "Acme",
                        "mediaFiles": ["https://example.test/hoodie-1.jpg", "https://example.test/hoodie-2.jpg"],
                        "characteristics": [
                            {"id": 10, "name": "Color", "value": ["Blue"]},
                            {"id": 11, "name": "Material", "value": ["Cotton"]},
                            {"id": 12, "name": "Country", "value": ["Turkey"]},
                            {"id": 13, "name": "Composition", "value": ["95% cotton, 5% elastane"]},
                        ],
                        "sizes": [
                            {
                                "techSize": "L",
                                "wbSize": "50",
                                "price": "3499",
                                "skus": ["4601234567890"],
                            }
                        ],
                    }
                ],
            }
        ]
    ]


def test_saved_wb_category_mapping_resolves_preview_for_ozon_source(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBRichTargetClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonUnmappedCategoryByIdClient())
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

    save_response = client.post(
        "/api/v1/mappings/categories",
        headers=headers,
        json={
            "source_marketplace": "ozon",
            "target_marketplace": "wb",
            "items": [
                {
                    "type": "category",
                    "source_key": "ozon:59968946",
                    "source_label": "Аппараты для маникюра и педикюра",
                    "target_key": "wb:77",
                    "target_label": "Hoodies",
                    "target_context": {
                        "subject_id": 77,
                    },
                }
            ],
        },
    )
    assert save_response.status_code == 200

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={"source_marketplace": "ozon", "target_marketplace": "wb", "product_ids": ["2001"]},
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["category_issues"] == []
    assert preview_data["items"][0]["target_category_id"] == 77
    assert preview_data["items"][0]["target_category_name"] == "Hoodies"


class FakeYandexUnmappedCategorySourceClient(MarketplaceClient):
    async def list_products(self, credentials, *, limit: int = 50):
        return [
            ProductSummary(
                id="ym-1001",
                offer_id="YM-1001",
                title="Blue mug",
                category_id=77,
                category_name="Mugs",
                price="990",
                images=["https://example.test/mug.jpg"],
            )
        ]

    async def get_product_details(self, credentials, product_id: str):
        return ProductDetails(
            id=product_id,
            offer_id="YM-1001",
            title="Blue mug",
            description="Large ceramic mug",
            category_id=77,
            category_name="Mugs",
            price="990",
            images=["https://example.test/mug.jpg"],
            attributes={"Color": ["Blue"]},
            brand="Acme",
        )

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(id=10, name="Home", parent_id=None, raw={"path": "Home"}),
            CategoryNode(id=77, name="Mugs", parent_id=10, raw={"path": "Home > Mugs"}),
        ]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return []

    async def create_products(self, credentials, items):
        return {"external_task_id": "ym-task"}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed"}


class FakeYandexTargetCategoryClient(MarketplaceClient):
    async def list_products(self, credentials, *, limit: int = 50):
        return []

    async def get_product_details(self, credentials, product_id: str):
        raise AssertionError("Not used in this test")

    async def list_categories(self, credentials, *, parent_id: int | None = None):
        return [
            CategoryNode(id=100, name="Kitchen", parent_id=None, raw={"path": "Kitchen"}),
            CategoryNode(id=700, name="Mugs", parent_id=100, raw={"path": "Kitchen > Drinkware > Mugs"}),
        ]

    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return [
            CategoryAttribute(
                id=501,
                name="Brand",
                required=True,
                type="ENUM",
                dictionary_values=[
                    {"id": 11, "value": "Acme"},
                    {"id": 12, "value": "Contoso"},
                ],
            )
        ]

    async def create_products(self, credentials, items):
        return {"external_task_id": "ym-task"}

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {"status": "completed"}


class FakeYandexImportLifecycleClient(FakeYandexTargetCategoryClient):
    def __init__(self) -> None:
        self.created_items = []
        self.status_calls = 0

    async def create_products(self, credentials, items):
        self.created_items.append(items)
        return {
            "status": "submitted",
            "external_task_id": "SKU-1001",
            "submitted_count": len(items),
            "items": [{"offer_id": "SKU-1001", "status": "submitted"}],
        }

    async def get_import_status(self, credentials, external_task_id: str | None):
        self.status_calls += 1
        if self.status_calls == 1:
            return {
                "status": "processing",
                "processed_count": 1,
                "completed_count": 0,
                "failed_count": 0,
                "errors": [],
                "items": [{"offer_id": "SKU-1001", "status": "processing", "notes": []}],
            }
        return {
            "status": "completed",
            "processed_count": 1,
            "completed_count": 1,
            "failed_count": 0,
            "errors": [],
            "items": [{"offer_id": "SKU-1001", "status": "ready", "notes": []}],
        }


class FakeYandexFailedImportStatusClient(FakeYandexTargetCategoryClient):
    async def create_products(self, credentials, items):
        return {
            "status": "submitted",
            "external_task_id": "SKU-1001",
            "submitted_count": len(items),
            "items": [{"offer_id": "SKU-1001", "status": "submitted"}],
        }

    async def get_import_status(self, credentials, external_task_id: str | None):
        return {
            "status": "failed",
            "processed_count": 1,
            "completed_count": 0,
            "failed_count": 1,
            "errors": [{"message": "Missing certificate"}],
            "items": [{"offer_id": "SKU-1001", "status": "failed", "notes": ["Missing certificate"]}],
        }


class FakeYandexTargetCategoryWithMissingBrandClient(FakeYandexTargetCategoryClient):
    async def get_category_attributes(self, credentials, category_id: int, *, required_only: bool = False):
        return [
            CategoryAttribute(
                id=501,
                name="Brand",
                required=True,
                type="ENUM",
                dictionary_values=[
                    {"id": 11, "value": "Acme"},
                    {"id": 12, "value": "Contoso"},
                ],
            ),
            CategoryAttribute(
                id=777,
                name="Country",
                required=True,
                type="STRING",
            ),
        ]


class FakeWBNoImagesClient(FakeWBClient):
    async def list_products(self, credentials, *, limit: int = 50):
        return [
            ProductSummary(
                id="1001",
                offer_id="SKU-1001",
                title="Red t-shirt",
                category_id=10,
                category_name="T-shirts",
                price="1999",
                images=[],
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
            images=[],
            attributes={"Color": ["Red"], "Material": ["Cotton"]},
            dimensions={"height": 10, "width": 20, "depth": 30, "weight": 400},
            sizes=[{"techSize": "L", "wbSize": "48"}],
            brand="Acme",
        )


def test_preview_returns_category_issues_for_yandex_source(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, FakeYandexUnmappedCategorySourceClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonNoAutoCategoryClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )
    client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={"source_marketplace": "yandex_market", "target_marketplace": "ozon", "product_ids": ["ym-1001"]},
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is False
    assert preview_data["category_issues"][0]["source_key"] == "yandex_market:77"
    assert preview_data["category_issues"][0]["source_label"] == "Mugs"


def test_saved_category_mapping_resolves_preview_for_yandex_source(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, FakeYandexUnmappedCategorySourceClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonStrictBrandClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )
    client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )

    save_response = client.post(
        "/api/v1/mappings/categories",
        headers=headers,
        json={
            "source_marketplace": "yandex_market",
            "target_marketplace": "ozon",
            "items": [
                {
                    "type": "category",
                    "source_key": "yandex_market:77",
                    "source_label": "Mugs",
                    "target_key": "ozon:501",
                    "target_label": "T-shirts",
                    "target_context": {"description_category_id": 501, "type_id": 601, "type_name": "T-shirt"},
                }
            ],
        },
    )
    assert save_response.status_code == 200

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={"source_marketplace": "yandex_market", "target_marketplace": "ozon", "product_ids": ["ym-1001"]},
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["category_issues"] == []
    assert preview_data["items"][0]["target_category_id"] == 501


def test_save_dictionary_mapping_accepts_yandex_market_target(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, FakeYandexTargetCategoryClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )

    save_response = client.post(
        "/api/v1/mappings/dictionary",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "yandex_market",
            "items": [
                {
                    "type": "brand",
                    "source_value": "Acme",
                    "target_category_id": 700,
                    "target_attribute_id": 501,
                    "target_dictionary_value_id": 11,
                    "target_dictionary_value": "Acme",
                }
            ],
        },
    )
    assert save_response.status_code == 200
    assert save_response.json()[0]["target_dictionary_value_id"] == 11


def test_preview_builds_yandex_target_payload_from_wb_source(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, FakeYandexTargetCategoryClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "yandex_market",
            "product_ids": ["1001"],
            "target_category_id": 700,
        },
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is True
    item = preview_data["items"][0]
    assert item["readiness"] == "ready"
    assert item["target_category_id"] == 700
    assert item["payload"] == {
        "marketCategoryId": 700,
        "offer": {
            "shopSku": "SKU-1001",
            "name": "Red t-shirt",
            "description": "Basic cotton t-shirt",
            "vendor": "Acme",
            "pictures": ["https://example.test/image-1.jpg"],
        },
        "parameterValues": [
            {
                "parameterId": 501,
                "values": [
                    {
                        "value": "Acme",
                        "optionId": 11,
                    }
                ],
            }
        ],
    }


def test_preview_blocks_yandex_target_when_required_attribute_missing(tmp_path):
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
    app.state.container.client_factory.register_override(
        Marketplace.YANDEX_MARKET,
        FakeYandexTargetCategoryWithMissingBrandClient(),
    )
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "yandex_market",
            "product_ids": ["1001"],
            "target_category_id": 700,
        },
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is False
    item = preview_data["items"][0]
    assert item["readiness"] == "blocked"
    assert item["missing_required_attributes"] == ["Country"]


def test_preview_marks_unmapped_yandex_source_as_needs_mapping(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, FakeYandexUnmappedCategorySourceClient())
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonNoAutoCategoryClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )
    client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={"source_marketplace": "yandex_market", "target_marketplace": "ozon", "product_ids": ["ym-1001"]},
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["items"][0]["readiness"] == "needs_mapping"


def test_preview_builds_yandex_target_payload_from_ozon_source(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonRichProductClient())
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, FakeYandexTargetCategoryClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/ozon",
        headers=headers,
        json={"marketplace": "ozon", "client_id": "cid", "api_key": "apikey"},
    )
    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "ozon",
            "target_marketplace": "yandex_market",
            "product_ids": ["2001"],
            "target_category_id": 700,
        },
    )
    assert preview_response.status_code == 200
    preview_data = preview_response.json()
    assert preview_data["ready_to_import"] is True
    item = preview_data["items"][0]
    assert item["readiness"] == "ready"
    assert item["payload"]["marketCategoryId"] == 700
    assert item["payload"]["offer"]["shopSku"] == "OZ-2001"
    assert item["payload"]["offer"]["pictures"] == ["https://example.test/hoodie-1.jpg", "https://example.test/hoodie-2.jpg"]


def test_preview_preserves_media_for_yandex_source_to_wb(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, FakeYandexUnmappedCategorySourceClient())
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBRichTargetClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )
    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "yandex_market",
            "target_marketplace": "wb",
            "product_ids": ["ym-1001"],
            "target_category_id": 77,
        },
    )
    assert preview_response.status_code == 200
    payload = preview_response.json()["items"][0]["payload"]
    assert payload["variants"][0]["mediaFiles"] == ["https://example.test/mug.jpg"]


def test_preview_warns_when_yandex_target_has_no_source_images(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBNoImagesClient())
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, FakeYandexTargetCategoryClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )

    preview_response = client.post(
        "/api/v1/transfers/preview",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "yandex_market",
            "product_ids": ["1001"],
            "target_category_id": 700,
        },
    )
    assert preview_response.status_code == 200
    item = preview_response.json()["items"][0]
    assert item["readiness"] == "ready"
    assert item["payload"]["offer"]["pictures"] == []
    assert any("изображ" in warning.lower() for warning in item["warnings"])
def test_launch_and_sync_transfer_for_yandex_target(tmp_path):
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
    yandex_client = FakeYandexImportLifecycleClient()
    app.state.container.client_factory.register_override(Marketplace.WB, FakeWBClient())
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, yandex_client)
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )

    launch_response = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "yandex_market",
            "product_ids": ["1001"],
            "target_category_id": 700,
        },
    )
    assert launch_response.status_code == 200
    job = launch_response.json()
    assert job["status"] == "submitted"
    assert job["external_task_id"] == "SKU-1001"
    assert yandex_client.created_items[0][0]["offer"]["pictures"] == ["https://example.test/image-1.jpg"]

    processing_response = client.post(f"/api/v1/transfers/{job['id']}/sync", headers=headers)
    assert processing_response.status_code == 200
    assert processing_response.json()["status"] == "processing"

    completed_response = client.post(f"/api/v1/transfers/{job['id']}/sync", headers=headers)
    assert completed_response.status_code == 200
    completed_job = completed_response.json()
    assert completed_job["status"] == "completed"
    assert completed_job["result"]["completed_count"] == 1
    assert completed_job["result"]["items"][0]["status"] == "ready"


def test_sync_transfer_marks_failed_yandex_target_job_and_surfaces_error(tmp_path):
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
    app.state.container.client_factory.register_override(Marketplace.YANDEX_MARKET, FakeYandexFailedImportStatusClient())
    client = TestClient(app)
    headers = auth_headers(client)

    client.put(
        "/api/v1/connections/wb",
        headers=headers,
        json={"marketplace": "wb", "token": "wb-secret-token"},
    )
    client.put(
        "/api/v1/connections/yandex_market",
        headers=headers,
        json={"marketplace": "yandex_market", "token": "ym-token", "business_id": 321, "campaign_id": 654},
    )

    launch_response = client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_marketplace": "wb",
            "target_marketplace": "yandex_market",
            "product_ids": ["1001"],
            "target_category_id": 700,
        },
    )
    assert launch_response.status_code == 200
    job = launch_response.json()

    sync_response = client.post(f"/api/v1/transfers/{job['id']}/sync", headers=headers)
    assert sync_response.status_code == 200
    synced_job = sync_response.json()
    assert synced_job["status"] == "failed"
    assert synced_job["error_message"] == "Missing certificate"
