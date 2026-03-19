# Phase 2: Category and Mapping Model - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Add Yandex Market target category and parameter metadata plus reusable mapping persistence needed by later preview and import flows. This phase expands the current generalized mapping model and current-flow UI, but does not yet claim full preview or import parity for Yandex Market.

</domain>

<decisions>
## Implementation Decisions

### Target metadata depth
- Phase 2 should use import-leaning metadata for Yandex Market, not a preview-minimum subset.
- The normalized metadata layer should include categories, parameter IDs, names, required flags, value types, enum or dictionary-like options when available, basic constraints, and unit information when it affects future payload building.
- This phase may stop short of import submission, but should avoid a second metadata redesign in Phase 3 or 4.

### Category mapping identity
- Category mappings involving Yandex Market should remain ID-based in the primary key path.
- Saved mappings must also preserve stable context alongside IDs, including path or label data useful for diagnostics and future reuse.
- The generalized mapping store should carry enough target/source context to explain long Yandex category paths in preview and UI flows.

### Attribute mapping scope
- Manual attribute mappings for this phase are limited to controlled values only.
- Phase 2 should support enum or dictionary-like mappings where the target marketplace expects a specific option or value identifier.
- Free-text normalization or broad transform rules are out of scope for this phase.

### UI exposure
- Yandex Market support must be wired into the current mapping flows UI rather than deferred to backend-only support.
- This does not require a new standalone mappings screen.
- The current category-mapping and dictionary-like mapping interactions should accept Yandex Market as source or target wherever Phase 2 backend support exists.

### Claude's Discretion
- Exact normalized field names inside `raw` or auxiliary metadata structures.
- Whether Yandex-specific helper methods live in `MappingService`, the client, or route-layer helpers, as long as the generalized flow remains coherent.
- How much path text to include in labels versus `target_context_json`, provided mappings stay debuggable and reusable.

</decisions>

<specifics>
## Specific Ideas

- The user expects near parity, so this phase should not hide Yandex Market behind backend-only plumbing.
- UI will likely be redesigned later, but this phase still needs real usability in the current built-in SPA.
- The existing generalized `mappings` table is the preferred reuse point rather than creating a Yandex-only persistence model.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` - product goal and MVP boundary
- `.planning/REQUIREMENTS.md` - authoritative requirement list for `CAT-03`, `CAT-04`, `MAP-01`, `MAP-02`, `MAP-03`
- `.planning/ROADMAP.md` - phase boundary and success criteria
- `.planning/STATE.md` - current roadmap state
- `.planning/1-CONTEXT.md` - locked decisions from Phase 1 that constrain Yandex Market identity and normalization

### Mapping and catalog code
- `app/services/mapping.py` - current category auto-match and dictionary handling patterns
- `app/services/transfer.py` - current preview orchestration and saved-mapping reuse points
- `app/api/routes/catalog.py` - current category and attribute API shape
- `app/api/routes/mappings.py` - current manual mapping save flows and Ozon-specific constraints
- `app/db.py` - generalized mapping persistence and uniqueness rules
- `app/clients/base.py` - marketplace client contract for categories and attributes
- `app/clients/ozon.py` - reference implementation for target metadata and dictionary-value retrieval
- `app/clients/yandex_market.py` - Yandex client introduced in Phase 1 and expected extension point for metadata
- `app/static/app.js` - current-flow UI behavior for category and dictionary mapping interactions

### Tests and regression anchors
- `tests/test_transfer_preview.py` - current preview behavior, category issue shape, and saved-mapping reuse
- `tests/test_dictionary_mappings.py` - generalized mapping persistence expectations
- `tests/test_ozon_client.py` - target metadata and dictionary-value patterns already covered in tests

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Database.save_mapping()` and `list_mappings()` already provide a generalized persistence layer keyed by connection pair, mapping type, and source key.
- `app/api/routes/mappings.py` already has the shape for manual category and dictionary saves; it mainly needs marketplace-generalization rather than a fresh endpoint family.
- `MappingService.auto_match_category()` and `build_import_payload()` already centralize target metadata usage and are the natural place to extend Yandex-aware logic.

### Established Patterns
- Ozon currently acts as the only marketplace with controlled dictionary values, so its client and route behavior are the closest reference pattern for Yandex target metadata.
- Category issues already carry `source_key`, `target_*` labels, and options lists, which matches the direction needed for reusable Yandex mappings.
- The UI mapping flow is driven by preview responses rather than a separate admin surface, so Phase 2 should preserve that shape.

### Integration Points
- `YandexMarketClient.get_category_attributes()` is still unimplemented and is the main backend gap for `CAT-04`.
- `save_dictionary_mappings()` in `app/api/routes/mappings.py` currently hard-blocks non-Ozon targets and will need to become marketplace-aware.
- `TransferService` already loads saved mappings before preview; Phase 2 should keep new mapping keys compatible with that retrieval path.

</code_context>

<deferred>
## Deferred Ideas

- Broad free-text attribute transformation rules belong to later phases if they become necessary.
- Full preview parity, media completeness warnings, and import/status behavior remain in Phases 3 and 4.
- Exhaustive support for rare Yandex category schemas remains out of MVP scope.

</deferred>

---

*Phase: 02-category-and-mapping-model*
*Context gathered: 2026-03-18*
