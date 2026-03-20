from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_catalog_service, get_connection_service, get_auth_service
from app.schemas import Marketplace, ProductSummary, PublicFetchRequest, PublicFetchResponse

router = APIRouter(prefix="/public", tags=["public"])

_security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# WB image URL helpers
# ---------------------------------------------------------------------------

_WB_BASKET_RANGES: list[tuple[int, str]] = [
    (143, "01"),
    (287, "02"),
    (431, "03"),
    (719, "04"),
    (1007, "05"),
    (1061, "06"),
    (1115, "07"),
    (1169, "08"),
    (1313, "09"),
    (1601, "10"),
    (1655, "11"),
    (1919, "12"),
    (2045, "13"),
    (2189, "14"),
    (2405, "15"),
    (2621, "16"),
    (2837, "17"),
]


def _wb_basket_number(vol: int) -> str:
    for upper, basket in _WB_BASKET_RANGES:
        if vol <= upper:
            return basket
    return "18"


def _wb_image_url(nm_id: int, idx: int = 1) -> str:
    vol = nm_id // 100000
    part = nm_id // 1000
    basket = _wb_basket_number(vol)
    return (
        f"https://basket-{basket}.wbbasket.ru"
        f"/vol{vol}/part{part}/{nm_id}/images/big/{idx}.webp"
    )


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

def _parse_url(raw_url: str) -> tuple[str, str, str] | None:
    """Return (marketplace, source_type, source_id) or None if unrecognised."""
    parsed = urlparse(raw_url)
    host = parsed.hostname or ""
    path = parsed.path.rstrip("/")

    # Wildberries
    if host in ("wildberries.ru", "www.wildberries.ru", "wb.ru", "www.wb.ru"):
        # seller: /seller/123456
        m = re.match(r"^/seller/(\d+)$", path)
        if m:
            return "wb", "seller", m.group(1)

        # product: /catalog/123456/detail.aspx
        m = re.match(r"^/catalog/(\d+)/detail\.aspx$", path)
        if m:
            return "wb", "product", m.group(1)

        return None

    # Ozon
    if host in ("ozon.ru", "www.ozon.ru"):
        # seller: /seller/name-123456/
        m = re.match(r"^/seller/[^/]+-(\d+)$", path)
        if m:
            return "ozon", "seller", m.group(1)

        # product: /product/title-123456/
        m = re.match(r"^/product/[^/]+-(\d+)$", path)
        if m:
            return "ozon", "product", m.group(1)

        return None

    # Yandex Market
    if host in ("market.yandex.ru", "www.market.yandex.ru"):
        # shop: /shop--name/123456
        m = re.match(r"^/shop--[^/]+/(\d+)$", path)
        if m:
            return "yandex_market", "seller", m.group(1)

        # product: /product--title/123456
        m = re.match(r"^/product--[^/]+/(\d+)$", path)
        if m:
            return "yandex_market", "product", m.group(1)

        return None

    return None


# ---------------------------------------------------------------------------
# WB fetching helpers
# ---------------------------------------------------------------------------

def _map_wb_product(product: dict) -> ProductSummary:
    nm_id = product.get("id", 0)
    price_u = product.get("priceU")
    price = str(price_u // 100) if price_u else None
    images = [_wb_image_url(nm_id)] if nm_id else []
    return ProductSummary(
        id=str(nm_id),
        offer_id=None,
        title=product.get("name") or "Без названия",
        description=None,
        category_id=None,
        category_name=product.get("brand"),
        price=price,
        currency="RUB",
        stock=None,
        images=images,
        raw=product,
    )


async def _fetch_wb_seller(seller_id: str, limit: int) -> list[ProductSummary]:
    url = (
        f"https://catalog.wb.ru/sellers/catalog"
        f"?supplier={seller_id}&sort=popular&page=1&limit={limit}"
        f"&appType=1&curr=rub&dest=-1257786"
    )
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    products = data.get("data", {}).get("products") or []
    return [_map_wb_product(p) for p in products[:limit]]


async def _fetch_wb_product(nm_id: str) -> list[ProductSummary]:
    url = (
        f"https://card.wb.ru/cards/v4/detail"
        f"?appType=1&curr=rub&dest=-1257786&nm={nm_id}"
    )
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    products = data.get("products") or []
    if not products:
        return []
    return [_map_wb_product(products[0])]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/fetch", response_model=PublicFetchResponse)
async def public_fetch(
    body: PublicFetchRequest,
    credentials_header: HTTPAuthorizationCredentials | None = Depends(_security),
    auth_service=Depends(get_auth_service),
    connection_service=Depends(get_connection_service),
    catalog_service=Depends(get_catalog_service),
) -> PublicFetchResponse:
    parsed = _parse_url(body.url)
    if parsed is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Не удалось распознать ссылку. Поддерживаются URL Wildberries, Ozon и Яндекс.Маркет."
            ),
        )

    marketplace, source_type, source_id = parsed

    # Ozon — requires user credentials
    if marketplace == "ozon":
        user = _resolve_optional_user(credentials_header, auth_service)
        if user is None:
            return PublicFetchResponse(
                marketplace=marketplace,
                source_type=source_type,
                source_id=source_id,
                products=[],
                total=0,
                message="Для Ozon подключите ваш магазин через API-ключ",
                requires_credentials=True,
            )

        row = connection_service.database.get_connection(user["id"], Marketplace.OZON.value)
        if row is None:
            return PublicFetchResponse(
                marketplace=marketplace,
                source_type=source_type,
                source_id=source_id,
                products=[],
                total=0,
                message="Подключение Ozon не настроено. Добавьте API-ключ в настройках.",
                requires_credentials=True,
            )

        try:
            if source_type == "product":
                product = await catalog_service.get_product_details(
                    user["id"], Marketplace.OZON, source_id
                )
                products: list[ProductSummary] = [product]
            else:
                products = await catalog_service.list_products(
                    user["id"], Marketplace.OZON, limit=body.limit
                )
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Не удалось получить данные от Ozon: {exc}",
            )

        return PublicFetchResponse(
            marketplace=marketplace,
            source_type=source_type,
            source_id=source_id,
            products=products,
            total=len(products),
        )

    if marketplace == "yandex_market":
        return PublicFetchResponse(
            marketplace=marketplace,
            source_type=source_type,
            source_id=source_id,
            products=[],
            total=0,
            message="Для Яндекс.Маркет подключите ваш магазин через API-ключ",
            requires_credentials=True,
        )

    # Wildberries — use public API
    try:
        if source_type == "seller":
            products = await _fetch_wb_seller(source_id, body.limit)
        else:
            products = await _fetch_wb_product(source_id)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Не удалось получить данные от Wildberries: {exc}",
        )

    return PublicFetchResponse(
        marketplace=marketplace,
        source_type=source_type,
        source_id=source_id,
        products=products,
        total=len(products),
    )


def _resolve_optional_user(
    credentials_header: HTTPAuthorizationCredentials | None,
    auth_service,
) -> dict | None:
    if credentials_header is None or credentials_header.scheme.lower() != "bearer":
        return None
    try:
        return auth_service.get_current_user(credentials_header.credentials)
    except HTTPException:
        return None
