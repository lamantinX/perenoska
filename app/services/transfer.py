from __future__ import annotations

import asyncio
import base64
import json
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from app.clients.base import use_trace_context
from app.schemas import (
    CategoryNode,
    JobStatus,
    Marketplace,
    PreviewItemReadiness,
    TransferJobResponse,
    TransferLaunchRequest,
    TransferPreviewItem,
    TransferPreviewRequest,
    TransferPreviewResponse,
)
from app.services.catalog import CatalogService
from app.services.category_mapper import CategoryMapper, MappingResult, _flatten_categories
from app.services.connections import ConnectionService
from app.services.container import MarketplaceClientFactory
from app.services.mapping import MappingService


SENSITIVE_TRACE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "client_id",
    "token",
    "access_token",
    "refresh_token",
}


def mask_trace_payload(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_TRACE_KEYS:
                masked[key] = "***"
            else:
                masked[key] = mask_trace_payload(item)
        return masked
    if isinstance(value, list):
        return [mask_trace_payload(item) for item in value]
    return value


class TransferTraceContext:
    def __init__(
        self,
        *,
        database,
        base_token: str | None = None,
        source_marketplace: str | None = None,
        target_marketplace: str | None = None,
        job_id: int | None = None,
    ) -> None:
        self.database = database
        self.base_token = base_token or secrets.token_urlsafe(6).replace("-", "").replace("_", "")
        self.source_marketplace = source_marketplace
        self.target_marketplace = target_marketplace
        self.job_id = job_id
        self._sequence_no = 0

    def next_token(self) -> str:
        self._sequence_no += 1
        return f"{self.base_token}_{self._sequence_no}"

    def log_event(
        self,
        *,
        event_type: str,
        operation: str,
        request_url: str,
        request_headers: dict[str, Any] | None = None,
        request_body: Any = None,
        response_headers: dict[str, Any] | None = None,
        response_body: Any = None,
        status_code: int | None = None,
        duration_ms: int | None = None,
        error_text: str | None = None,
        job_id: int | None = None,
    ) -> dict[str, Any]:
        token = self.next_token()
        return self.database.create_transfer_log(
            created_at=datetime.now(UTC).isoformat(),
            base_token=self.base_token,
            sequence_no=self._sequence_no,
            token=token,
            event_type=event_type,
            operation=operation,
            request_url=request_url,
            request_headers=mask_trace_payload(request_headers or {}),
            request_body=mask_trace_payload(request_body),
            response_headers=mask_trace_payload(response_headers or {}),
            response_body=mask_trace_payload(response_body),
            source_marketplace=self.source_marketplace,
            target_marketplace=self.target_marketplace,
            job_id=job_id if job_id is not None else self.job_id,
            status_code=status_code,
            duration_ms=duration_ms,
            error_text=error_text,
        )


class TransferService:
    def __init__(
        self,
        *,
        database,
        connection_service: ConnectionService,
        catalog_service: CatalogService,
        client_factory: MarketplaceClientFactory,
        mapping_service: MappingService,
        category_mapper: CategoryMapper | None = None,
    ) -> None:
        self.database = database
        self.connection_service = connection_service
        self.catalog_service = catalog_service
        self.client_factory = client_factory
        self.mapping_service = mapping_service
        self.category_mapper = category_mapper

    async def preview(
        self,
        user_id: int,
        payload: TransferPreviewRequest,
        trace: TransferTraceContext | None = None,
    ) -> TransferPreviewResponse:
        trace = trace or TransferTraceContext(
            database=self.database,
            source_marketplace=payload.source_marketplace.value,
            target_marketplace=payload.target_marketplace.value,
        )
        trace.log_event(
            event_type="function",
            operation="transfer.preview.start",
            request_url="function://transfer/preview",
            request_body=payload.model_dump(mode="json"),
        )
        with use_trace_context(trace):
            source_categories = await self.catalog_service.list_categories(user_id, payload.source_marketplace)
            target_categories = await self.catalog_service.list_categories(user_id, payload.target_marketplace)
            source_categories_by_id = {item.id: item for item in source_categories}
            target_credentials = self.connection_service.get_credentials(user_id, payload.target_marketplace)
            target_client = self.client_factory.get_client(payload.target_marketplace)
            source_connection = self.database.get_connection(user_id, payload.source_marketplace.value)
            target_connection = self.database.get_connection(user_id, payload.target_marketplace.value)
            saved_dictionary_mappings: dict[str, dict] = {}
            saved_category_mappings: dict[str, dict] = {}
            if source_connection and target_connection:
                saved_dictionary_mappings = {
                    str(item["source_key"]).partition(":")[2]: item
                    for item in self.database.list_mappings(
                        source_connection_id=source_connection["id"],
                        target_connection_id=target_connection["id"],
                        mapping_type="dictionary_brand",
                    )
                }
                saved_category_mappings = {
                    item["source_key"]: item
                    for item in self.database.list_mappings(
                        source_connection_id=source_connection["id"],
                        target_connection_id=target_connection["id"],
                        mapping_type="category",
                    )
                }

            preview_items: list[TransferPreviewItem] = []
            dictionary_issues: list[dict] = []
            brand_mapping_index: dict[str, dict] = {}
            category_issue_index: dict[str, dict] = {}
            target_categories_by_id = {item.id: item for item in target_categories}
            category_attributes_cache: dict[tuple[int, int | None, bool], list] = {}
            dictionary_options_cache: dict[tuple[int, int, int], list[dict]] = {}
            semaphore = asyncio.Semaphore(4)
            ozon_flat = _flatten_categories(target_categories) if self.category_mapper else []

            async def build_preview_item(product_id: str) -> tuple[TransferPreviewItem, list[dict], dict | None, dict | None]:
                async with semaphore:
                    product = await self.catalog_service.get_product_details(user_id, payload.source_marketplace, product_id)
                product = self._apply_product_overrides(product, payload.product_overrides.get(product_id) or {})

                if payload.target_category_id is not None:
                    target_category = target_categories_by_id.get(payload.target_category_id)
                else:
                    target_category = self._resolve_saved_category_mapping(
                        product,
                        payload.source_marketplace,
                        target_categories,
                        saved_category_mappings,
                    )
                    if target_category is None:
                        target_category = self.mapping_service.auto_match_category(product, target_categories)

                # Try CategoryMapper (fuzzy/embedding/LLM) as additional fallback
                auto_mapping_result: MappingResult | None = None
                if target_category is None and self.category_mapper and product.category_name:
                    wb_node = CategoryNode(
                        id=product.category_id or 0,
                        name=product.category_name or product.title,
                    )
                    auto_mapping_result = await self.category_mapper.map_category(
                        wb_node, ozon_flat, wb_path=product.category_name or "",
                    )
                    if auto_mapping_result.confidence >= self.category_mapper.settings.catmatch_llm_min:
                        target_category = target_categories_by_id.get(auto_mapping_result.ozon_id)

                warnings: list[str] = []
                price_scope_warning = self._wb_price_scope_warning(user_id, payload.source_marketplace, product.price)
                if price_scope_warning:
                    warnings.append(price_scope_warning)
                if target_category is None:
                    warnings.append("Не удалось автоматически подобрать целевую категорию.")
                    issue = self._category_issue_payload(
                        product=product,
                        source_marketplace=payload.source_marketplace.value,
                        source_categories_by_id=source_categories_by_id,
                        target_marketplace=payload.target_marketplace.value,
                        target_categories=target_categories,
                    )
                    if auto_mapping_result and auto_mapping_result.alternatives:
                        issue["suggestions"] = auto_mapping_result.alternatives
                    return (
                        TransferPreviewItem(
                            product_id=product.id,
                            title=product.title,
                            readiness=PreviewItemReadiness.NEEDS_MAPPING,
                            source_category_id=product.category_id,
                            payload=self._preview_source_payload(product, payload.target_marketplace),
                            warnings=warnings,
                        ),
                        [],
                        issue,
                        None,
                    )

                target_category = self._resolve_target_category_context(
                    target_category=target_category,
                    source_product=product,
                    target_marketplace=payload.target_marketplace,
                    target_client=target_client,
                )
                required_only = payload.target_marketplace == Marketplace.OZON
                cache_key = (
                    int(target_category.id),
                    self.mapping_service._resolve_ozon_type_id(target_category),
                    required_only,
                )
                if cache_key not in category_attributes_cache:
                    async with semaphore:
                        category_attributes_cache[cache_key] = await self.catalog_service.get_category_attributes_for_category(
                            user_id,
                            payload.target_marketplace,
                            target_category,
                            source_product=product,
                            required_only=required_only,
                        )
                target_attributes = category_attributes_cache[cache_key]
                (
                    import_payload,
                    mapped_attributes,
                    missing_required,
                    missing_critical,
                    mapping_warnings,
                    item_dictionary_issues,
                ) = self.mapping_service.build_import_payload(
                    source_product=product,
                    target_category=target_category,
                    target_attributes=target_attributes,
                    target_marketplace=payload.target_marketplace.value,
                    saved_dictionary_mappings=saved_dictionary_mappings,
                    trace=trace,
                )
                warnings.extend(mapping_warnings)
                if payload.target_marketplace == Marketplace.OZON and item_dictionary_issues:
                    await self._populate_dictionary_issue_options(
                        target_client=target_client,
                        target_credentials=target_credentials,
                        target_category=target_category,
                        issues=item_dictionary_issues,
                        cache=dictionary_options_cache,
                        semaphore=semaphore,
                    )
                brand_mapping = self._brand_mapping_payload(
                    product=product,
                    target_category=target_category,
                    target_attributes=target_attributes,
                    item_dictionary_issues=item_dictionary_issues,
                    saved_dictionary_mappings=saved_dictionary_mappings,
                )
                if payload.target_marketplace == Marketplace.OZON and brand_mapping is not None:
                    await self._populate_dictionary_issue_options(
                        target_client=target_client,
                        target_credentials=target_credentials,
                        target_category=target_category,
                        issues=[brand_mapping],
                        cache=dictionary_options_cache,
                        semaphore=semaphore,
                    )
                return (
                    TransferPreviewItem(
                        product_id=product.id,
                        title=product.title,
                        readiness=self._preview_item_readiness(
                            target_category_id=target_category.id,
                            missing_required=missing_required,
                            missing_critical=missing_critical,
                            dictionary_issues=item_dictionary_issues,
                        ),
                        source_category_id=product.category_id,
                        target_category_id=target_category.id,
                        target_category_name=target_category.name,
                        payload=import_payload,
                        mapped_attributes=mapped_attributes,
                        missing_required_attributes=missing_required,
                        missing_critical_fields=missing_critical,
                        warnings=warnings,
                        dictionary_issues=item_dictionary_issues,
                    ),
                    item_dictionary_issues,
                    None,
                    brand_mapping,
                )

            results = await asyncio.gather(*(build_preview_item(product_id) for product_id in payload.product_ids))
            for preview_item, item_dictionary_issues, category_issue, brand_mapping in results:
                preview_items.append(preview_item)
                dictionary_issues.extend(item_dictionary_issues)
                if brand_mapping is not None:
                    brand_mapping_index.setdefault(brand_mapping["source_value_normalized"], brand_mapping)
                if category_issue is None:
                    continue
                source_key = category_issue["source_key"]
                if source_key not in category_issue_index:
                    category_issue_index[source_key] = category_issue
                    continue
                category_issue_index[source_key]["product_ids"].extend(category_issue["product_ids"])
                category_issue_index[source_key]["products"].extend(category_issue["products"])

            ready = all(item.readiness == PreviewItemReadiness.READY for item in preview_items)
            response = TransferPreviewResponse(
                source_marketplace=payload.source_marketplace,
                target_marketplace=payload.target_marketplace,
                ready_to_import=ready,
                items=preview_items,
                dictionary_issues=dictionary_issues,
                brand_mappings=list(brand_mapping_index.values()),
                category_issues=list(category_issue_index.values()),
            )
        trace.log_event(
            event_type="function",
            operation="transfer.preview.result",
            request_url="function://transfer/preview",
            response_body=response.model_dump(mode="json"),
        )
        return response

    @staticmethod
    def _preview_source_payload(product, target_marketplace: Marketplace) -> dict:
        if target_marketplace == Marketplace.WB:
            return {
                "subjectID": 0,
                "variants": [
                    {
                        "vendorCode": product.offer_id or "",
                        "title": product.title,
                        "description": product.description or "",
                        "brand": product.brand or "",
                        "mediaFiles": list(product.images or []),
                        "characteristics": [],
                        "sizes": [
                            {
                                "techSize": "0",
                                "wbSize": "",
                                "price": product.price or "",
                                "skus": list(product.barcode_list or []),
                            }
                        ],
                    }
                ],
            }
        if target_marketplace == Marketplace.OZON:
            payload = {
                "name": product.title,
                "description": product.description or "",
                "price": product.price or "",
                "images": list(product.images or []),
                "offer_id": product.offer_id or "",
                "attributes": [],
            }
            if product.brand:
                payload["attributes"].append({"name": "Бренд", "value": [product.brand]})
            return payload
        return {
            "offer": {
                "shopSku": product.offer_id or "",
                "name": product.title,
                "description": product.description or "",
                "vendor": product.brand or "",
                "pictures": list(product.images or []),
            }
        }

    @staticmethod
    def _preview_item_readiness(
        *,
        target_category_id: int | None,
        missing_required: list[str],
        missing_critical: list[str],
        dictionary_issues: list[dict],
    ) -> PreviewItemReadiness:
        if target_category_id is None or dictionary_issues:
            return PreviewItemReadiness.NEEDS_MAPPING
        if missing_required or missing_critical:
            return PreviewItemReadiness.BLOCKED
        return PreviewItemReadiness.READY

    def _resolve_saved_category_mapping(
        self,
        product,
        source_marketplace: Marketplace,
        target_categories: list,
        saved_category_mappings: dict[str, dict],
    ):
        saved = saved_category_mappings.get(self._source_category_key(product, source_marketplace))
        if not saved:
            return None
        target_context = json.loads(saved["target_context_json"])
        category_id = int(
            target_context.get("description_category_id")
            or target_context.get("market_category_id")
            or target_context.get("category_id")
            or target_context.get("subject_id")
            or str(saved.get("target_key") or "").partition(":")[2]
            or 0
        )
        if not category_id:
            return None
        category = next((item for item in target_categories if item.id == category_id), None)
        if category is None:
            return None
        return self._clone_category_with_context(
            category,
            resolved_type_id=target_context.get("type_id"),
            resolved_type_name=target_context.get("type_name"),
        )

    def _category_issue_payload(
        self,
        *,
        product,
        source_marketplace: str,
        source_categories_by_id: dict[int, object],
        target_marketplace: str,
        target_categories: list,
    ) -> dict:
        source_key = self._source_category_key(product, Marketplace(source_marketplace))
        return {
            "type": "category",
            "source_key": source_key,
            "source_label": self._source_category_label(product, source_categories_by_id),
            "target_marketplace": target_marketplace,
            "product_ids": [product.id],
            "products": [{"id": product.id, "title": product.title}],
            "options": self._category_issue_options(target_marketplace, target_categories),
        }

    def _resolve_target_category_context(
        self,
        *,
        target_category: CategoryNode,
        source_product,
        target_marketplace: Marketplace,
        target_client,
    ) -> CategoryNode:
        if target_marketplace != Marketplace.OZON:
            return target_category
        resolve_category_context = getattr(target_client, "resolve_category_context", None)
        if not callable(resolve_category_context):
            return self._clone_category_with_context(target_category)
        context = resolve_category_context(target_category, source_product=source_product) or {}
        return self._clone_category_with_context(
            target_category,
            resolved_type_id=context.get("type_id"),
            resolved_type_name=context.get("type_name"),
        )

    @staticmethod
    def _clone_category_with_context(
        category: CategoryNode,
        *,
        resolved_type_id: int | None = None,
        resolved_type_name: str | None = None,
    ) -> CategoryNode:
        raw = dict(category.raw or {})
        if resolved_type_id:
            raw["_resolved_type_id"] = int(resolved_type_id)
        if resolved_type_name:
            raw["_resolved_type_name"] = str(resolved_type_name)
        return category.model_copy(deep=True, update={"raw": raw})

    def _category_issue_options(self, target_marketplace: str, target_categories: list) -> list[dict]:
        options: list[dict] = []
        if target_marketplace == Marketplace.OZON.value:
            for category in target_categories:
                children = [child for child in category.raw.get("children") or [] if child.get("type_id") and not child.get("disabled")]
                options.append(
                    {
                        "key": f"ozon:{category.id}",
                        "label": category.name,
                        "path": category.name,
                        "context": {
                            "description_category_id": category.id,
                            "types": [{"id": int(child["type_id"]), "name": str(child.get("type_name") or child["type_id"])} for child in children],
                        },
                    }
                )
            return options
        if target_marketplace == Marketplace.WB.value:
            for category in target_categories:
                options.append(
                    {
                        "key": f"wb:{category.id}",
                        "label": category.name,
                        "path": category.name,
                        "context": {"subject_id": category.id},
                    }
                )
            return options
        if target_marketplace == Marketplace.YANDEX_MARKET.value:
            category_index = {category.id: category for category in target_categories}

            def category_path(category) -> str:
                raw_path = str((category.raw or {}).get("path") or "").strip()
                if raw_path:
                    return raw_path
                parts = [category.name]
                parent_id = category.parent_id
                while parent_id:
                    parent = category_index.get(parent_id)
                    if parent is None:
                        break
                    parts.append(parent.name)
                    parent_id = parent.parent_id
                return " > ".join(reversed(parts))

            for category in target_categories:
                options.append(
                    {
                        "key": f"yandex_market:{category.id}",
                        "label": category.name,
                        "path": category_path(category),
                        "context": {"market_category_id": category.id, "category_id": category.id},
                    }
                )
        return options

    def _brand_mapping_payload(
        self,
        *,
        product,
        target_category,
        target_attributes: list,
        item_dictionary_issues: list[dict],
        saved_dictionary_mappings: dict[str, dict],
    ) -> dict | None:
        brand_issue = next((issue for issue in item_dictionary_issues if issue.get("type") == "brand"), None)
        if brand_issue is not None:
            return dict(brand_issue) | {
                "selected_dictionary_value_id": None,
                "selected_dictionary_value": None,
            }

        brand_attribute = next(
            (
                attribute
                for attribute in target_attributes
                if self.mapping_service._is_brand_attribute(attribute)
                and self.mapping_service._requires_ozon_dictionary_match(attribute)
            ),
            None,
        )
        if brand_attribute is None or not product.brand:
            return None

        source_value = str(product.brand).strip()
        normalized_source = self.mapping_service._normalize(source_value)
        saved_value = saved_dictionary_mappings.get(normalized_source)
        selected_dictionary_value_id = None
        selected_dictionary_value = None
        if saved_value is not None:
            target_context = json.loads(saved_value.get("target_context_json") or "{}")
            selected_dictionary_value_id = int(target_context.get("target_dictionary_value_id") or 0) or None
            selected_dictionary_value = str(target_context.get("target_dictionary_value") or saved_value.get("target_label") or "")

        return {
            "type": "brand",
            "product_id": product.id,
            "source_value": source_value,
            "source_value_normalized": normalized_source,
            "target_category_id": target_category.id,
            "target_attribute_id": brand_attribute.id,
            "target_attribute_name": brand_attribute.name,
            "selected_dictionary_value_id": selected_dictionary_value_id,
            "selected_dictionary_value": selected_dictionary_value or None,
            "options": [
                {
                    "id": item.get("id") or item.get("dictionary_value_id") or 0,
                    "value": str(item.get("value") or item.get("name") or ""),
                }
                for item in brand_attribute.dictionary_values
            ],
        }

    @staticmethod
    def _source_category_key(product, source_marketplace: Marketplace) -> str:
        if product.category_id is not None:
            return f"{source_marketplace.value}:{product.category_id}"
        return f"{source_marketplace.value}-name:{(product.category_name or '').strip().lower()}"

    @staticmethod
    def _source_category_label(product, source_categories_by_id: dict[int, object]) -> str:
        if product.category_name and str(product.category_name).strip():
            category_name = str(product.category_name).strip()
            if product.category_id is None or category_name != str(product.category_id):
                return category_name
        if product.category_id is not None:
            source_category = source_categories_by_id.get(product.category_id)
            if source_category is not None and getattr(source_category, "name", None):
                return str(source_category.name)
        if product.category_name:
            return str(product.category_name)
        return str(product.category_id or "Без категории")

    async def _populate_dictionary_issue_options(
        self,
        *,
        target_client,
        target_credentials: dict,
        target_category: object,
        issues: list[dict],
        cache: dict[tuple[int, int, int], list[dict]] | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        get_dictionary_values = getattr(target_client, "get_dictionary_values", None)
        if not callable(get_dictionary_values):
            return

        resolved_type_id = self.mapping_service._resolve_ozon_type_id(target_category)
        if not resolved_type_id:
            return

        for issue in issues:
            if issue.get("options"):
                continue
            cache_key = (int(target_category.id), int(resolved_type_id), int(issue["target_attribute_id"]))
            if cache is None or cache_key not in cache:
                if semaphore is None:
                    options = await get_dictionary_values(
                        target_credentials,
                        attribute_id=int(issue["target_attribute_id"]),
                        description_category_id=int(target_category.id),
                        type_id=int(resolved_type_id),
                        search=None,
                        limit=100,
                    )
                else:
                    async with semaphore:
                        options = await get_dictionary_values(
                            target_credentials,
                            attribute_id=int(issue["target_attribute_id"]),
                            description_category_id=int(target_category.id),
                            type_id=int(resolved_type_id),
                            search=None,
                            limit=100,
                        )
                normalized_options = [
                    {
                        "id": int(option.get("id") or 0),
                        "value": str(option.get("value") or ""),
                    }
                    for option in options
                    if option.get("id") and option.get("value")
                ]
                if cache is None:
                    issue["options"] = normalized_options
                    continue
                cache[cache_key] = normalized_options
            issue["options"] = list(cache[cache_key])

    def _apply_product_overrides(self, product, overrides: dict) -> object:
        if not overrides:
            return product
        normalized = {}
        if overrides.get("price") not in {None, ""}:
            normalized["price"] = str(overrides["price"]).strip()
        if overrides.get("stock") not in {None, ""}:
            normalized["stock"] = int(overrides["stock"])
        if overrides.get("brand") not in {None, ""}:
            normalized["brand"] = str(overrides["brand"]).strip()
        if overrides.get("title") not in {None, ""}:
            normalized["title"] = str(overrides["title"]).strip()
        if overrides.get("offer_id") not in {None, ""}:
            normalized["offer_id"] = str(overrides["offer_id"]).strip()
        return product.model_copy(update=normalized) if normalized else product

    def _wb_price_scope_warning(self, user_id: int, source_marketplace: Marketplace, price: str | None) -> str | None:
        if source_marketplace != Marketplace.WB or price:
            return None
        try:
            credentials = self.connection_service.get_credentials(user_id, Marketplace.WB)
            scope = self._extract_wb_scope(credentials.get("token") or "")
        except Exception:
            return None
        if scope is None or scope & 4:
            return None
        return "Цена WB недоступна: текущий token не имеет доступа к API цен и скидок. Нужен новый WB token с price-scope."

    @staticmethod
    def _extract_wb_scope(token: str) -> int | None:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        try:
            data = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
        except Exception:
            return None
        scope = data.get("s")
        return int(scope) if isinstance(scope, int) else None

    async def launch(self, user_id: int, payload: TransferLaunchRequest) -> TransferJobResponse:
        trace = TransferTraceContext(
            database=self.database,
            source_marketplace=payload.source_marketplace.value,
            target_marketplace=payload.target_marketplace.value,
        )
        trace.log_event(
            event_type="function",
            operation="transfer.launch.start",
            request_url="function://transfer/launch",
            request_body=payload.model_dump(mode="json"),
        )
        preview = await self.preview(user_id, payload, trace=trace)
        if not preview.ready_to_import:
            detail = "Не все товары готовы к импорту. Сначала исправьте preview."
            if preview.category_issues:
                detail = "Не все категории сопоставлены. Сначала сохраните сопоставления категорий."
            elif any(issue.get("type") == "brand" for issue in preview.dictionary_issues):
                detail = "Не все бренды сопоставлены для Ozon. Сначала сохраните сопоставления брендов."
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )

        now = datetime.now(UTC).isoformat()
        job = self.database.create_transfer_job(
            user_id=user_id,
            source_marketplace=payload.source_marketplace.value,
            target_marketplace=payload.target_marketplace.value,
            status=JobStatus.PENDING.value,
            payload=preview.model_dump(),
            result={},
            created_at=now,
        )
        target_credentials = self.connection_service.get_credentials(user_id, payload.target_marketplace)
        target_client = self.client_factory.get_client(payload.target_marketplace)
        items = [item.payload for item in preview.items]

        with use_trace_context(trace):
            try:
                result = await target_client.create_products(target_credentials, items)
                job = self.database.update_transfer_job(
                    job_id=job["id"],
                    status=JobStatus.SUBMITTED.value,
                    updated_at=datetime.now(UTC).isoformat(),
                    external_task_id=result.get("external_task_id") or None,
                    result=result,
                )
            except Exception as error:
                job = self.database.update_transfer_job(
                    job_id=job["id"],
                    status=JobStatus.FAILED.value,
                    updated_at=datetime.now(UTC).isoformat(),
                    error_message=str(error),
                    result={"error": str(error)},
                )
        response = self._job_response(job)
        trace.log_event(
            event_type="function",
            operation="transfer.launch.result",
            request_url="function://transfer/launch",
            response_body=response.model_dump(mode="json"),
            job_id=job["id"],
            error_text=job.get("error_message"),
        )
        return response

    async def sync_status(self, user_id: int, job_id: int) -> TransferJobResponse:
        job = self.database.get_transfer_job(user_id, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")
        if not job.get("external_task_id") and job.get("status") == JobStatus.FAILED.value:
            return self._job_response(job)
        target_marketplace = Marketplace(job["target_marketplace"])
        target_credentials = self.connection_service.get_credentials(user_id, target_marketplace)
        target_client = self.client_factory.get_client(target_marketplace)
        result = await target_client.get_import_status(target_credentials, job.get("external_task_id"))

        remote_status = str(result.get("status") or "").lower()
        if remote_status in {"completed", "success", "done"}:
            status_value = JobStatus.COMPLETED.value
        elif remote_status in {"failed", "error", "unknown"}:
            status_value = JobStatus.FAILED.value
        else:
            status_value = JobStatus.PROCESSING.value

        job = self.database.update_transfer_job(
            job_id=job_id,
            status=status_value,
            updated_at=datetime.now(UTC).isoformat(),
            result=result,
            error_message=self._result_error_message(result),
        )
        return self._job_response(job)

    def list_jobs(self, user_id: int) -> list[TransferJobResponse]:
        jobs = self.database.list_transfer_jobs(user_id)
        return [self._job_response(job) for job in jobs]

    def get_job(self, user_id: int, job_id: int) -> TransferJobResponse:
        job = self.database.get_transfer_job(user_id, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")
        return self._job_response(job)

    def _job_response(self, job: dict) -> TransferJobResponse:
        return TransferJobResponse(
            id=job["id"],
            source_marketplace=Marketplace(job["source_marketplace"]),
            target_marketplace=Marketplace(job["target_marketplace"]),
            status=JobStatus(job["status"]),
            external_task_id=job.get("external_task_id"),
            error_message=job.get("error_message"),
            created_at=job["created_at"],
            updated_at=job["updated_at"],
            payload=job["payload_json"],
            result=job["result_json"],
        )

    @staticmethod
    def _result_error_message(result: dict) -> str | None:
        if result.get("message"):
            return str(result["message"])
        errors = result.get("errors") or []
        if not errors:
            return None
        first = errors[0]
        if isinstance(first, dict):
            return str(first.get("message") or first.get("description") or first.get("code") or "Import error")
        return str(first)
