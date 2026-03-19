# Phase 3: Preview Parity - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver usable preview workflows for every direction that involves Yandex Market: `yandex_market -> wb`, `yandex_market -> ozon`, `wb -> yandex_market`, and `ozon -> yandex_market`. This phase must improve backend preview semantics, media preservation and warnings, mapping reuse, and the built-in UI feedback so the preview result is operationally useful before import/status parity lands in Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Preview strictness
- Preview parity should use a hybrid model rather than a binary success or failure.
- The backend should still build preview items whenever it can assemble a draft payload, even if some required fields or mappings are missing.
- Each item should expose a clear readiness state equivalent to `ready`, `needs_mapping`, or `blocked`, whether this is represented as an explicit field or as deterministic combinations of existing issue fields.
- `ready_to_import` at response level should remain strict and should only be true when every item is import-ready.

### Media policy
- Phase 3 must preserve media in preview payloads for supported directions and separately validate media completeness.
- Media problems should appear as actionable warnings, not as a silent omission.
- This phase should detect at least the practical cases that matter for preview: no images at all, empty or malformed image lists, and cases where the target preview payload would be missing media even though the source had it.
- Media validation should inform readiness but should not automatically hard-block every item unless the target preview truly cannot be formed.

### Direction symmetry
- Phase 3 requires full symmetry across all four directions involving Yandex Market.
- No direction should be treated as backend-only or secondary in preview UX.
- The plan may sequence implementation internally, but the phase is not complete until API and UI preview are usable in both source-side and target-side Yandex scenarios.

### Issue surfacing
- Preview feedback should be actionable rather than purely compact or diagnostic-heavy.
- The user must be able to understand whether a preview item is not ready because of category mismatch, missing required attributes, controlled-value gaps, or media insufficiency.
- The UI should keep using the current preview surface and modals rather than introducing a new workflow shell in this phase.

### Claude's Discretion
- Exact field naming for per-item readiness or issue summaries, as long as the UI can reliably render hybrid statuses.
- Whether media warnings are synthesized inside `TransferService`, `MappingService`, or a small helper layer, as long as warning semantics remain testable and marketplace-neutral where appropriate.
- How much preview detail is repeated in list cards versus the existing preview-card modal, provided the list remains scannable and the modal remains the deeper inspection surface.

</decisions>

<specifics>
## Specific Ideas

- The current backend already supports Yandex-related category and controlled-value persistence from Phase 2, so Phase 3 should consume that work rather than building a second mapping loop.
- The current UI already has a richer preview modal with images, payload display, mapped attributes, and issue sections; this phase should deepen that surface instead of inventing another preview page.
- The user already stated that the UI will likely be redesigned later, so this phase should optimize for current-flow usability rather than large UI architecture changes.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` - product goal and MVP boundary
- `.planning/REQUIREMENTS.md` - authoritative requirement list for `PREV-01` through `PREV-07`, `MAP-04`, `MEDIA-01`, `MEDIA-02`, `MEDIA-03`, `MEDIA-05`, `UI-03`, and `UI-04`
- `.planning/ROADMAP.md` - Phase 3 goal and success criteria
- `.planning/STATE.md` - current roadmap state
- `.planning/1-CONTEXT.md` - Yandex foundation constraints from Phase 1
- `.planning/phases/02-category-and-mapping-model/02-CONTEXT.md` - mapping and metadata decisions from Phase 2

### Preview and mapping code
- `app/services/transfer.py` - current preview orchestration, issue aggregation, and launch gate
- `app/services/mapping.py` - payload building, required-field detection, and saved-dictionary reuse
- `app/api/routes/transfers.py` - shared preview API shape
- `app/api/routes/mappings.py` - manual mapping endpoints the UI depends on during preview reruns
- `app/clients/base.py` - marketplace client contract used by preview
- `app/clients/wb.py` - WB source normalization, especially image extraction
- `app/clients/ozon.py` - Ozon product normalization and target metadata patterns
- `app/clients/yandex_market.py` - Yandex source normalization and target metadata behavior
- `app/schemas.py` - preview response and item schemas

### UI and regression anchors
- `app/static/index.html` - current preview panel, mapping buttons, and preview-card modal shell
- `app/static/app.js` - preview request flow, preview rendering, mapping modals, and actionable feedback surface
- `app/static/app.css` - preview and modal styling constraints
- `tests/test_transfer_preview.py` - dominant regression anchor for preview behavior in both directions
- `tests/test_yandex_market_client.py` - Yandex metadata behavior that preview depends on

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TransferService.preview()` already centralizes source fetch, auto-match, saved-mapping reuse, warning aggregation, and preview response construction.
- `MappingService.build_import_payload()` already returns `mapped_attributes`, `missing_required`, `missing_critical`, and dictionary issues, which is a natural base for hybrid readiness.
- The built-in SPA already supports preview rendering, a detailed preview-card modal, and issue-driven mapping dialogs, so Phase 3 can upgrade those flows rather than add new routes.

### Established Patterns
- Preview currently treats readiness as `target_category_id present + no missing_required_attributes + no missing_critical_fields`; this can be extended to explicit item status without rewriting the whole response shape.
- WB and Ozon rich-preview tests already encode the expected payload detail and warning style for non-Yandex directions.
- Yandex Market source products already normalize `images`, `title`, `description`, `category`, `price`, and `brand`, which is enough to start symmetric preview work.

### Integration Points
- `TransferService.preview()` currently fetches Yandex target attributes through the shared catalog service, but Ozon still has target-specific dictionary option population logic that is not yet mirrored for Yandex preview issue richness.
- Media is visible in normalized product models and in the preview-card modal, but readiness and warnings are not yet consistently derived from media completeness across directions.
- `app/static/app.js` preview list currently shows a simple badge based only on missing required or critical fields; it does not yet reflect hybrid states or richer Yandex-target issue reasons.

</code_context>

<deferred>
## Deferred Ideas

- Import launch, payload submission, and job status parity remain Phase 4 concerns even if Phase 3 preview structures are designed to feed them.
- Exhaustive handling of every rare Yandex category and edge-case parameter schema remains outside MVP scope.
- Full media transformation to target-specific import payloads is deferred to `MEDIA-04` in Phase 4.

</deferred>

---

*Phase: 03-preview-parity*
*Context gathered: 2026-03-18*
