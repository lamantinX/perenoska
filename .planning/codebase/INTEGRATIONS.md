# Integrations

## External systems

### Wildberries

- Adapter: `app/clients/wb.py`
- Credentials shape: `{"token": "..."}`
- Main API families used:
  - Seller content cards list: `/content/v2/get/cards/list`
  - Subject/category tree: `/content/v2/object/parent/all`, `/content/v2/object/all`
  - Subject attributes: `/content/v2/object/charcs/{category_id}`
  - Upload cards: `/content/v2/cards/upload`
  - Error list fallback: `/content/v2/cards/error/list`
- Additional public WB sources are queried for enrichment:
  - `https://card.wb.ru/cards/v4/detail`
  - basket-hosted `card.json` / `sellers.json`
  - price API `https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter`

### Ozon

- Adapter: `app/clients/ozon.py`
- Credentials shape: `{"client_id": "...", "api_key": "..."}`
- Main API families used:
  - Product list: `/v3/product/list`
  - Product details: `/v3/product/info/list`
  - Product import: `/v3/product/import`
  - Import status: `/v1/product/import/info`
  - Category tree: `/v1/description-category/tree`
  - Category attributes: `/v1/description-category/attribute`
  - Dictionary values: `/v1/description-category/attribute/values`
  - Product description enrichment: `/v1/product/info/description`
  - Attribute enrichment fallback: `/v4/products/info/attributes`

## Internal integration boundaries

- Routes depend on services through FastAPI deps in `app/api/deps.py`.
- Services depend on a shared `ServiceContainer` from `app/services/container.py`.
- `CatalogService` is the abstraction over marketplace catalog clients.
- `TransferService` orchestrates preview, import launch, and status sync across:
  - `CatalogService`
  - `ConnectionService`
  - `MappingService`
  - `MarketplaceClientFactory`
  - `Database`

## Database integration

- Persistence adapter: `app/db.py`
- Tables currently in use:
  - `users`
  - `sessions`
  - `marketplace_connections`
  - `transfer_jobs`
  - `dictionary_mappings`
  - `mappings`
- In practice, generalized `mappings` is the current canonical store for both category and dictionary mappings.

## Auth/session integration

- Auth endpoints: `app/api/routes/auth.py`
- Session lookup is performed on every authenticated request using bearer tokens.
- Current-user resolution is handled in `app/services/auth.py`.

## Static UI integration

- `/` serves `app/static/index.html`.
- `/static/*` serves JS/CSS/assets.
- Routes mounted under `/api/v1` are consumed by the built-in SPA in `app/static/app.js`.
- Route additions must be reflected in the SPA because there is no generated client layer.

## Mapping-specific integrations

- Manual category mapping API: `POST /api/v1/mappings/categories`
- Manual dictionary mapping API: `POST /api/v1/mappings/dictionary`
- Transfer preview reads saved mappings back from SQLite before running heuristics.
- Ozon brand mapping uses live dictionary lookup to validate user-selected values before saving mappings.

## Error handling patterns

- External client failures raise `MarketplaceAPIError`.
- Service and route layers convert domain/precondition failures into `HTTPException`.
- Some enrichment failures are intentionally soft:
  - Ozon missing attribute/description endpoints can degrade to partial product data.
  - WB public enrichment and seller price fetches can return empty results without failing the whole request.
