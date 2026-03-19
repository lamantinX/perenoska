# Architecture

## High-level shape

- Monolithic FastAPI application with embedded SPA.
- Clear but lightweight layering:
  - HTTP routes in `app/api/routes/`
  - Service layer in `app/services/`
  - Marketplace adapters in `app/clients/`
  - Persistence layer in `app/db.py`
  - Shared schemas in `app/schemas.py`

## Application bootstrap

- `app/main.py` constructs `Settings`, then `ServiceContainer`, then initializes SQLite schema.
- Routers are registered directly on the app.
- Static assets are mounted at `/static`; root `/` serves the SPA shell.
- Middleware disables cache for `/` and `/static/*` to simplify local iteration.

## Dependency wiring

- `ServiceContainer` is the central composition root.
- It wires:
  - `Database`
  - `PasswordManager`
  - `CredentialVault`
  - `MarketplaceClientFactory`
  - `ConnectionService`
  - `AuthService`
  - `MappingService`
- FastAPI dependency functions pull these objects from `app.state.container`.

## Request/data flow

### Auth flow

1. Route receives `UserCreate` or `UserLogin`.
2. `AuthService` validates credentials and persists/reads user data via `Database`.
3. A session token is generated and stored in `sessions`.
4. Authenticated routes resolve the current user from the bearer token.

### Connections flow

1. Route validates connection payload for WB or Ozon.
2. `ConnectionService` builds normalized credentials.
3. Credentials are encrypted by `CredentialVault`.
4. Encrypted blob is upserted into `marketplace_connections`.

### Catalog flow

1. Route identifies marketplace and limit/category id.
2. `CatalogService` resolves credentials and client implementation.
3. Client calls the marketplace API and normalizes responses into shared schemas.

### Transfer preview/import flow

1. Preview request enters `TransferService.preview()`.
2. Source and target categories are loaded through `CatalogService`.
3. Saved category/dictionary mappings are loaded from SQLite.
4. Source product details are fetched concurrently with a semaphore.
5. Target category is resolved either from explicit request, saved mapping, or heuristic matching.
6. Target attributes are loaded and cached per category/type tuple.
7. `MappingService.build_import_payload()` maps source data into WB or Ozon import payloads.
8. Preview aggregates warnings, missing fields, dictionary issues, and category issues.
9. Launch persists a transfer job, sends payloads to target marketplace, then updates job status/result.
10. Sync re-queries the target marketplace and maps remote status into local job state.

## Architectural patterns in use

- Simple DI container instead of framework-heavy inversion.
- Shared schema normalization to decouple API routes from raw marketplace responses.
- Thin routes, fatter services.
- Marketplace polymorphism through `MarketplaceClient` abstract base class.
- Persistence implemented as explicit SQL methods rather than repositories per entity.

## Important architectural asymmetries

- `CatalogService` has an Ozon-specific escape hatch: `get_category_attributes_for_category()` checks for `get_category_attributes_for_node`.
- `TransferService` directly calls some semi-private helpers on `MappingService` such as `_resolve_ozon_type_id()` and `_is_brand_attribute()`.
- `ConnectionService` and `AuthService` are clean service boundaries, but mapping persistence is still accessed directly through `container.database` from routes and services.

## Current boundaries that matter for changes

- Changes to route contracts likely require synchronized edits in `app/static/app.js`.
- Changes in `app/db.py` affect both live behavior and tests because schema creation is done at runtime.
- Changes in `app/services/mapping.py` and `app/services/transfer.py` have the highest behavioral blast radius.
- Marketplace client parsing logic is a separate change surface from orchestration logic; tests reflect this split.
