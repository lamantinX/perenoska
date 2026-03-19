# Roadmap: Perenoska

**Created:** 2026-03-17
**Mode:** yolo
**Granularity:** standard
**Model profile:** balanced

## Summary

- Phases: 4
- v1 requirements: 35
- Mapped requirements: 35
- Unmapped requirements: 0

## Phases

| # | Phase | Goal | Requirements |
|---|-------|------|--------------|
| 1 | Yandex Market Foundation | Add marketplace identity, connection handling, basic catalog source support, and first-class UI presence | CONN-01, CONN-02, CONN-03, CAT-01, CAT-02, UI-01, UI-02 |
| 2 | Category and Mapping Model | Support Yandex Market category metadata and reusable mapping persistence across preview flows | CAT-03, CAT-04, MAP-01, MAP-02, MAP-03 |
| 3 | Preview Parity | Make preview flows involving Yandex Market usable in both directions, including media and mapping issues | PREV-01, PREV-02, PREV-03, PREV-04, PREV-05, PREV-06, PREV-07, MAP-04, MEDIA-01, MEDIA-02, MEDIA-03, MEDIA-05, UI-03, UI-04 |
| 4 | Import, Status, and Hardening | Enable launch and status handling for Yandex Market transfers and close the expansion with regression safety | MEDIA-04, IMPT-01, IMPT-02, IMPT-03, IMPT-04, IMPT-05, IMPT-06, UI-05, QUAL-01, QUAL-02 |

## Phase Details

### Phase 1: Yandex Market Foundation

**Goal:** Introduce Yandex Market as a recognized marketplace across schemas, connection flows, source catalog reads, and the built-in UI.

**Requirements:** CONN-01, CONN-02, CONN-03, CAT-01, CAT-02, UI-01, UI-02

**Success criteria:**
1. Backend schemas, routes, and services accept Yandex Market as a marketplace value without breaking WB/Ozon flows.
2. Users can configure Yandex Market credentials through the current connections UI and see the saved state.
3. The system can read Yandex Market product summaries and product details into the shared internal schema model.
4. The UI exposes Yandex Market in connection and marketplace-selection controls where appropriate.

### Phase 2: Category and Mapping Model

**Goal:** Add Yandex Market category and attribute metadata support plus reusable mapping persistence needed by preview and import flows.

**Requirements:** CAT-03, CAT-04, MAP-01, MAP-02, MAP-03

**Success criteria:**
1. The backend can fetch and normalize Yandex Market categories and target parameter metadata required by preview.
2. Auto-match can propose Yandex Market category mappings using the current mapping architecture.
3. Manual category mappings involving Yandex Market can be saved and reused.
4. Manual attribute/value mappings involving Yandex Market can be saved in the generalized mapping store.

### Phase 3: Preview Parity

**Goal:** Deliver usable preview workflows in both directions involving Yandex Market, including media preservation and mapping feedback.

**Requirements:** PREV-01, PREV-02, PREV-03, PREV-04, PREV-05, PREV-06, PREV-07, MAP-04, MEDIA-01, MEDIA-02, MEDIA-03, MEDIA-05, UI-03, UI-04

**Success criteria:**
1. Users can generate preview for all four directions involving Yandex Market through the API and UI.
2. Preview correctly reports missing required fields, category mismatches, and mapping issues when Yandex Market is source or target.
3. Images/media are preserved in preview payloads for supported directions and warnings appear when they are insufficient.
4. Saved mappings involving Yandex Market are applied automatically in later preview runs.

### Phase 4: Import, Status, and Hardening

**Goal:** Complete the workflow by launching imports, syncing statuses, and proving the Yandex Market expansion is stable across all three marketplaces.

**Requirements:** MEDIA-04, IMPT-01, IMPT-02, IMPT-03, IMPT-04, IMPT-05, IMPT-06, UI-05, QUAL-01, QUAL-02

**Success criteria:**
1. Users can launch transfer jobs in all directions involving Yandex Market through the existing workflow shape.
2. Import payloads sent to Yandex Market include media in a valid target format.
3. Transfer job list and detail views show Yandex Market-related jobs correctly.
4. Status sync works for transfers where Yandex Market is the target marketplace.
5. Automated tests cover connection, catalog, preview, mapping, import, and status behavior involving Yandex Market.
6. Existing WB/Ozon behavior remains green after the new marketplace support is added.
7. Known high-risk integration points have targeted regression coverage.

## Traceability Check

- Phase 1: 7 requirements
- Phase 2: 5 requirements
- Phase 3: 14 requirements
- Phase 4: 10 requirements

All v1 requirements are mapped exactly once.

---
*Last updated: 2026-03-18 after completing Phase 4 implementation*
