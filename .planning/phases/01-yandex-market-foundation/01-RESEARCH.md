# Phase 1 Research: Yandex Market Foundation

**Phase:** 1 - Yandex Market Foundation  
**Date:** 2026-03-18  
**Status:** complete

## Objective

Research the API and implementation details needed to plan Phase 1 well: explicit connection shape, source catalog reads, category listing, and UI integration for Yandex Market.

## Findings

### 1. Connection contract should be explicit

Phase 1 should not model Yandex Market as a token-only connector. The official API model is organized around seller/business and campaign/shop context, and practical product/catalog operations are campaign-scoped.

Recommended Phase 1 credential shape:

- `token`
- `business_id`
- `campaign_id`

Implication for implementation:

- `ConnectionUpsert` validation must add a Yandex Market-specific branch
- encrypted connection payload can continue to live as JSON in `marketplace_connections`
- UI connection form needs three inputs, not one or two

### 2. Source catalog can fit the current client abstraction

The current `MarketplaceClient` contract is sufficient for Phase 1 if the new client implements:

- `list_products(credentials, limit=...)`
- `get_product_details(credentials, product_id)`
- `list_categories(credentials, parent_id=None)`

Phase 1 does not need target attribute metadata or import submission yet.

Implication for implementation:

- `app/clients/base.py` can likely stay unchanged for Phase 1
- `CatalogService` and route layer should continue working if `Marketplace.YANDEX_MARKET` is added cleanly

### 3. Catalog normalization should target preview-ready core

Even though Phase 1 does not implement preview for Yandex Market, the new client should normalize to the same core fields already used by `ProductSummary` and `ProductDetails`:

- `id`
- `offer_id`
- `title`
- `description`
- `category_id`
- `category_name`
- `price`
- `stock`
- `images`
- `raw` / `raw_sources`

Implication for implementation:

- avoid a temporary UI-only mapper
- include enough raw context in details to support later Phase 2/3 work

### 4. Categories belong in Phase 1, parameters do not

Phase 1 should expose Yandex Market categories because they are part of marketplace identity and future mapping groundwork. But full parameter/attribute metadata belongs to Phase 2.

Implication for implementation:

- support `GET /catalog/categories?marketplace=yandex_market`
- do not yet extend preview/mapping endpoints for Market-specific parameter logic

### 5. UI work is real foundation work, not polish

Because the project uses a built-in SPA with hardcoded marketplace forms and selectors, UI support must land in Phase 1 to satisfy the phase goal.

Minimum visible UI surface for this phase:

- Yandex Market connection form and badge/masked state
- marketplace selectors
- source catalog loading and source product details for Yandex Market

Implication for implementation:

- `app/static/index.html`, `app/static/app.js`, and likely `app/static/app.css` all need edits
- selector synchronization logic currently assumes only `wb` and `ozon` in some branches and must be generalized

## Implementation recommendations

### Backend

- Add `Marketplace.YANDEX_MARKET` to the enum in `app/schemas.py`
- Extend `ConnectionUpsert` with:
  - `business_id: int | None`
  - `campaign_id: int | None`
- Extend connection validation and masking for Yandex Market in `app/services/connections.py`
- Add `app/clients/yandex_market.py`
- Register new client in `MarketplaceClientFactory`

### Client

The new client should:

- use `httpx.AsyncClient`
- send Authorization header using the stored token
- treat `campaign_id` as a core routing parameter for source catalog calls
- normalize list/details/categories into existing schema models

### Tests

Phase 1 needs coverage for:

- connection save/list for Yandex Market
- catalog products for Yandex Market
- catalog product details for Yandex Market
- catalog categories for Yandex Market
- non-regression for existing WB/Ozon selector and connection behavior

## Risks to manage in planning

- current `app/static/app.js` has two-marketplace assumptions and manual form wiring
- schema changes ripple through routes, validation, UI, and tests together
- if the client normalization is too thin, Phase 3 will need rework

## Validation Architecture

Phase 1 can use the existing pytest-based validation loop.

- Quick command: `python -m pytest tests/test_auth_and_connections.py tests/test_yandex_market_client.py`
- Full command: `python -m pytest`
- Sampling approach:
  - after backend contract/client tasks: focused pytest subset
  - after UI/backend integration tasks: full pytest

## Sources

- Yandex Market Partner API overview: https://yandex.ru/dev/market/partner-api/
- Campaign context docs used for seller scope research: https://yandex.ru/dev/market/partner-api/doc/ru/reference/campaigns/getCampaigns
- Offer list / campaign-scoped catalog research: https://yandex.ru/dev/market/partner-api/doc/ru/reference/business-assortment/getOffers
- Category tree research: https://yandex.ru/dev/market/partner-api/doc/ru/reference/categories/getCategoriesTree
- Offer mappings update reference for future compatibility boundary: https://yandex.ru/dev/market/partner-api/doc/ru/reference/business-assortment/updateOfferMappings
