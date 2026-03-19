from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_catalog_service, get_current_user
from app.schemas import CategoryAttribute, CategoryNode, Marketplace, ProductDetails, ProductSummary

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/products", response_model=list[ProductSummary])
async def list_products(
    marketplace: Marketplace,
    limit: int = Query(default=500, ge=1, le=1000),
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

