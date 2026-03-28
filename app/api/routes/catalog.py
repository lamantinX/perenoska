from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_catalog_service, get_current_user
from app.clients.base import MarketplaceAPIError
from app.schemas import CategoryAttribute, CategoryNode, Marketplace, ProductDetails, ProductSummary

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/products", response_model=list[ProductSummary])
async def list_products(
    marketplace: Marketplace,
    limit: int = Query(default=50, ge=1, le=100),
    user=Depends(get_current_user),
    catalog_service=Depends(get_catalog_service),
) -> list[ProductSummary]:
    return await catalog_service.list_products(user["id"], marketplace, limit)


@router.get("/products/{product_id}", response_model=ProductDetails)
async def get_product(
    product_id: str,
    marketplace: Marketplace,
    user=Depends(get_current_user),
    catalog_service=Depends(get_catalog_service),
) -> ProductDetails:
    return await catalog_service.get_product_details(user["id"], marketplace, product_id)


@router.get("/categories", response_model=list[CategoryNode])
async def list_categories(
    marketplace: Marketplace,
    parent_id: int | None = None,
    user=Depends(get_current_user),
    catalog_service=Depends(get_catalog_service),
) -> list[CategoryNode]:
    return await catalog_service.list_categories(user["id"], marketplace, parent_id)


@router.get("/categories/{category_id}/attributes", response_model=list[CategoryAttribute])
async def get_category_attributes(
    category_id: int,
    marketplace: Marketplace,
    required_only: bool = Query(default=False),
    user=Depends(get_current_user),
    catalog_service=Depends(get_catalog_service),
) -> list[CategoryAttribute]:
    return await catalog_service.get_category_attributes(user["id"], marketplace, category_id, required_only)


@router.get("/{marketplace}/brands")
async def list_brands(
    marketplace: str,
    q: str,
    limit: int = Query(default=20, le=100),
    user=Depends(get_current_user),
    catalog_service=Depends(get_catalog_service),
) -> dict[str, Any]:
    if marketplace != "ozon":
        raise HTTPException(status_code=400, detail="Only ozon marketplace supports brand search")
    try:
        items = await catalog_service.list_brands(user["id"], Marketplace.OZON, query=q, limit=limit)
    except MarketplaceAPIError as error:
        raise HTTPException(
            status_code=502,
            detail={"code": "OZON_API_UNAVAILABLE", "message": str(error)},
        ) from error
    return {"items": items, "total": len(items)}

