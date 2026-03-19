# Structure

## Top-level layout

- `app/` - application package.
- `app/api/` - FastAPI dependency helpers and route modules.
- `app/clients/` - marketplace adapter implementations.
- `app/services/` - business logic and orchestration.
- `app/static/` - embedded frontend.
- `tests/` - pytest coverage for API/service/client behavior.
- `docs/codex/` - local project docs for navigation and workflow.
- `docs/superpowers/` - planning/spec notes created via local superpower workflows.
- `scripts/` - project verification helpers.
- `data/` - local SQLite database file.

## Key backend files

- `app/main.py` - FastAPI app factory and static mounting.
- `app/config.py` - environment-backed settings dataclass.
- `app/schemas.py` - Pydantic schemas and enums shared everywhere.
- `app/db.py` - schema DDL plus all DB access helpers.
- `app/security.py` - password hashing, credential encryption, session token generation.

## Route modules

- `app/api/routes/health.py`
- `app/api/routes/auth.py`
- `app/api/routes/connections.py`
- `app/api/routes/catalog.py`
- `app/api/routes/transfers.py`
- `app/api/routes/mappings.py`

## Service modules

- `app/services/auth.py` - user register/login/session lookup.
- `app/services/connections.py` - connection persistence and masking.
- `app/services/catalog.py` - marketplace catalog facade.
- `app/services/mapping.py` - category matching and payload shaping.
- `app/services/transfer.py` - preview/import/status orchestration.
- `app/services/container.py` - service wiring and client factory.

## Client modules

- `app/clients/base.py` - abstract contract and shared error type.
- `app/clients/wb.py` - Wildberries API + public enrichment parsing.
- `app/clients/ozon.py` - Ozon API, category type resolution, dictionary lookups.

## Frontend files

- `app/static/index.html` - app shell.
- `app/static/app.js` - all SPA behavior and API calls.
- `app/static/app.css` - UI styles.

## Test layout

- `tests/test_auth_and_connections.py` - auth, root page, connections, catalog limit pass-through.
- `tests/test_transfer_preview.py` - preview/import/status flows, category mapping, brand dictionary behavior, client pagination stubs.
- `tests/test_dictionary_mappings.py` - persistence rules for generalized mappings.
- `tests/test_ozon_client.py` - Ozon client paging, dictionary values, detail enrichment.

## Documentation and workflow references

- `AGENTS.md` - repo-local operating instructions for Codex.
- `README.md` - project overview and local commands.
- `docs/codex/project-overview.md`
- `docs/codex/file-map.md`
- `docs/codex/workflow.md`
- `docs/codex/architecture.md`

## Naming and organization patterns

- Marketplace-specific code is split primarily by `wb` and `ozon`.
- Shared enums use `Marketplace.WB` and `Marketplace.OZON`.
- API route modules map 1:1 to major product domains.
- Tests favor scenario-oriented names like `test_preview_*`, `test_launch_*`, `test_get_*`.

## Files and directories to treat carefully

- `app/db.py` - schema + persistence coupling point.
- `app/services/transfer.py` - central orchestration with multiple side effects.
- `app/services/mapping.py` - heuristic logic and payload builders.
- `app/static/app.js` - unbundled frontend state machine.
- `app/clients/wb.py` and `app/clients/ozon.py` - integration-specific parsing.
