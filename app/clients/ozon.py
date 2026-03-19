from __future__ import annotations

import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any

import httpx

from app.clients.base import MarketplaceAPIError, MarketplaceClient, get_trace_context
from app.schemas import CategoryAttribute, CategoryNode, ProductDetails, ProductSummary


class OzonClient(MarketplaceClient):
    GENERIC_TYPE_STEMS = {"игрушк", "набор", "товар", "дет", "игр"}

    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def list_products(self, credentials: dict[str, Any], *, limit: int = 500) -> list[ProductSummary]:
        items: list[dict[str, Any]] = []
        last_id = ""
        seen_last_ids: set[str] = set()
        while len(items) < limit:
            payload = {
                "filter": {
                    "visibility": "ALL",
                },
                "last_id": last_id,
                "limit": limit - len(items),
            }
            data = await self._request("POST", "/v3/product/list", credentials, json=payload)
            result = data.get("result", {}) or {}
            batch = result.get("items") or data.get("items") or []
            if not batch:
                break
            items.extend(batch)
            next_last_id = result.get("last_id") or data.get("last_id") or ""
            if not next_last_id or len(items) >= limit:
                break
            next_last_id = str(next_last_id)
            if next_last_id == last_id or next_last_id in seen_last_ids:
                break
            seen_last_ids.add(next_last_id)
            last_id = next_last_id
        if not items:
            return []

        product_ids = [item.get("product_id") for item in items if item.get("product_id")]
        detailed_items = await self._request(
            "POST",
            "/v3/product/info/list",
            credentials,
            json={"product_id": product_ids},
        )
        detailed_index = {
            str(item.get("id") or item.get("product_id")): item
            for item in detailed_items.get("items") or detailed_items.get("result", {}).get("items") or []
        }
        merged_items = []
        for item in items:
            product_id = str(item.get("product_id") or "")
            merged = dict(item)
            if product_id in detailed_index:
                merged.update(detailed_index[product_id])
            merged_items.append(merged)
        return [self._parse_product_summary(item) for item in merged_items]

    async def get_product_details(self, credentials: dict[str, Any], product_id: str) -> ProductDetails:
        info = await self._request(
            "POST",
            "/v3/product/info/list",
            credentials,
            json={"product_id": [int(product_id)]} if str(product_id).isdigit() else {"offer_id": [product_id]},
        )
        items = info.get("items") or info.get("result", {}).get("items") or []
        if not items:
            raise MarketplaceAPIError(f"Карточка Ozon {product_id} не найдена.")
        info_payload = items[0]
        details = self._parse_product_details(info_payload)

        try:
            attributes_response = await self._request(
                "POST",
                "/v4/products/info/attributes",
                credentials,
                json={
                    "filter": {
                        "offer_id": [details.offer_id] if details.offer_id else [],
                        "product_id": [int(product_id)] if str(product_id).isdigit() else [],
                        "visibility": "ALL",
                    },
                    "limit": 1,
                },
            )
        except MarketplaceAPIError as error:
            if "404" not in str(error):
                raise
            attributes_response = {}

        attribute_items = attributes_response.get("result") or []
        if attribute_items:
            self._merge_attribute_details(details, attribute_items[0])

        description = await self._get_product_description(
            credentials,
            product_id=product_id,
            offer_id=details.offer_id,
        )
        if description:
            details.description = description
        return details

    async def list_categories(
        self,
        credentials: dict[str, Any],
        *,
        parent_id: int | None = None,
    ) -> list[CategoryNode]:
        data = await self._request("POST", "/v1/description-category/tree", credentials, json={})
        roots = data.get("result") or data.get("data") or []
        flattened = self._flatten_categories(roots, parent_id=None)
        if parent_id is None:
            return flattened
        return [item for item in flattened if item.parent_id == parent_id]

    async def get_category_attributes(
        self,
        credentials: dict[str, Any],
        category_id: int,
        *,
        required_only: bool = False,
    ) -> list[CategoryAttribute]:
        categories = await self.list_categories(credentials)
        category = next((item for item in categories if item.id == category_id), None)
        if category is None:
            raise MarketplaceAPIError(f"Ozon category {category_id} not found.")
        return await self.get_category_attributes_for_node(
            credentials,
            category,
            required_only=required_only,
        )

    async def get_category_attributes_for_node(
        self,
        credentials: dict[str, Any],
        category: CategoryNode,
        *,
        source_product: ProductDetails | None = None,
        required_only: bool = False,
    ) -> list[CategoryAttribute]:
        context = self.resolve_category_context(category, source_product=source_product)
        category.raw["_resolved_type_id"] = context["type_id"]
        category.raw["_resolved_type_name"] = context["type_name"]
        type_id = context["type_id"]
        if not type_id:
            return []

        payload = {
            "description_category_id": context["description_category_id"],
            "type_id": type_id,
            "type": "REQUIRED" if required_only else "ALL",
            "language": "DEFAULT",
        }
        data = await self._request("POST", "/v1/description-category/attribute", credentials, json=payload)
        items = data.get("result") or data.get("attributes") or []
        attributes: list[CategoryAttribute] = []
        for item in items:
            attribute = CategoryAttribute(
                id=int(item.get("id") or item.get("attribute_id") or 0),
                name=item.get("name") or "Без названия",
                required=bool(item.get("is_required") or item.get("required")),
                type=item.get("type") or item.get("attribute_type"),
                raw=item,
            )
            if item.get("dictionary_id") or item.get("is_dictionary"):
                dictionary_payload = {
                    "description_category_id": context["description_category_id"],
                    "type_id": type_id,
                    "attribute_id": attribute.id,
                    "language": "DEFAULT",
                    "limit": 100,
                    "last_value_id": 0,
                }
                try:
                    dictionary_response = await self._request(
                        "POST",
                        "/v1/description-category/attribute/values",
                        credentials,
                        json=dictionary_payload,
                    )
                except MarketplaceAPIError:
                    dictionary_response = {}
                attribute.dictionary_values = dictionary_response.get("result") or []
            attributes.append(attribute)
        if required_only:
            return [attribute for attribute in attributes if attribute.required]
        return attributes

    def resolve_category_context(
        self,
        category: CategoryNode,
        *,
        source_product: ProductDetails | None = None,
    ) -> dict[str, Any]:
        raw = category.raw or {}
        description_category_id = int(raw.get("description_category_id") or category.id)
        candidates = [
            child
            for child in raw.get("children") or []
            if child.get("type_id") and not child.get("disabled")
        ]
        if not candidates:
            return {
                "description_category_id": description_category_id,
                "type_id": None,
                "type_name": None,
            }

        best = candidates[0]
        best_score = -1.0
        for candidate in candidates:
            score = self._type_match_score(candidate, source_product)
            if score > best_score:
                best = candidate
                best_score = score

        return {
            "description_category_id": description_category_id,
            "type_id": int(best.get("type_id") or 0) or None,
            "type_name": best.get("type_name"),
        }

    async def create_products(self, credentials: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        data = await self._request("POST", "/v3/product/import", credentials, json={"items": items})
        result = data.get("result") or data
        return {
            "external_task_id": str(result.get("task_id") or result.get("taskId") or ""),
            "raw_response": data,
        }

    async def get_import_status(
        self,
        credentials: dict[str, Any],
        external_task_id: str | None,
    ) -> dict[str, Any]:
        if not external_task_id:
            return {"status": "unknown", "message": "Ozon task_id не был получен при запуске импорта."}
        try:
            data = await self._request(
                "POST",
                "/v1/product/import/info",
                credentials,
                json={"task_id": external_task_id},
            )
        except MarketplaceAPIError as error:
            message = str(error)
            if "task not found" in message.lower():
                return {"status": "failed", "message": message, "errors": [message]}
            raise
        result = data.get("result") or data
        errors = result.get("errors") or []
        items = result.get("items") or []
        item_errors = [error for item in items for error in item.get("errors") or []]
        item_statuses = {str(item.get("status") or "").lower() for item in items if item.get("status")}
        combined_errors = [*errors, *item_errors]
        if item_statuses:
            success_statuses = {"imported", "completed", "done", "success"}
            pending_statuses = {"processing", "pending", "created", "submitted", "importing"}
            failed_statuses = {"failed", "error", "rejected", "skipped"}
            if item_statuses <= success_statuses and not combined_errors:
                status_value = "completed"
            elif item_statuses & failed_statuses or combined_errors:
                status_value = "failed"
            elif item_statuses & pending_statuses:
                status_value = "processing"
            else:
                status_value = result.get("status") or result.get("state") or "processing"
        else:
            status_value = result.get("status") or result.get("state") or ("failed" if combined_errors else "processing")
        return {"status": str(status_value).lower(), "errors": combined_errors, "raw_response": data}

    async def get_dictionary_values(
        self,
        credentials: dict[str, Any],
        *,
        attribute_id: int,
        description_category_id: int,
        type_id: int,
        search: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "description_category_id": description_category_id,
            "type_id": type_id,
            "attribute_id": attribute_id,
            "language": "DEFAULT",
            "limit": limit,
            "last_value_id": 0,
        }
        if search:
            payload["value"] = search
        data = await self._request("POST", "/v1/description-category/attribute/values", credentials, json=payload)
        items = data.get("result") or []
        return [
            {
                "id": int(item.get("id") or item.get("dictionary_value_id") or 0),
                "value": str(item.get("value") or item.get("name") or ""),
            }
            for item in items
            if item.get("id") or item.get("dictionary_value_id")
        ]

    async def _get_product_description(
        self,
        credentials: dict[str, Any],
        *,
        product_id: str,
        offer_id: str | None,
    ) -> str | None:
        try:
            response = await self._request(
                "POST",
                "/v1/product/info/description",
                credentials,
                json={
                    "offer_id": offer_id or "",
                    "product_id": int(product_id) if str(product_id).isdigit() else 0,
                },
            )
        except MarketplaceAPIError:
            return None
        result = response.get("result") or response
        description = result.get("description")
        return str(description) if description else None

    def _merge_attribute_details(self, details: ProductDetails, payload: dict[str, Any]) -> None:
        attributes: dict[str, list[str]] = {}
        for item in payload.get("attributes") or []:
            values = item.get("values") or []
            attribute_key = str(item.get("name") or item.get("attribute_name") or item.get("attribute_id") or item.get("id"))
            attributes[attribute_key] = [
                str(value.get("value") or value.get("dictionary_value_id") or "")
                for value in values
                if value.get("value") is not None or value.get("dictionary_value_id") is not None
            ]
        if attributes:
            details.attributes = attributes

        brand_values = attributes.get("Бренд") or attributes.get("Brand") or attributes.get("85") or []
        if brand_values:
            details.brand = brand_values[0]

        barcode = payload.get("barcode")
        if barcode:
            details.barcode_list = [str(barcode)]

        image_payload = payload.get("images") or []
        normalized_images = []
        for item in image_payload:
            if isinstance(item, dict):
                normalized_images.append(str(item.get("file_name") or item.get("url") or item.get("src") or "").strip())
                continue
            normalized_images.append(str(item).strip())
        normalized_images = [item for item in normalized_images if item]
        if normalized_images:
            details.images = normalized_images

        details.dimensions = {
            "height": payload.get("height") or details.dimensions.get("height"),
            "width": payload.get("width") or details.dimensions.get("width"),
            "depth": payload.get("depth") or details.dimensions.get("depth"),
            "weight": payload.get("weight") or details.dimensions.get("weight"),
            "dimension_unit": payload.get("dimension_unit") or details.dimensions.get("dimension_unit"),
            "weight_unit": payload.get("weight_unit") or details.dimensions.get("weight_unit"),
        }

    async def _request(
        self,
        method: str,
        path: str,
        credentials: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = {"Client-Id": credentials["client_id"], "Api-Key": credentials["api_key"]}
        trace = get_trace_context()
        started_at = datetime.now(UTC)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
        if trace is not None:
            trace.log_event(
                event_type="http",
                operation=f"ozon:{method} {path}",
                request_url=f"{self.base_url}{path}",
                request_headers=headers,
                request_body=kwargs.get("json") or kwargs.get("params"),
                response_headers=dict(response.headers),
                response_body=response.json() if response.content else {},
                status_code=response.status_code,
                duration_ms=int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                error_text=response.text if response.is_error else None,
            )
        if response.is_error:
            raise MarketplaceAPIError(f"Ozon API error {response.status_code}: {response.text}")
        if not response.content:
            return {}
        return response.json()

    def _flatten_categories(self, items: list[dict[str, Any]], *, parent_id: int | None) -> list[CategoryNode]:
        flat: list[CategoryNode] = []
        for item in items:
            category_id = item.get("description_category_id") or item.get("category_id") or item.get("id")
            if not category_id:
                continue
            node = CategoryNode(
                id=int(category_id),
                name=item.get("category_name") or item.get("title") or item.get("name") or "Без названия",
                parent_id=parent_id,
                raw=item,
            )
            flat.append(node)
            children = item.get("children") or item.get("category_children") or []
            flat.extend(self._flatten_categories(children, parent_id=node.id))
        return flat

    def _type_match_score(self, candidate: dict[str, Any], source_product: ProductDetails | None) -> float:
        if source_product is None:
            return 0.0
        candidate_name = self._normalize_text(str(candidate.get("type_name") or candidate.get("name") or ""))
        if not candidate_name:
            return 0.0

        candidate_stems = self._token_stems(candidate_name)
        specific_candidate_stems = candidate_stems - self.GENERIC_TYPE_STEMS
        best = 0.0
        attribute_text = " ".join(
            [*source_product.attributes.keys(), *[item for values in source_product.attributes.values() for item in values]]
        )
        for source_value in (
            source_product.category_name or "",
            source_product.title or "",
            source_product.description or "",
            attribute_text,
        ):
            source_name = self._normalize_text(source_value)
            if not source_name:
                continue
            source_stems = self._token_stems(source_name)
            specific_overlap = len(specific_candidate_stems & source_stems)
            total_overlap = len(candidate_stems & source_stems)
            overlap_bonus = (specific_overlap * 2.0) + (total_overlap * 0.2)
            exact_phrase_bonus = 6.0 if candidate_name in source_name else 0.0
            reverse_phrase_bonus = 2.0 if source_name in candidate_name else 0.0
            sequence_score = SequenceMatcher(None, source_name, candidate_name).ratio() * 0.5
            generic_penalty = 1.0 if not specific_overlap and not exact_phrase_bonus and specific_candidate_stems else 0.0
            best = max(
                best,
                overlap_bonus + exact_phrase_bonus + reverse_phrase_bonus + sequence_score - generic_penalty,
            )
        return best

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    @staticmethod
    def _token_stems(value: str) -> set[str]:
        stems: set[str] = set()
        for token in re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", value.lower()):
            stem = re.sub(
                r"(ами|ями|ого|его|ому|ему|ах|ях|ов|ев|ей|ой|ий|ый|ая|яя|ое|ее|ые|ие|ам|ям|ом|ем|у|ю|а|я|ы|и|е|о)$",
                "",
                token,
            )
            if stem:
                stems.add(stem)
        return stems

    def _parse_product_summary(self, item: dict[str, Any]) -> ProductSummary:
        images = item.get("images") or []
        primary_image = item.get("primary_image")
        if isinstance(primary_image, list):
            images = [*primary_image, *images]
        elif primary_image:
            images = [primary_image, *images]
        return ProductSummary(
            id=str(item.get("product_id") or item.get("id") or item.get("offer_id") or ""),
            offer_id=item.get("offer_id"),
            title=item.get("name") or item.get("title") or item.get("offer_id") or "Без названия",
            description=item.get("description"),
            category_id=item.get("category_id") or item.get("description_category_id"),
            category_name=item.get("category_name") or item.get("description_category_name") or str(item.get("description_category_id") or ""),
            price=str(item.get("price") or item.get("min_price") or item.get("old_price"))
            if item.get("price") is not None or item.get("min_price") is not None or item.get("old_price") is not None
            else None,
            currency=item.get("currency_code") or "RUB",
            stock=item.get("stocks", {}).get("present") or item.get("stocks", {}).get("coming"),
            images=[str(image) for image in images if image],
            raw=item,
        )

    def _parse_product_details(self, item: dict[str, Any]) -> ProductDetails:
        summary = self._parse_product_summary(item)
        dimensions = {
            "height": item.get("height"),
            "width": item.get("width"),
            "depth": item.get("depth"),
            "weight": item.get("weight"),
            "dimension_unit": item.get("dimension_unit"),
            "weight_unit": item.get("weight_unit"),
        }
        return ProductDetails(
            **summary.model_dump(),
            attributes={},
            dimensions=dimensions,
            sizes=item.get("sources") or [],
            barcode_list=[str(barcode) for barcode in item.get("barcodes") or []],
            brand=item.get("brand") or item.get("brand_name"),
        )
