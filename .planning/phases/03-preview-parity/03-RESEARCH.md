# Phase 3: Preview Parity - Research

**Date:** 2026-03-18
**Phase:** 03 - Preview Parity
**Status:** Complete

## Research Question

What needs to be true in the current codebase and Yandex Market API model to plan usable preview parity in both directions involving Yandex Market, including actionable mapping feedback and media handling?

## Current Codebase Findings

### 1. Preview orchestration is already centralized

`app/services/transfer.py` is the decisive execution point for this phase. It already:
- fetches source product details;
- loads source and target categories;
- reuses saved category mappings;
- resolves target category metadata;
- builds import payloads through `MappingService`;
- aggregates category issues, dictionary issues, and warnings;
- computes response-level `ready_to_import`.

This means Phase 3 should remain centered on `TransferService.preview()` and its immediate collaborators instead of adding a second preview path.

### 2. Hybrid readiness is not yet explicit

The current readiness rule is effectively:
- target category exists;
- there are no missing required attributes;
- there are no missing critical fields.

This supports `ready_to_import`, but it does not yet expose a per-item readiness state that distinguishes:
- preview built but category still unresolved;
- preview built but mappings are incomplete;
- preview built with warnings only;
- preview fully ready.

Phase 3 should therefore add explicit per-item readiness semantics or an equivalent deterministic status model that the UI can render.

### 3. Media data is present but not yet validated as preview quality

Source normalization already preserves image lists:
- WB normalization extracts `mediaFiles` and photo URLs.
- Ozon rich-product tests already expect image-bearing detail payloads.
- Yandex source normalization from earlier phases preserves `images`.

The preview-card modal in `app/static/app.js` already renders:
- hero image;
- thumbnail gallery;
- empty-state fallback when no images exist.

What is missing is preview-level policy:
- whether lack of images is only a display concern or a transfer concern;
- when to warn about media completeness;
- how those warnings affect hybrid readiness.

### 4. Mapping reuse is already strong enough to leverage

Phase 2 added:
- saved category mappings involving Yandex Market;
- controlled-value mappings for Yandex target metadata;
- Yandex-aware category issue options and target contexts.

Phase 3 should reuse these capabilities and focus on making them visibly effective in preview:
- rerun preview after save;
- reduce repeated issue noise;
- surface the remaining unresolved issues clearly.

### 5. UI already has the right containers

The current built-in SPA already includes:
- preview list cards;
- preview-card modal;
- category mapping modal;
- brand/dictionary mapping modal;
- preview progress feedback.

Therefore Phase 3 should modify the existing preview rendering rather than add:
- a new preview route family;
- a dedicated mapping page;
- a separate Yandex-only workflow.

## External API Findings

### 1. Yandex category parameters are the canonical source of preview validation

Official Yandex Market docs for `POST /v2/category/{categoryId}/parameters` say the method returns category characteristics and the rules for transmitting them later in product update requests, including:
- `required`;
- `type`;
- `allowCustomValues`;
- `multivalue`;
- acceptable values and units;
- constraints;
- optional cabinet-specific behavior through `businessId`.

