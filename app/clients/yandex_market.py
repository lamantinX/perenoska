from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.clients.base import MarketplaceAPIError, MarketplaceClient, get_trace_context
from app.schemas import CategoryAttribute, CategoryNode, ProductDetails, ProductSummary


class YandexMarketClient(MarketplaceClient):
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def list_products(self, credentials: dict[str, Any], *, limit: int = 500) -> list[ProductSummary]:
        entries: list[dict[str, Any]] = []
        page_token: str | None = None
        while len(entries) < limit:
            payload: dict[str, Any] = {"limit": min(limit - len(entries), 200)}
            if page_token:
                payload["page_token"] = page_token
            data = await self._request(
                "POST",
                f"/v2/campaigns/{credentials['campaign_id']}/offer-mapping-entries.json",
                credentials,
                json=payload,
            )
            result = data.get("result") or data
            batch = result.get("offerMappingEntries") or result.get("items") or []
            if not batch:
                break
            entries.extend(batch)
            next_page = result.get("paging", {}).get("nextPageToken") or result.get("nextPageToken")
            if not next_page or next_page == page_token or len(entries) >= limit:
                break
            page_token = str(next_page)
        return [self._parse_product_summary(item) for item in entries[:limit]]

    async def get_product_details(self, credentials: dict[str, Any], product_id: str) -> ProductDetails:
        data = await self._request(
            "POST",
            f"/v2/campaigns/{credentials['campaign_id']}/offer-mapping-entries.json",
            credentials,
            json={"offerIds": [product_id], "limit": 1},
        )
        result = data.get("result") or data
        entries = result.get("offerMappingEntries") or result.get("items") or []
        if not entries:
            raise MarketplaceAPIError(f"Yandex Market offer {product_id} not found.")
        return self._parse_product_details(entries[0])

    async def list_categories(
        self,
        credentials: dict[str, Any],
        *,
        parent_id: int | None = None,
    ) -> list[CategoryNode]:
        data = await self._request(
            "POST",
            "/v2/categories/tree",
            credentials,
            json={"businessId": credentials["business_id"]},
        )
        result = data.get("result") or data
        roots = result.get("children") or result.get("categories") or []
        categories = self._flatten_categories(roots, parent_id=None)
        if parent_id is None:
            return categories
        return [item for item in categories if item.parent_id == parent_id]

    async def get_category_attributes(
        self,
        credentials: dict[str, Any],
        category_id: int,
        *,
        required_only: bool = False,
    ) -> list[CategoryAttribute]:
        data = await self._request(
            "POST",
            f"/v2/category/{category_id}/parameters",
            credentials,
            json={"businessId": credentials["business_id"]},
        )
        result = data.get("result") or data
        items = result.get("parameters") or result.get("attributes") or []
        attributes = [self._parse_category_attribute(item) for item in items]
        if required_only:
            return [attribute for attribute in attributes if attribute.required]
        return attributes

    async def create_products(self, credentials: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        if not items:
            raise MarketplaceAPIError("Yandex Market import requires at least one item.")
        await self._request(
            "POST",
            f"/businesses/{credentials['business_id']}/offer-mappings/update",
            credentials,
            json={"offerMappingEntries": items},
        )
        offer_ids = [
            str((item.get("offer") or {}).get("shopSku") or "").strip()
            for item in items
        ]
        normalized_offer_ids = [offer_id for offer_id in offer_ids if offer_id]
        return {
            "status": "submitted",
            "external_task_id": ",".join(normalized_offer_ids) or None,
            "submitted_count": len(items),
            "items": [{"offer_id": offer_id, "status": "submitted"} for offer_id in normalized_offer_ids],
        }

    async def get_import_status(
        self,
        credentials: dict[str, Any],
        external_task_id: str | None,
    ) -> dict[str, Any]:
        offer_ids = [item.strip() for item in (external_task_id or "").split(",") if item.strip()]
        if not offer_ids:
            raise MarketplaceAPIError("Yandex Market import status requires submitted offer ids.")

        data = await self._request(
            "POST",
            f"/businesses/{credentials['business_id']}/offer-mappings",
            credentials,
            json={"offerIds": offer_ids},
        )
        result = data.get("result") or data
        entries = result.get("offerMappingEntries") or result.get("items") or []
        items: list[dict[str, Any]] = []
        completed_count = 0
        failed_count = 0
        processing_count = 0
        errors: list[dict[str, Any]] = []

        for entry in entries:
            offer = entry.get("offer") or {}
            processing_state = entry.get("processingState") or {}
            normalized_status = self._normalize_processing_status(processing_state)
            notes = self._processing_notes(processing_state)
            items.append(
                {
                    "offer_id": str(offer.get("shopSku") or offer.get("offerId") or offer.get("id") or ""),
                    "status": normalized_status,
                    "notes": notes,
                }
            )
            if normalized_status == "ready":
                completed_count += 1
            elif normalized_status == "failed":
                failed_count += 1
                errors.extend({"message": note} for note in notes if note)
            else:
                processing_count += 1

        if items and completed_count == len(items):
            aggregate_status = "completed"
        elif failed_count and not processing_count:
            aggregate_status = "failed"
        else:
            aggregate_status = "processing"

        return {
            "status": aggregate_status,
            "processed_count": len(items),
            "completed_count": completed_count,
            "failed_count": failed_count,
            "errors": errors,
            "items": items,
        }

    async def _request(
        self,
        method: str,
        path: str,
        credentials: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"OAuth {credentials['token']}",
            "Accept": "application/json",
        }
        trace = get_trace_context()
        started_at = datetime.now(UTC)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
        if trace is not None:
            trace.log_event(
                event_type="http",
                operation=f"yandex_market:{method} {path}",
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
            raise MarketplaceAPIError(f"Yandex Market API error {response.status_code}: {response.text}")
        if not response.content:
            return {}
        return response.json()

    def _parse_product_summary(self, entry: dict[str, Any]) -> ProductSummary:
        offer = entry.get("offer") or entry
        mapping = entry.get("mapping") or {}
        category = mapping.get("marketCategory") or entry.get("marketCategory") or {}
        price = offer.get("price") or offer.get("basicPrice") or mapping.get("price")
        stock = offer.get("stock") or offer.get("count") or mapping.get("stockCount")
        return ProductSummary(
            id=str(offer.get("shopSku") or offer.get("offerId") or offer.get("id") or ""),
            offer_id=str(offer.get("shopSku") or offer.get("offerId") or "") or None,
            title=offer.get("name") or offer.get("title") or offer.get("shopSku") or "Untitled",
            description=offer.get("description"),
            category_id=category.get("id"),
            category_name=category.get("name"),
            price=str(price) if price not in {None, ""} else None,
            currency=offer.get("currency") or "RUB",
            stock=int(stock) if isinstance(stock, int | float) else None,
            images=[str(item) for item in offer.get("pictures") or offer.get("images") or [] if item],
            raw=entry,
        )

    def _parse_product_details(self, entry: dict[str, Any]) -> ProductDetails:
        summary = self._parse_product_summary(entry)
        offer = entry.get("offer") or entry
        attributes = {
            str(param.get("name") or param.get("code") or param.get("id") or "attribute"): [
                str(value) for value in param.get("values") or [param.get("value")] if value not in {None, ""}
            ]
            for param in offer.get("parameters") or offer.get("attributes") or []
        }
        return ProductDetails(
            **summary.model_dump(),
            attributes=attributes,
            dimensions=offer.get("dimensions") or {},
            sizes=offer.get("sizes") or [],
            barcode_list=[str(item) for item in offer.get("barcodes") or []],
            brand=offer.get("vendor") or offer.get("brand"),
            raw_sources={"offer_mapping_entry": entry},
        )

    def _flatten_categories(self, items: list[dict[str, Any]], *, parent_id: int | None) -> list[CategoryNode]:
        flat: list[CategoryNode] = []
        for item in items:
            category_id = item.get("id") or item.get("categoryId")
            if not category_id:
                continue
            node = CategoryNode(
                id=int(category_id),
                name=str(item.get("name") or item.get("title") or category_id),
                parent_id=parent_id,
                raw=item,
            )
            flat.append(node)
            flat.extend(self._flatten_categories(item.get("children") or [], parent_id=node.id))
        return flat

    def _parse_category_attribute(self, item: dict[str, Any]) -> CategoryAttribute:
        values = item.get("values") or item.get("options") or []
        dictionary_values = [
            {
                "id": int(value.get("id") or value.get("valueId") or value.get("optionId") or 0),
                "value": str(value.get("value") or value.get("name") or value.get("label") or ""),
            }
            for value in values
            if value.get("id") or value.get("valueId") or value.get("optionId")
        ]
        return CategoryAttribute(
            id=int(item.get("id") or item.get("parameterId") or 0),
            name=str(item.get("name") or item.get("title") or item.get("code") or "Attribute"),
            required=bool(item.get("required") or item.get("isRequired")),
            type=str(item.get("type") or item.get("valueType") or "") or None,
            dictionary_values=dictionary_values,
            raw=item,
        )

    @staticmethod
    def _normalize_processing_status(processing_state: dict[str, Any]) -> str:
        raw_status = str(
            processing_state.get("status")
            or processing_state.get("state")
            or processing_state.get("processingStatus")
            or ""
        ).strip().upper()
        if raw_status in {"READY", "ACCEPTED", "PUBLISHED"}:
            return "ready"
        if raw_status in {"REJECTED", "FAILED", "ERROR", "NEED_INFO"}:
            return "failed"
        return "processing"

    @staticmethod
    def _processing_notes(processing_state: dict[str, Any]) -> list[str]:
        raw_notes = processing_state.get("notes") or processing_state.get("messages") or []
        notes: list[str] = []
        for item in raw_notes:
            if isinstance(item, dict):
                value = item.get("message") or item.get("text") or item.get("description") or item.get("code")
            else:
                value = item
            if value not in {None, ""}:
                notes.append(str(value))
        return notes
