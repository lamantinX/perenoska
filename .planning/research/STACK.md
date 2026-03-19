# Research: Stack

## Question

What is the practical stack and integration shape for adding Yandex Market seller support to this project?

## Recommended approach

- Keep the current FastAPI + SQLite + embedded SPA architecture.
- Add a dedicated Yandex Market client alongside `WBClient` and `OzonClient`.
- Extend existing marketplace enum/schema/service abstractions instead of building a side path.
- Model Yandex Market connection credentials explicitly around the identifiers used by the official API.

## Yandex Market integration shape

- Official seller APIs are exposed through Yandex Market Partner / Marketplace APIs.
- The API model is business-oriented rather than just token-oriented:
  - business-level identifier
  - campaign/shop identifier in many operations
  - OAuth/token-based authorization
- Product operations are centered on offers/cards, publication state, and category parameter requirements.

## What this means for `perenoska`

### Credentials/config

- Add a Yandex Market connection payload to `ConnectionUpsert` and related schemas.
- Likely required connection fields:
  - OAuth token / API token
  - `business_id`
  - one or more campaign/shop identifiers depending on how the current seller account model is exposed in the chosen endpoints

### Client responsibilities

The new `YandexMarketClient` should cover the same contract shape as existing clients:

- `list_products(...)`
- `get_product_details(...)`
- `list_categories(...)`
- `get_category_attributes(...)`
- `create_products(...)`
- `get_import_status(...)`

Likely additional helper responsibilities:

- resolve business/campaign context
- normalize Market-specific parameter metadata
- map Market publication/import status into local `JobStatus`

### Service-layer impact

- `CatalogService` can likely stay stable if client contract parity is preserved.
- `TransferService` will need new branching only where payload formats and import status semantics differ.
- `MappingService` will need a third target/source payload dialect for Yandex Market.

## Recommended implementation stack

- Reuse `httpx.AsyncClient` for Yandex requests to stay consistent with existing clients.
- Reuse current Pydantic schema style in `app/schemas.py`.
- Reuse current generalized mappings table instead of adding a separate Yandex-only mapping storage path.
- Reuse current UI approach in `app/static/app.js` rather than introducing a frontend framework.

## What not to add yet

- No queue/broker just for Yandex Market.
- No separate service/process for synchronization.
- No ORM or migration framework solely because of the new marketplace.

## Confidence

- High: Yandex Market can fit the current adapter-based architecture.
- High: new marketplace support will require schema, client, mapping, transfer, and UI changes together.
- Medium: exact credential field set depends on the specific official endpoint family chosen during implementation.

## Sources

- Official Yandex Market developer docs inspected on 2026-03-17
- https://yandex.ru/dev/market/partner-api/
