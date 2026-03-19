# Conventions

## General coding style

- Python code uses `from __future__ import annotations` consistently.
- Type hints are present across most functions and methods.
- Domain objects are modeled with Pydantic schemas rather than ad hoc dicts at the API boundary.
- Modules are small-to-medium and organized by responsibility rather than by technical framework layers.

## Naming patterns

- Services are named `*Service`.
- Marketplace adapters are named `WBClient` and `OzonClient`.
- Factory/container names are explicit: `MarketplaceClientFactory`, `ServiceContainer`.
- Shared enums and schemas use descriptive names such as `TransferPreviewResponse`, `CategoryNode`, `Marketplace`.
- Test names follow scenario style: `test_preview_...`, `test_launch_...`, `test_get_...`.

## API and service conventions

- Routes are thin and rely on FastAPI dependency injection.
- Service methods raise `HTTPException` directly for many user-facing precondition failures.
- Route prefixes are grouped under `/api/v1`.
- Response models are declared on routes rather than inferred.

## Persistence conventions

- SQL is written inline in `app/db.py`.
- Each DB method usually opens its own SQLite connection with `row_factory=sqlite3.Row`.
- Rows are normalized to dictionaries using `_row_to_dict()`.
- JSON payload/result fields are serialized with `json.dumps(..., ensure_ascii=True)`.

## Error handling conventions

- External API failures use `MarketplaceAPIError`.
- User-facing auth/validation errors use `HTTPException` with explicit status codes.
- Some external enrichment calls degrade gracefully instead of aborting the request.
- Status normalization converts heterogeneous remote states into internal `JobStatus`.

## Mapping and payload conventions

- Mapping logic relies on normalized lowercase strings and synonym tables.
- Ozon payloads and WB payloads are built in separate helpers.
- Missing data is split into:
  - required attributes
  - critical fields
  - warnings
- Manual mappings are stored in generalized mapping rows with typed `mapping_type` values such as `category` and `dictionary_brand`.

## Testing conventions

- Tests favor explicit fakes/stubs over heavy mocking frameworks.
- Many tests exercise the real FastAPI app through `TestClient`.
- Client tests subclass real adapter classes and override `_request()`.
- Temp SQLite DBs are created via `tmp_path`.

## Notable implicit conventions

- UTF-8 / Russian product-facing strings are intended, even if current terminal output shows mojibake.
- Frontend and backend evolve together; route contract changes should be mirrored in `app/static/app.js`.
- Product logic changes are expected to be covered by tests first, per `AGENTS.md`.

## Convention drift / rough edges

- `dictionary_mappings` table still exists in schema, but current reads/writes are largely routed through generalized `mappings`.
- Some service internals call underscore-prefixed helpers across class boundaries, which weakens encapsulation.
- There is no enforced formatter/linter config in the inspected Python tooling.
