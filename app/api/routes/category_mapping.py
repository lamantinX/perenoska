from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_catalog_service,
    get_category_mapper,
    get_container,
    get_current_user,
)
from app.schemas import (
    AutoMappingResult,
    AutoMappingStatusResponse,
    Marketplace,
    ReviewQueueItem,
    ReviewResolveRequest,
)
from app.services.catalog import CatalogService
from app.services.category_mapper import CategoryMapper, _flatten_categories

router = APIRouter(prefix="/category-mapping", tags=["category-mapping"])


@router.post("/run", response_model=list[AutoMappingResult])
async def run_mapping(
    wb_category_id: int | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    catalog_service: CatalogService = Depends(get_catalog_service),
    mapper: CategoryMapper = Depends(get_category_mapper),
):
    """Run category mapping for one or all WB categories against Ozon."""
    user_id = user["id"]

    # Fetch WB categories
    wb_categories = await catalog_service.list_categories(user_id, Marketplace.WB)
    if not wb_categories:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нет категорий WB. Проверьте подключение.")

    # Fetch Ozon categories
    ozon_categories = await catalog_service.list_categories(user_id, Marketplace.OZON)
    if not ozon_categories:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нет категорий Ozon. Проверьте подключение.")

    ozon_flat = _flatten_categories(ozon_categories)

    if wb_category_id is not None:
        # Map single category
        wb_flat = _flatten_categories(wb_categories)
        target = next((c for c in wb_flat if c["id"] == wb_category_id), None)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"WB категория {wb_category_id} не найдена.")
        result = await mapper.map_category(target["node"], ozon_flat, wb_path=target["path"])
        return [result.to_dict()]

    # Batch: map all leaf WB categories
    wb_flat = _flatten_categories(wb_categories)
    wb_leaves = [c["node"] for c in wb_flat if not c["node"].children]
    if not wb_leaves:
        wb_leaves = [c["node"] for c in wb_flat]

    results = await mapper.map_categories_batch(wb_leaves, ozon_categories)
    return [r.to_dict() for r in results]


@router.get("/status", response_model=AutoMappingStatusResponse)
async def mapping_status(
    user: dict[str, Any] = Depends(get_current_user),
    catalog_service: CatalogService = Depends(get_catalog_service),
    container=Depends(get_container),
):
    """Get current mapping status: counts by confidence level."""
    user_id = user["id"]
    wb_categories = await catalog_service.list_categories(user_id, Marketplace.WB)
    wb_flat = _flatten_categories(wb_categories)
    total = len(wb_flat)

    stats = container.database.get_category_mapping_stats()
    return AutoMappingStatusResponse(
        total_wb_categories=total,
        mapped=stats["mapped"],
        pending_review=stats["pending_review"],
        high_confidence=stats["high_confidence"],
        medium_confidence=stats["medium_confidence"],
        low_confidence=stats["low_confidence"],
    )


@router.get("/review", response_model=list[ReviewQueueItem])
async def list_review_queue(
    queue_status: str = "pending",
    user: dict[str, Any] = Depends(get_current_user),
    container=Depends(get_container),
):
    """List items in the manual review queue."""
    rows = container.database.list_review_queue(status=queue_status)
    items = []
    for row in rows:
        candidates = row.get("candidates", "[]")
        if isinstance(candidates, str):
            candidates = json.loads(candidates)
        items.append(
            ReviewQueueItem(
                id=row["id"],
                wb_id=row["wb_id"],
                wb_name=row["wb_name"],
                wb_path=row.get("wb_path", ""),
                candidates=candidates,
                reason=row.get("reason", ""),
                status=row["status"],
                created_at=row["created_at"],
            )
        )
    return items


@router.post("/review/{item_id}/resolve", response_model=AutoMappingResult)
async def resolve_review_item(
    item_id: int,
    body: ReviewResolveRequest,
    user: dict[str, Any] = Depends(get_current_user),
    container=Depends(get_container),
):
    """Resolve a manual review item by providing the correct Ozon category."""
    now = datetime.now(UTC).isoformat()
    resolved = container.database.resolve_review_item(
        item_id=item_id,
        ozon_id=body.ozon_id,
        ozon_name=body.ozon_name,
        now=now,
    )
    if resolved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Элемент очереди {item_id} не найден.")

    mapping = container.database.get_category_mapping(resolved["wb_id"])
    if mapping is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Маппинг не создан.")

    alternatives = mapping.get("alternatives", "[]")
    if isinstance(alternatives, str):
        alternatives = json.loads(alternatives)

    return AutoMappingResult(
        wb_id=mapping["wb_id"],
        ozon_id=mapping["ozon_id"],
        wb_name=mapping["wb_name"],
        ozon_name=mapping["ozon_name"],
        confidence=mapping["confidence"],
        source=mapping["source"],
        alternatives=alternatives,
    )


@router.get("/history/{wb_id}")
async def mapping_history(
    wb_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    container=Depends(get_container),
):
    """Get mapping history for a specific WB category."""
    return container.database.get_mapping_history(wb_id)
