# Research: Architecture

## Question

How should Yandex Market support integrate into the existing architecture?

## Suggested component boundaries

### Client layer

Add `app/clients/yandex_market.py` with responsibilities parallel to existing marketplace clients:

- API request/auth handling
- product summary normalization
- product detail normalization
- category tree retrieval
- category attribute/parameter retrieval
- import submission
- import/status lookup

### Schema layer

Extend `app/schemas.py` for:

- `Marketplace.YANDEX_MARKET`
- connection payload/response fields
- category node raw context required for Market parameter resolution
- product detail fields that may be required for Market payload construction

### Service layer

- `CatalogService` should remain the common catalog facade.
- `TransferService` should continue orchestrating preview/import/status across marketplaces.
- `MappingService` should gain Market-aware mapping and payload builders rather than moving logic into routes.

### Persistence layer

Use current tables and generalized `mappings` storage:

- `marketplace_connections` for Market credentials
- `transfer_jobs` for Market-related jobs
- `mappings` for category/value mapping persistence

## Data flow implications

### As source marketplace

1. User selects Yandex Market as source.
2. Catalog/products/categories/attributes are fetched and normalized into shared schemas.
3. Existing preview pipeline consumes normalized product data.
4. Mapping service builds WB or Ozon payloads from normalized Market product details.

### As target marketplace

1. User selects WB or Ozon as source and Yandex Market as target.
2. Target categories and parameters are fetched from Market.
3. Mapping service resolves target category and required parameter set.
4. Preview surfaces missing required Market fields/parameters.
5. Import payload is generated and submitted through the Market client.
6. Transfer job status is synced from Market response/status endpoints.

## Key architectural risks

- Yandex Market may have stricter category/parameter requirements than current WB flows.
- Business/campaign context may need to propagate deeper than the current two-marketplace model expects.
- Existing mapping helpers currently lean Ozon-specific in some places; they must be generalized further.

## Suggested build order

1. Extend enums/schemas and connection model
2. Add Yandex Market client with read-only catalog/category capabilities
3. Wire marketplace selection through services/routes/UI
4. Add preview support as source marketplace
5. Add preview support as target marketplace with mapping
6. Add import/status support
7. Harden tests and edge cases

## Confidence

- High: the adapter/service architecture is suitable for a third marketplace.
- High: `MappingService` and `TransferService` are the main integration points.
- Medium: some current abstractions may need mild refactoring to avoid hard-coded WB/Ozon assumptions.

## Sources

- Official Yandex Market developer docs inspected on 2026-03-17
- https://yandex.ru/dev/market/partner-api/
