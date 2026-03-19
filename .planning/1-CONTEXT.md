# Phase 1 Context

**Phase:** 1 - Yandex Market Foundation  
**Created:** 2026-03-18

## Phase Goal

Introduce Yandex Market as a recognized marketplace across schemas, connection flows, basic catalog source reads, and the built-in UI without pulling full preview/import parity into this phase.

## Locked Decisions

### 1. Credentials shape

Yandex Market connection support in Phase 1 must store:

- token
- `business_id`
- `campaign_id`

This phase should not rely on hidden autodetection as the primary connection model. The connection contract should be explicit in backend schemas, persistence, and UI forms.

**Why this is locked:**

- Future phases need stable business/campaign context for API calls.
- Building the integration on token-only assumptions would likely create rework.
- The user wants Yandex Market treated as a first-class marketplace, not a best-effort connector.

## 2. Catalog scope

Phase 1 catalog support for Yandex Market includes:

- product list
- product details
- categories

Phase 1 does **not** need full target parameter/attribute metadata support; that belongs to Phase 2.

**Why this is locked:**

- Categories are foundational for a real marketplace presence and upcoming mapping work.
- Pulling full parameter support into Phase 1 would blur the roadmap boundary.

## 3. Normalization

Phase 1 should normalize Yandex Market product data to a preview-ready core model, not just a UI-minimum subset.

Expected core normalized fields:

- `id`
- `offer_id`
- `title`
- `description`
- `category_id`
- `category_name`
- `price`
- `stock`
- `images`
- enough `raw` or source-context fields to support future preview/mapping work without redesigning the model

**Why this is locked:**

- Phase 3 depends on a stable normalized product model.
- A UI-only normalization in Phase 1 would likely create avoidable schema churn later.

## 4. UI exposure

In Phase 1, Yandex Market should appear in:

- connection management UI
- marketplace selectors
- source catalog views

It does not need fake/full preview or import parity in this phase.

**Why this is locked:**

- Users should be able to observe real progress in the built-in UI during foundation work.
- Showing Yandex Market only in settings/selectors would make the phase feel incomplete.
- Showing it everywhere as if full transfer support exists would misrepresent the actual roadmap boundary.

## Code Context

### Main integration points

- `app/schemas.py`
  - add marketplace enum/value support
  - extend connection payload and response schemas
  - ensure catalog/product/category schemas can carry Yandex Market normalized data

- `app/services/connections.py`
  - support encrypting/decrypting the new Yandex Market credential shape
  - preserve current WB/Ozon behavior

- `app/db.py`
  - existing `marketplace_connections` table can likely be reused without schema change because credentials are encrypted JSON
  - connection handling logic and any assumptions around marketplace values need review

- `app/clients/base.py`
  - current abstract contract is already close to what Phase 1 needs

- `app/services/container.py`
  - add client factory support for Yandex Market

- `app/services/catalog.py`
  - should remain the common façade if the new client implements the same contract

- `app/api/routes/catalog.py`
  - ensure marketplace validation and route behavior accept Yandex Market

- `app/api/routes/connections.py`
  - ensure request validation and connection upsert/list behavior accept Yandex Market

- `app/main.py`
  - router wiring may stay stable if route modules stay unchanged, but schema and UI expectations will change

- `app/static/app.js`
  - must expose Yandex Market in connection forms, selectors, and source catalog interactions

### Existing reusable patterns

- Marketplace polymorphism already exists through `MarketplaceClient` and `MarketplaceClientFactory`
- Connection credentials are already encrypted as JSON blobs, which is friendly to adding a richer credential shape
- Product and category loading already flows through `CatalogService`
- The built-in SPA already knows how to work with multiple marketplaces; the Yandex Market option should extend those paths instead of creating a separate UI branch

### Existing constraints

- This is brownfield code with working WB/Ozon behavior that must not regress
- Route/schema changes must stay aligned with `app/static/app.js`
- Product logic changes should be covered by tests

## Explicit Non-Goals For Phase 1

- No preview parity for Yandex Market yet
- No import launch/status parity yet
- No full attribute/parameter mapping layer yet
- No attempt to solve rare-category completeness

## Planning Implications

The downstream plan for Phase 1 should likely break around:

1. schema and connection contract updates
2. Yandex Market client + container wiring
3. catalog/category read support
4. UI exposure for connections, selectors, and source catalog
5. focused tests and regression checks

---
*Last updated: 2026-03-18 after phase discussion*
