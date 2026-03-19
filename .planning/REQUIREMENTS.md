# Requirements: Perenoska

**Defined:** 2026-03-17
**Core Value:** Users can reliably move product cards between Wildberries, Ozon, and Yandex Market through one workflow with preview, mapping, and import control.

## v1 Requirements

### Connections

- [ ] **CONN-01**: User can save Yandex Market connection credentials through the existing connections workflow
- [ ] **CONN-02**: User can view whether Yandex Market connection is configured in the same way as WB and Ozon connections
- [ ] **CONN-03**: User can reuse saved Yandex Market credentials across catalog, preview, import, and status operations

### Catalog

- [ ] **CAT-01**: User can list products from Yandex Market as a transfer source
- [ ] **CAT-02**: User can load Yandex Market product details in normalized internal format suitable for preview
- [ ] **CAT-03**: User can load Yandex Market category data needed for transfer target selection and mapping
- [ ] **CAT-04**: User can load Yandex Market attribute or parameter metadata needed to build transfer preview and import payloads

### Transfer Preview

- [ ] **PREV-01**: User can build preview for transfers from Yandex Market to Wildberries
- [ ] **PREV-02**: User can build preview for transfers from Yandex Market to Ozon
- [ ] **PREV-03**: User can build preview for transfers from Wildberries to Yandex Market
- [ ] **PREV-04**: User can build preview for transfers from Ozon to Yandex Market
- [ ] **PREV-05**: Preview surfaces missing required fields when Yandex Market is the target marketplace
- [ ] **PREV-06**: Preview surfaces category mismatches and mapping issues when Yandex Market is source or target
- [ ] **PREV-07**: Preview includes warnings when media required for target transfer is missing or incomplete

### Mapping

- [ ] **MAP-01**: User can use auto-matching to propose Yandex Market category mappings where sufficient data exists
- [ ] **MAP-02**: User can manually save category mappings involving Yandex Market through the existing mappings flow
- [ ] **MAP-03**: User can manually save attribute or dictionary-like mappings involving Yandex Market where target parameters require controlled values
- [ ] **MAP-04**: Saved mappings involving Yandex Market are reused in later preview runs

### Media

- [ ] **MEDIA-01**: Product images from Yandex Market are preserved in preview when transferring to Wildberries or Ozon
- [ ] **MEDIA-02**: Product images from Wildberries are preserved in preview when transferring to Yandex Market
- [ ] **MEDIA-03**: Product images from Ozon are preserved in preview when transferring to Yandex Market
- [ ] **MEDIA-04**: Import payloads involving Yandex Market include media in the format required by the target marketplace
- [ ] **MEDIA-05**: Preview warns when media cannot be transferred with acceptable completeness for the chosen direction

### Import and Status

- [ ] **IMPT-01**: User can launch import from Yandex Market to Wildberries through the existing transfer workflow
- [ ] **IMPT-02**: User can launch import from Yandex Market to Ozon through the existing transfer workflow
- [ ] **IMPT-03**: User can launch import from Wildberries to Yandex Market through the existing transfer workflow
- [ ] **IMPT-04**: User can launch import from Ozon to Yandex Market through the existing transfer workflow
- [ ] **IMPT-05**: User can sync status for transfer jobs where Yandex Market is the target marketplace
- [ ] **IMPT-06**: Transfer job history and detail views show Yandex Market jobs in the same way as existing marketplace jobs

### UI

- [ ] **UI-01**: User can select Yandex Market in the built-in UI anywhere marketplace selection is currently available
- [ ] **UI-02**: User can configure Yandex Market credentials through the built-in UI
- [ ] **UI-03**: User can run preview flows involving Yandex Market through the built-in UI without manual API calls
- [ ] **UI-04**: User can review mapping issues involving Yandex Market through the built-in UI
- [ ] **UI-05**: User can launch and inspect transfer jobs involving Yandex Market through the built-in UI

### Quality

- [ ] **QUAL-01**: Automated tests cover connection, catalog, preview, mapping, import, and status behavior involving Yandex Market
- [ ] **QUAL-02**: Existing WB/Ozon transfer behavior remains intact after adding Yandex Market support

## v2 Requirements

### Yandex Market Enhancements

- **YMK-01**: User can work with multiple Yandex Market business or campaign contexts through richer connection management
- **YMK-02**: User can transfer more complex or rare Yandex Market category schemas with deeper parameter coverage
- **YMK-03**: User can resolve marketplace-specific media transformation issues with richer diagnostics and remediation

### Transfer Platform

- **PLAT-01**: Transfer jobs run through background workers with retries and throttling
- **PLAT-02**: User can keep marketplaces synchronized after import through scheduled or continuous sync
- **PLAT-03**: User can edit price and stock strategies independently from card transfer payloads

## Out of Scope

| Feature | Reason |
|---------|--------|
| Exhaustive support for every rare Yandex Market category and parameter combination | The target is near parity within MVP scope, not complete marketplace coverage |
| Real-time or scheduled sync after import | Current initiative is about transfer workflows, not continuous synchronization |
| Queue-based job execution, retries, and rate-limit orchestration | Existing MVP executes inline and this initiative is not a platform rewrite |
| Product analytics, mass content operations, or marketplace management beyond transfer workflows | Not core to the product value being extended |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONN-01 | Phase 1 | Pending |
| CONN-02 | Phase 1 | Pending |
| CONN-03 | Phase 1 | Pending |
| CAT-01 | Phase 1 | Pending |
| CAT-02 | Phase 1 | Pending |
| CAT-03 | Phase 2 | Pending |
| CAT-04 | Phase 2 | Pending |
| PREV-01 | Phase 3 | Pending |
| PREV-02 | Phase 3 | Pending |
| PREV-03 | Phase 3 | Pending |
| PREV-04 | Phase 3 | Pending |
| PREV-05 | Phase 3 | Pending |
| PREV-06 | Phase 3 | Pending |
| PREV-07 | Phase 3 | Pending |
| MAP-01 | Phase 2 | Pending |
| MAP-02 | Phase 2 | Pending |
| MAP-03 | Phase 2 | Pending |
| MAP-04 | Phase 3 | Pending |
| MEDIA-01 | Phase 3 | Pending |
| MEDIA-02 | Phase 3 | Pending |
| MEDIA-03 | Phase 3 | Pending |
| MEDIA-04 | Phase 4 | Pending |
| MEDIA-05 | Phase 3 | Pending |
| IMPT-01 | Phase 4 | Pending |
| IMPT-02 | Phase 4 | Pending |
| IMPT-03 | Phase 4 | Pending |
| IMPT-04 | Phase 4 | Pending |
| IMPT-05 | Phase 4 | Pending |
| IMPT-06 | Phase 4 | Pending |
| UI-01 | Phase 1 | Pending |
| UI-02 | Phase 1 | Pending |
| UI-03 | Phase 3 | Pending |
| UI-04 | Phase 3 | Pending |
| UI-05 | Phase 4 | Pending |
| QUAL-01 | Phase 5 | Pending |
| QUAL-02 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 35 total
- Mapped to phases: 35
- Unmapped: 0

---
*Requirements defined: 2026-03-17*
*Last updated: 2026-03-17 after initial definition*
