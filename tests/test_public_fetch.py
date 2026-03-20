from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


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
    return TestClient(app)


# ---------------------------------------------------------------------------
# URL parsing tests (no HTTP calls needed)
# ---------------------------------------------------------------------------

class TestUrlParsing:
    def test_wb_seller_url(self, tmp_path):
        client = build_client(tmp_path)
        wb_products_response = {
            "data": {
                "products": [
                    {
                        "id": 123456,
                        "name": "Test Product",
                        "brand": "TestBrand",
                        "priceU": 150000,
                        "rating": 4.5,
                        "pics": 3,
                    }
                ]
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = wb_products_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/public/fetch",
                json={"url": "https://www.wildberries.ru/seller/987654", "limit": 20},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["marketplace"] == "wb"
        assert data["source_type"] == "seller"
        assert data["source_id"] == "987654"

    def test_wb_product_url(self, tmp_path):
        client = build_client(tmp_path)
        wb_product_response = {
            "data": {
                "products": [
                    {
                        "id": 555111,
                        "name": "Single Product",
                        "brand": "BrandX",
                        "priceU": 99900,
                        "rating": 4.0,
                        "pics": 1,
                    }
                ]
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = wb_product_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/public/fetch",
                json={"url": "https://www.wildberries.ru/catalog/555111/detail.aspx", "limit": 5},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["marketplace"] == "wb"
        assert data["source_type"] == "product"
        assert data["source_id"] == "555111"

    def test_wb_seller_url_short_domain(self, tmp_path):
        client = build_client(tmp_path)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"products": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/public/fetch",
                json={"url": "https://wb.ru/seller/111222"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["marketplace"] == "wb"
        assert data["source_id"] == "111222"

    def test_ozon_seller_url_returns_credentials_required(self, tmp_path):
        client = build_client(tmp_path)
        resp = client.post(
            "/api/v1/public/fetch",
            json={"url": "https://www.ozon.ru/seller/my-shop-123456/"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["marketplace"] == "ozon"
        assert data["source_type"] == "seller"
        assert data["source_id"] == "123456"
        assert data["products"] == []
        assert data["total"] == 0
        assert data["requires_credentials"] is True
        assert data["message"] is not None

    def test_ozon_product_url_returns_credentials_required(self, tmp_path):
        client = build_client(tmp_path)
        resp = client.post(
            "/api/v1/public/fetch",
            json={"url": "https://www.ozon.ru/product/some-cool-product-789012/"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["marketplace"] == "ozon"
        assert data["source_type"] == "product"
        assert data["source_id"] == "789012"
        assert data["requires_credentials"] is True

    def test_yandex_market_shop_url_returns_credentials_required(self, tmp_path):
        client = build_client(tmp_path)
        resp = client.post(
            "/api/v1/public/fetch",
            json={"url": "https://market.yandex.ru/shop--some-shop/456789"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["marketplace"] == "yandex_market"
        assert data["source_type"] == "seller"
        assert data["source_id"] == "456789"
        assert data["requires_credentials"] is True

    def test_yandex_market_product_url_returns_credentials_required(self, tmp_path):
        client = build_client(tmp_path)
        resp = client.post(
            "/api/v1/public/fetch",
            json={"url": "https://market.yandex.ru/product--some-title/654321"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["marketplace"] == "yandex_market"
        assert data["source_type"] == "product"
        assert data["source_id"] == "654321"
        assert data["requires_credentials"] is True

    def test_unknown_url_returns_422(self, tmp_path):
        client = build_client(tmp_path)
        resp = client.post(
            "/api/v1/public/fetch",
            json={"url": "https://amazon.com/product/12345"},
        )
        assert resp.status_code == 422

    def test_limit_validation_too_large(self, tmp_path):
        client = build_client(tmp_path)
        resp = client.post(
            "/api/v1/public/fetch",
            json={"url": "https://www.wildberries.ru/seller/123", "limit": 200},
        )
        assert resp.status_code == 422

    def test_limit_validation_zero(self, tmp_path):
        client = build_client(tmp_path)
        resp = client.post(
            "/api/v1/public/fetch",
            json={"url": "https://www.wildberries.ru/seller/123", "limit": 0},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# WB product mapping tests
# ---------------------------------------------------------------------------

class TestWbProductMapping:
    def test_products_mapped_to_product_summary(self, tmp_path):
        client = build_client(tmp_path)
        wb_response = {
            "data": {
                "products": [
                    {
                        "id": 100000000,
                        "name": "Awesome Widget",
                        "brand": "WidgetCo",
                        "priceU": 250000,
                        "rating": 4.8,
                        "pics": 5,
                    }
                ]
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = wb_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/public/fetch",
                json={"url": "https://www.wildberries.ru/seller/42", "limit": 10},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        product = data["products"][0]
        assert product["id"] == "100000000"
        assert product["title"] == "Awesome Widget"
        assert product["category_name"] == "WidgetCo"
        assert product["price"] == "2500"
        assert product["currency"] == "RUB"
        # Image URL should be derived from nm_id
        assert len(product["images"]) == 1
        assert "wbbasket.ru" in product["images"][0]

    def test_product_with_no_price(self, tmp_path):
        client = build_client(tmp_path)
        wb_response = {
            "data": {
                "products": [
                    {
                        "id": 12345678,
                        "name": "Free Item",
                        "brand": "FreeBrand",
                    }
                ]
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = wb_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/public/fetch",
                json={"url": "https://www.wildberries.ru/seller/99", "limit": 5},
            )

        assert resp.status_code == 200
        product = resp.json()["products"][0]
        assert product["price"] is None

    def test_empty_products_list(self, tmp_path):
        client = build_client(tmp_path)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"products": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/public/fetch",
                json={"url": "https://www.wildberries.ru/seller/0", "limit": 10},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["products"] == []
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# WB basket URL derivation tests
# ---------------------------------------------------------------------------

class TestWbBasketDerivation:
    def test_basket_ranges(self, tmp_path):
        """Verify basket numbers are derived from nm_id correctly."""
        from app.api.routes.public import _wb_basket_number, _wb_image_url

        # vol=143 (nm_id=14300000) → basket 01
        assert _wb_basket_number(143) == "01"
        # vol=144 → basket 02
        assert _wb_basket_number(144) == "02"
        # vol=288 → basket 03
        assert _wb_basket_number(288) == "03"
        # vol=2838 → basket 18
        assert _wb_basket_number(2838) == "18"
        # vol=9999 → basket 18
        assert _wb_basket_number(9999) == "18"

    def test_image_url_format(self, tmp_path):
        from app.api.routes.public import _wb_image_url

        nm_id = 100000000  # vol=1000, part=100000
        url = _wb_image_url(nm_id)
        assert "basket-" in url
        assert "wbbasket.ru" in url
        assert str(nm_id) in url
        assert url.endswith(".webp")


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_wb_api_failure_returns_422(self, tmp_path):
        client = build_client(tmp_path)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=httpx.HTTPError("Connection refused"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/public/fetch",
                json={"url": "https://www.wildberries.ru/seller/123", "limit": 10},
            )

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, str)
        assert len(detail) > 0

    def test_no_auth_required(self, tmp_path):
        """Public endpoint must work without any Authorization header."""
        client = build_client(tmp_path)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"products": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/api/v1/public/fetch",
                json={"url": "https://www.wildberries.ru/seller/1"},
                # Deliberately no Authorization header
            )

        assert resp.status_code == 200