Sources:
- [Lists of product characteristics by category](https://yandex.ru/dev/market/partner-api/doc/en/reference/content/getCategoryContentParameters)
- [Transfer of characteristic values](https://yandex.ru/dev/market/partner-api/doc/ru/step-by-step/parameter-values)

Planning implication:
- preview for Yandex target should be driven by normalized category-parameter metadata rather than hardcoded attribute assumptions;
- controlled-value and unit warnings should be explainable from this metadata.

### 2. Yandex content updates split main fields from categorical characteristics

Official docs distinguish:
- main product data such as names, descriptions, and photos via `POST /v2/businesses/{businessId}/offer-mappings/update`;
- category-specific characteristics via `POST /v2/businesses/{businessId}/offer-cards/update`.

The docs also indicate that category changes and parameter updates are validated against `marketCategoryId` and `parameterValues`, with warnings or errors when category/parameter combinations are incomplete or invalid.

Sources:
- [Adding and editing products](https://yandex.ru/dev/market/partner-api/doc/en/step-by-step/assortment-add-goods)
- [Editing product category characteristics](https://yandex.ru/dev/market/partner-api/doc/en/reference/content/updateOfferContent)

Planning implication:
- preview toward Yandex should treat title, description, and images as distinct from category-parameter completeness;
- media and main-field insufficiency can be actionable warnings even when categorical mapping is the dominant blocker;
- import payload assembly in Phase 4 will likely split across two Yandex API shapes, so Phase 3 should preserve enough draft structure to support that later.

### 3. Yandex media is operationally important for target readiness

The Yandex "adding and editing products" flow explicitly includes product information such as names, descriptions, and photos when adding products to the catalog. The same documentation points out that product information updates are not instantly reflected and can produce warnings or later review consequences.

Source:
- [Adding and editing products](https://yandex.ru/dev/market/partner-api/doc/en/step-by-step/assortment-add-goods)

Planning implication:
- preview toward Yandex should not silently drop images;
- missing media should be surfaced as warnings at minimum;
- media-presence regression coverage is necessary for `WB -> Yandex` and `Ozon -> Yandex`, while `Yandex -> WB/Ozon` needs preservation checks from the source side.

## Risk Areas

### 1. Response-shape drift in preview schemas

If Phase 3 adds hybrid status fields too casually, the UI and tests can drift apart. Any schema extension should be deliberate and backward-compatible with the current preview rendering path.

### 2. Ozon-specific dictionary assumptions leaking into Yandex preview

The current preview path has Ozon-only dictionary option enrichment. Phase 3 should not force identical mechanics for Yandex if the metadata model already carries enough controlled values in `CategoryAttribute.dictionary_values`.

### 3. Overloading readiness with every warning

The user explicitly chose validated media with hybrid readiness, not strict gating for every imperfection. The plan must keep the difference between:
- import blockers;
- mapping blockers;
- non-blocking warnings.

### 4. UI overload

The preview list is already dense. Adding actionable issue surfacing should likely split between:
- concise per-card readiness summaries;
- deeper issue detail in the preview-card modal and existing mapping dialogs.

## Recommended Planning Shape

### Wave 1: Backend preview parity and explicit item readiness
- Extend preview semantics across all four Yandex directions.
- Add or update tests first for symmetric preview coverage.
- Make per-item readiness explicit and ensure saved mappings are reused automatically.

### Wave 2: Media preservation and actionable issue surfacing
- Add preview-level media warnings and preservation checks.
- Distinguish warning-only states from mapping or required-field blockers.
- Keep logic in backend services and tests rather than burying it in UI-only conditionals.

### Wave 3: Current-flow UI parity
- Upgrade preview cards and preview modal to show hybrid readiness and actionable issues.
- Ensure mapping dialogs and rerun flow remain coherent for Yandex as both source and target.

## Validation Architecture

To consider Phase 3 well-planned, the plans should prove all of the following:
- every Phase 3 requirement ID appears in at least one plan;
- all four preview directions involving Yandex are explicitly covered by tests or acceptance criteria;
- media preservation and media-warning behavior are planned separately;
- the UI plan consumes the backend readiness and issue model rather than inventing divergent semantics;
- plan waves do not create same-wave edit collisions on the same core files.

## Sources

- [Yandex Market API for sellers: category parameters](https://yandex.ru/dev/market/partner-api/doc/en/reference/content/getCategoryContentParameters)
- [Yandex Market API for sellers: transfer of characteristic values](https://yandex.ru/dev/market/partner-api/doc/ru/step-by-step/parameter-values)
- [Yandex Market API for sellers: adding and editing products](https://yandex.ru/dev/market/partner-api/doc/en/step-by-step/assortment-add-goods)
- [Yandex Market API for sellers: editing category characteristics](https://yandex.ru/dev/market/partner-api/doc/en/reference/content/updateOfferContent)

---

*Research completed for Phase 03 on 2026-03-18*
