from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_catalog_service, get_connection_service, get_auth_service
from app.schemas import Marketplace, ProductSummary, PublicFetchRequest, PublicFetchResponse

router = APIRouter(prefix="/public", tags=["public"])

# Allowed image domains for proxy (security whitelist)
_ALLOWED_IMAGE_HOSTS = {
    "wbbasket.ru",
    "basket-01.wbbasket.ru", "basket-02.wbbasket.ru", "basket-03.wbbasket.ru",
    "basket-04.wbbasket.ru", "basket-05.wbbasket.ru", "basket-06.wbbasket.ru",
    "basket-07.wbbasket.ru", "basket-08.wbbasket.ru", "basket-09.wbbasket.ru",
    "basket-10.wbbasket.ru", "basket-11.wbbasket.ru", "basket-12.wbbasket.ru",
    "basket-13.wbbasket.ru", "basket-14.wbbasket.ru", "basket-15.wbbasket.ru",
    "basket-16.wbbasket.ru", "basket-17.wbbasket.ru", "basket-18.wbbasket.ru",
    "cdn1.ozone.ru", "cdn2.ozone.ru", "ir.ozone.ru",
    "avatars.mds.yandex.net",
}


@router.get("/img", response_class=StreamingResponse)
async def proxy_image(url: str = Query(..., description="Image URL to proxy")) -> StreamingResponse:
    """Proxy marketplace images to avoid hotlink-protection blocks in the browser."""
    parsed = urlparse(url)
    host = parsed.hostname or ""

    # Allow subdomains of known hosts
    allowed = any(
        host == allowed_host or host.endswith("." + allowed_host.lstrip("*."))
        for allowed_host in _ALLOWED_IMAGE_HOSTS
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Image host not allowed")

    # Determine referer based on host
    if "wbbasket" in host or "wildberries" in host:
        referer = "https://www.wildberries.ru/"
    elif "ozone" in host or "ozon" in host:
        referer = "https://www.ozon.ru/"
    else:
        referer = "https://market.yandex.ru/"

    headers = {
        "Referer": referer,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "image/webp,image/avif,image/*,*/*;q=0.8",
    }

    try:
        client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        response = await client.get(url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch image: {exc}")

    content_type = response.headers.get("content-type", "image/webp")

    async def stream():
        async for chunk in response.aiter_bytes(chunk_size=8192):
            yield chunk
        await client.aclose()

    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )

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

# WB keeps adding basket servers — exact upper bounds beyond vol=2837 are
# not publicly documented and shift over time.  We start at basket-18 and
# let the browser's wbLoadImg() probe forward automatically.
def _wb_basket_number(vol: int) -> str:
    for upper, basket in _WB_BASKET_RANGES:
        if vol <= upper:
            return basket
    # Rough heuristic for vol > 2837: each ~300 vol units ≈ one new basket
    extra = max(0, (vol - 2837) // 300)
    n = 18 + extra
    return str(min(n, 30)).zfill(2)


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
