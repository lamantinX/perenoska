# Perenoska

## What This Is

`perenoska` is a local FastAPI MVP for transferring product cards between marketplaces through a built-in web UI. Today the product already covers Wildberries and Ozon; the current project focus is expanding that MVP so Yandex Market becomes a first-class marketplace in the same transfer flow.

The intended result is a three-marketplace transfer tool where a user can connect Yandex Market, preview transfers, map categories and attributes, and launch imports in both directions between Yandex Market, Wildberries, and Ozon from the existing interface.

## Core Value

Users can reliably move product cards between Wildberries, Ozon, and Yandex Market through one workflow with preview, mapping, and import control.

## Requirements

### Validated

- ✓ User can register, log in, and work through authenticated API sessions — existing
- ✓ User can save and reuse marketplace connections for Wildberries and Ozon — existing
- ✓ User can load marketplace catalog data, categories, and attributes for Wildberries and Ozon — existing
- ✓ User can build transfer preview between Wildberries and Ozon with auto-matching and manual mapping support — existing
- ✓ User can launch transfer jobs and sync import status for existing marketplace directions — existing
- ✓ User can operate the current MVP through the built-in SPA in `app/static/` — existing

### Active

- [ ] Add Yandex Market API connection support alongside existing Wildberries and Ozon connections
- [ ] Let users read Yandex Market catalog data needed for transfer preview and import preparation
- [ ] Support full preview flow for transfers from Yandex Market to Wildberries and Ozon
- [ ] Support full preview flow for transfers from Wildberries and Ozon to Yandex Market
- [ ] Support import launch and status handling for transfers where Yandex Market is the target marketplace
- [ ] Extend category and attribute mapping so Yandex Market works at near-parity with current MVP expectations
- [ ] Extend the built-in UI so Yandex Market is available in connection management, source/target selection, preview, mapping, launch, and status views

### Out of Scope

- Full guaranteed support for every rare or highly specialized product schema in all marketplaces — MVP scope is near parity, not exhaustive marketplace completeness
- Background queues, retry orchestration, and production-grade async job infrastructure — current product remains an MVP with inline job execution
- Real-time synchronization between marketplaces after import — not part of the existing MVP transfer model
- Broad product-management tooling outside transfer workflows (mass editing, analytics, content governance) — not core to the transfer value

## Context

The repository is an existing brownfield FastAPI application with SQLite persistence, built-in static frontend, marketplace adapters in `app/clients/`, orchestration in `app/services/transfer.py`, and mapping logic in `app/services/mapping.py`. The current codebase already supports Wildberries and Ozon, including connection storage, catalog/category loading, preview generation, transfer launch, status sync, and manual mapping endpoints.

This project phase is not about inventing a new product direction. It is about extending the current MVP architecture so Yandex Market becomes a third marketplace with almost the same practical capability level as the current WB/Ozon support. That means the work will touch backend adapters, schemas, services, routes, persistence, tests, and the built-in UI together.

The most sensitive areas are already known from the codebase map: `app/db.py`, `app/services/transfer.py`, `app/services/mapping.py`, `app/static/app.js`, and marketplace client implementations. Changes to route contracts must stay aligned with frontend expectations.

## Constraints

- **Architecture**: Extend the existing FastAPI + SQLite + embedded SPA structure — the project is already brownfield and should evolve inside current patterns
- **Product Scope**: Deliver near parity for Yandex Market within MVP boundaries — the goal is strong functional symmetry, not exhaustive enterprise coverage
- **Marketplace Coverage**: Support full transfer cycle in both directions involving Yandex Market — connection, catalog read, preview, mapping, import, and status handling must all participate
- **Testing**: Behavior changes should be covered by tests first or alongside implementation — repository instructions explicitly require updating tests for behavior changes
- **UI Compatibility**: Backend route and schema changes must be reflected in `app/static/app.js` — the frontend is tightly coupled to API responses
- **Persistence**: Do not edit SQLite data files manually — schema and data handling must change through code only

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Treat Yandex Market as a first-class marketplace, not a limited connector | The requested outcome is full transfer cycle in both directions, not a partial integration | — Pending |
| Target near parity with current WB/Ozon MVP behavior | User wants the strongest MVP version without requiring exhaustive marketplace completeness | — Pending |
| Keep the work inside existing MVP architecture and UI | The current product is already working brownfield code; expansion should reuse current service, route, and SPA model | — Pending |

---
*Last updated: 2026-03-17 after initialization*
