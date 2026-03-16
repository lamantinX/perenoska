from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from app.clients.base import MarketplaceAPIError, MarketplaceClient
from app.schemas import CategoryAttribute, CategoryNode, ProductDetails, ProductSummary


class WBClient(MarketplaceClient):
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def list_products(self, credentials: dict[str, Any], *, limit: int = 50) -> list[ProductSummary]:
        payload = {
            "settings": {
                "cursor": {
                    "limit": limit,
                },
                "filter": {
                    "withPhoto": -1,
                },
            }
        }
        data = await self._request("POST", "/content/v2/get/cards/list", credentials, json=payload)
        cards = data.get("cards") or data.get("data", {}).get("cards") or data.get("data", []) or []
        nm_ids = [card.get("nmID") for card in cards if card.get("nmID")]
        public_details = await self._fetch_public_details(nm_ids)
        seller_prices = await self._fetch_seller_prices(credentials, nm_ids)
        return [
            self._parse_product_summary(
                card,
                public_details.get(str(card.get("nmID"))),
                seller_prices.get(str(card.get("nmID"))),
            )
            for card in cards
        ]

    async def get_product_details(self, credentials: dict[str, Any], product_id: str) -> ProductDetails:
        payload = {
            "settings": {
                "cursor": {"limit": 100},
                "filter": {"textSearch": str(product_id), "withPhoto": -1},
            }
        }
        data = await self._request("POST", "/content/v2/get/cards/list", credentials, json=payload)
        cards = data.get("cards") or data.get("data", {}).get("cards") or []
        if not cards:
            raise MarketplaceAPIError(f"Карточка WB {product_id} не найдена.")
        card = cards[0]
        nm_id = card.get("nmID")
        public_detail = (await self._fetch_public_details([nm_id])).get(str(nm_id))
        seller_price = (await self._fetch_seller_prices(credentials, [nm_id])).get(str(nm_id))
        public_card = await self._fetch_public_card_json(card)
        seller_info = await self._fetch_public_seller_info(card)
        return self._parse_product_details(
            card,
            public_detail=public_detail,
            public_card=public_card,
            seller_info=seller_info,
            seller_price=seller_price,
        )

    async def list_categories(
        self,
        credentials: dict[str, Any],
        *,
        parent_id: int | None = None,
    ) -> list[CategoryNode]:
        if parent_id is None:
            data = await self._request("GET", "/content/v2/object/parent/all", credentials)
        else:
            data = await self._request(
                "GET",
                "/content/v2/object/all",
                credentials,
                params={"parentID": parent_id, "limit": 1000, "offset": 0},
            )
        items = data.get("data") or data or []
        return [
            CategoryNode(
                id=int(item.get("id") or item.get("subjectID") or 0),
                name=item.get("name") or item.get("subjectName") or "Без названия",
                parent_id=parent_id,
                raw=item,
            )
            for item in items
            if item.get("id") or item.get("subjectID")
        ]

    async def get_category_attributes(
        self,
        credentials: dict[str, Any],
        category_id: int,
        *,
        required_only: bool = False,
    ) -> list[CategoryAttribute]:
        data = await self._request("GET", f"/content/v2/object/charcs/{category_id}", credentials)
        items = data.get("data") or data or []
        attributes = [
            CategoryAttribute(
                id=int(item.get("charcID") or item.get("id") or 0),
                name=item.get("name") or item.get("charcName") or "Без названия",
                required=bool(item.get("required") or item.get("isRequired")),
                type=item.get("type") or item.get("charcType"),
                raw=item,
            )
            for item in items
            if item.get("charcID") or item.get("id")
        ]
        if required_only:
            return [attribute for attribute in attributes if attribute.required]
        return attributes

    async def create_products(self, credentials: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        data = await self._request("POST", "/content/v2/cards/upload", credentials, json=items)
        return {"external_task_id": data.get("taskId") or data.get("task_id"), "raw_response": data}

    async def get_import_status(
        self,
        credentials: dict[str, Any],
        external_task_id: str | None,
    ) -> dict[str, Any]:
        if external_task_id:
            return {
                "status": "submitted",
                "message": "Для WB статус зависит от асинхронной обработки и ошибок контента.",
                "external_task_id": external_task_id,
            }
        data = await self._request("GET", "/content/v2/cards/error/list", credentials)
        errors = data.get("data") or data.get("errors") or []
        return {"status": "completed" if not errors else "failed", "errors": errors}

    async def _request(
        self,
        method: str,
        path: str,
        credentials: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = {"Authorization": credentials["token"]}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
        if response.is_error:
            raise MarketplaceAPIError(f"WB API error {response.status_code}: {response.text}")
        if not response.content:
            return {}
        return response.json()

    def _parse_product_summary(
        self,
        card: dict[str, Any],
        public_detail: dict[str, Any] | None = None,
        seller_price: dict[str, Any] | None = None,
    ) -> ProductSummary:
        variant = (card.get("variants") or [{}])[0]
        size = (card.get("sizes") or variant.get("sizes") or [{}])[0]
        media = card.get("mediaFiles") or card.get("photos") or []
        images = [item.get("big") or item.get("tm") or item.get("url") or item for item in media if item]
        vendor_code = card.get("vendorCode") or variant.get("vendorCode")
        title = (
            card.get("title")
            or variant.get("title")
            or card.get("subjectName")
            or vendor_code
            or "Без названия"
        )
        description = card.get("description") or variant.get("description")
        price = self._extract_price(card, size, public_detail, seller_price)
        stock = self._extract_stock(card, size, public_detail)
        if public_detail and not images:
            images = self._public_images_from_detail(public_detail)
        return ProductSummary(
            id=str(card.get("nmID") or vendor_code or title),
            offer_id=vendor_code,
            title=title,
            description=description,
            category_id=card.get("subjectID"),
            category_name=card.get("subjectName"),
            price=price,
            currency="RUB",
            stock=stock,
            images=[str(image) for image in images if image],
            raw={"seller_content": card, "public_detail": public_detail or {}, "seller_price": seller_price or {}},
        )

    def _parse_product_details(
        self,
        card: dict[str, Any],
        *,
        public_detail: dict[str, Any] | None = None,
        public_card: dict[str, Any] | None = None,
        seller_info: dict[str, Any] | None = None,
        seller_price: dict[str, Any] | None = None,
    ) -> ProductDetails:
        summary = self._parse_product_summary(card, public_detail, seller_price)
        summary_payload = summary.model_dump()
        summary_payload.pop("raw", None)
        variant = (card.get("variants") or [{}])[0]
        raw_characteristics = card.get("characteristics") or variant.get("characteristics") or []
        attributes: dict[str, list[str]] = {}
        for characteristic in raw_characteristics:
            name = characteristic.get("name") or str(characteristic.get("id") or "attribute")
            value = characteristic.get("value")
            if isinstance(value, list):
                attributes[name] = [str(item) for item in value if item is not None]
            elif value is None:
                attributes[name] = []
            else:
                attributes[name] = [str(value)]
        for option in (public_card or {}).get("options") or []:
            name = option.get("name") or "attribute"
            if name not in attributes:
                raw_value = option.get("variable_values") or option.get("value") or []
                if isinstance(raw_value, list):
                    attributes[name] = [str(item) for item in raw_value if item is not None]
                else:
                    attributes[name] = [str(part).strip() for part in str(raw_value).split(";") if str(part).strip()]
        sizes = card.get("sizes") or variant.get("sizes") or []
        barcode_list: list[str] = []
        for size in sizes:
            for barcode in size.get("skus") or size.get("barcodes") or []:
                barcode_list.append(str(barcode))
        if public_detail:
            for size in public_detail.get("sizes") or []:
                for stock in size.get("stocks") or []:
                    if stock.get("qty") is not None:
                        barcode_list = barcode_list or []
        return ProductDetails(
            **summary_payload,
            attributes=attributes,
            dimensions=card.get("dimensions") or self._public_dimensions(public_detail),
            sizes=sizes,
            barcode_list=barcode_list,
            brand=(card.get("brand") or variant.get("brand") or (seller_info or {}).get("trademark") or None),
            supplier=(seller_info or {}).get("supplierName") or (public_detail or {}).get("supplier"),
            supplier_id=(seller_info or {}).get("supplierId") or (public_detail or {}).get("supplierId"),
            grouped_attributes=(public_card or {}).get("grouped_options") or [],
            seller_info=seller_info or {},
            raw_sources={
                "seller_content": card,
                "public_detail": public_detail or {},
                "public_card": public_card or {},
                "seller_info": seller_info or {},
                "seller_price": seller_price or {},
            },
            raw={
                "seller_content": card,
                "public_detail": public_detail or {},
                "public_card": public_card or {},
                "seller_info": seller_info or {},
                "seller_price": seller_price or {},
            },
        )

    @staticmethod
    def _extract_price(
        card: dict[str, Any],
        size: dict[str, Any],
        public_detail: dict[str, Any] | None = None,
        seller_price: dict[str, Any] | None = None,
    ) -> str | None:
        for seller_size in (seller_price or {}).get("sizes") or []:
            for key in ("discountedPrice", "price"):
                value = seller_size.get(key)
                if value not in (None, "", 0):
                    return str(value)
        for source in (size, card):
            for key in (
                "price",
                "salePrice",
                "discountedPrice",
                "basicPrice",
                "priceWithDiscount",
            ):
                value = source.get(key)
                if value not in (None, "", 0):
                    return str(value)
        for detail_size in (public_detail or {}).get("sizes") or []:
            price = detail_size.get("price") or {}
            for key in ("product", "basic"):
                value = price.get(key)
                if value not in (None, "", 0):
                    return f"{float(value) / 100:.2f}"
        for key in ("salePriceU", "priceU"):
            value = (public_detail or {}).get(key)
            if value not in (None, "", 0):
                return f"{float(value) / 100:.2f}"
        return None

    @staticmethod
    def _extract_stock(card: dict[str, Any], size: dict[str, Any], public_detail: dict[str, Any] | None = None) -> int | None:
        for source in (size, card):
            for key in ("quantity", "stock", "stocks", "balance"):
                value = source.get(key)
                if isinstance(value, int):
                    return value
        if isinstance((public_detail or {}).get("totalQuantity"), int):
            return int(public_detail["totalQuantity"])
        total = 0
        found = False
        for detail_size in (public_detail or {}).get("sizes") or []:
            for stock in detail_size.get("stocks") or []:
                qty = stock.get("qty")
                if isinstance(qty, int):
                    total += qty
                    found = True
        if found:
            return total
        return None

    @staticmethod
    def _public_dimensions(public_detail: dict[str, Any] | None) -> dict[str, Any]:
        if not public_detail:
            return {}
        return {
            "weight": public_detail.get("weight"),
        }

    @staticmethod
    def _public_images_from_detail(public_detail: dict[str, Any]) -> list[str]:
        product_id = public_detail.get("id")
        pics = public_detail.get("pics") or 0
        if not product_id or not pics:
            return []
        basket_base = WBClient._basket_base_for_nm(int(product_id))
        volume = int(product_id) // 100000
        part = int(product_id) // 1000
        return [
            f"{basket_base}/vol{volume}/part{part}/{product_id}/images/big/{index}.webp"
            for index in range(1, int(pics) + 1)
        ]

    @staticmethod
    def _basket_base_for_nm(nm_id: int) -> str:
        volume = nm_id // 100000
        if volume <= 143:
            basket = 1
        elif volume <= 287:
            basket = 2
        elif volume <= 431:
            basket = 3
        elif volume <= 719:
            basket = 4
        elif volume <= 1007:
            basket = 5
        elif volume <= 1061:
            basket = 6
        elif volume <= 1115:
            basket = 7
        elif volume <= 1169:
            basket = 8
        elif volume <= 1313:
            basket = 9
        elif volume <= 1601:
            basket = 10
        elif volume <= 1655:
            basket = 11
        elif volume <= 1919:
            basket = 12
        elif volume <= 2045:
            basket = 13
        elif volume <= 2189:
            basket = 14
        elif volume <= 2405:
            basket = 15
        elif volume <= 2621:
            basket = 16
        elif volume <= 2837:
            basket = 17
        else:
            basket = 18
        return f"https://basket-{basket:02d}.wbbasket.ru"

    async def _fetch_public_details(self, nm_ids: list[Any]) -> dict[str, dict[str, Any]]:
        clean_ids = [str(nm_id) for nm_id in nm_ids if nm_id]
        if not clean_ids:
            return {}
        params = {"appType": 1, "curr": "rub", "dest": "-1257786", "nm": ";".join(clean_ids)}
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get("https://card.wb.ru/cards/v4/detail", params=params, headers=headers)
        if response.is_error:
            return {}
        products = response.json().get("products") or []
        return {str(item.get("id")): item for item in products if item.get("id")}

    async def _fetch_seller_prices(self, credentials: dict[str, Any], nm_ids: list[Any]) -> dict[str, dict[str, Any]]:
        if not self._has_price_scope(credentials.get("token") or ""):
            return {}
        clean_ids = [int(nm_id) for nm_id in nm_ids if nm_id]
        if not clean_ids:
            return {}
        headers = {"Authorization": credentials["token"], "Content-Type": "application/json"}
        async with httpx.AsyncClient(
            base_url="https://discounts-prices-api.wildberries.ru",
            timeout=self.timeout,
        ) as client:
            response = await client.post("/api/v2/list/goods/filter", headers=headers, json={"nmList": clean_ids})
        if response.is_error:
            return {}
        goods = response.json().get("data", {}).get("listGoods") or []
        return {str(item.get("nmID")): item for item in goods if item.get("nmID")}

    async def _fetch_public_card_json(self, card: dict[str, Any]) -> dict[str, Any]:
        url = self._infer_public_info_url(card, "info/ru/card.json")
        if not url:
            return {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
        if response.is_error:
            return {}
        return response.json()

    async def _fetch_public_seller_info(self, card: dict[str, Any]) -> dict[str, Any]:
        url = self._infer_public_info_url(card, "info/sellers.json")
        if not url:
            return {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
        if response.is_error:
            return {}
        return response.json()

    def _infer_public_info_url(self, card: dict[str, Any], suffix: str) -> str | None:
        nm_id = card.get("nmID")
        photos = card.get("photos") or []
        photo = photos[0].get("big") if photos and isinstance(photos[0], dict) else None
        if photo:
            match = re.match(r"^(https://basket-\d+\.wbbasket\.ru/vol\d+/part\d+/\d+)/images/", str(photo))
            if match:
                return f"{match.group(1)}/{suffix}"
        if nm_id:
            volume = int(nm_id) // 100000
            part = int(nm_id) // 1000
            return f"{self._basket_base_for_nm(int(nm_id))}/vol{volume}/part{part}/{nm_id}/{suffix}"
        return None

    @staticmethod
    def _has_price_scope(token: str) -> bool:
        parts = token.split(".")
        if len(parts) < 2:
            return False
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        try:
            data = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
        except Exception:
            return False
        scope = data.get("s")
        return bool(isinstance(scope, int) and scope & 4)
