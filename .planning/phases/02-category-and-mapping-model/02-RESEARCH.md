# Phase 2 Research: Category and Mapping Model

**Phase:** 2 - Category and Mapping Model
**Date:** 2026-03-18
**Status:** complete

## Objective

Research what Phase 2 needs in order to plan Yandex Market target metadata and reusable mappings well: category tree usage, parameter metadata shape, controlled-value behavior, generalized persistence, and current-flow UI constraints.

## Findings

### 1. Yandex target metadata should be modeled as parameter-driven, not category-only

Official Yandex Market docs describe target metadata in two layers:

- category tree from `POST /v2/categories/tree`
- category parameters from `POST /v2/category/{categoryId}/parameters`

The parameter response is the real source of truth for preview and later import preparation. It defines required fields, acceptable values, units, multi-value rules, and constraints. Planning implication: `YandexMarketClient.get_category_attributes()` must become a first-class implementation in this phase instead of staying a stub.

### 2. Import-leaning metadata is justified by the API shape

The Yandex docs explicitly tie parameter metadata to future product update methods and validation rules. The parameter payload exposes enough structure to avoid a second normalization pass later:

- `id` and parameter identity
- required-ness
- controlled values or `values[].id` for option-based parameters
- unit information
- constraints and value-shape hints
- whether custom values are allowed

Planning implication: Phase 2 should normalize more than just `required`; otherwise Phase 3 preview and Phase 4 import will need a schema expansion under active feature work.

### 3. Leaf-category discipline matters for saved mappings

Yandex Market parameter methods work on leaf categories. Error docs explicitly call out non-leaf category misuse. Planning implication:

- saved category mappings that target Yandex must resolve to leaf category IDs
- preserved path or label context is important for debugging because the tree is large and labels can repeat
- the generalized mapping store can stay ID-based, but should save extra context for diagnostics and reuse

### 4. The current generalized mappings store is already the right persistence base

Local code review shows that the repo already has a generalized `mappings` table with:

- `mapping_type`
- `source_key`
- `source_label`
- `source_context_json`
- `target_key`
- `target_label`
- `target_context_json`

Planning implication: Phase 2 should keep using `save_mapping()` and `list_mappings()` for both category and controlled-value mappings involving Yandex Market, instead of adding Yandex-only tables.

### 5. The biggest backend gap is marketplace-generalization, not storage

`app/api/routes/mappings.py` currently hardcodes Ozon assumptions in `save_dictionary_mappings()`:

- rejects non-Ozon targets
- resolves `type_id` through Ozon category context
- requires `get_dictionary_values()` semantics specific to Ozon

Planning implication: Phase 2 should split this into generalized controlled-value mapping logic plus marketplace-specific resolution helpers. That is a larger planning concern than SQLite changes.

### 6. The biggest UI gap is reuse of current preview-driven mapping flows

`app/static/app.js` already renders:

- category issues
- dictionary issues
- brand-mapping interactions

The UI is not missing a framework; it is missing Yandex-aware issue payloads and save endpoints that accept Yandex as source or target. Planning implication: a current-flow UI plan is realistic in this phase without inventing a new screen.

## Implementation recommendations

### Backend metadata

- Implement `YandexMarketClient.get_category_attributes()` via `POST /v2/category/{categoryId}/parameters`
- Normalize Yandex parameter metadata into `CategoryAttribute` with import-leaning raw context
- Preserve controlled values, unit options, required flags, and constraint hints in normalized/raw fields

### Mapping model

- Keep category mappings keyed by marketplace-native IDs
- Save path/label/context in `source_context_json` and `target_context_json`
- Generalize controlled-value mapping persistence so Yandex Market can participate without Ozon-only guards

### Preview compatibility prep

- Ensure the normalized attribute shape is directly consumable by `MappingService.build_import_payload()`
- Make any marketplace-specific required/dictionary checks explicit helpers rather than implicit Ozon-only assumptions

### UI

- Reuse existing category and dictionary mapping modal flows
- Update preview payload consumption and save requests only where Yandex Market support requires it
- Avoid introducing a separate mapping management screen in this phase

## Risks to manage in planning

- Yandex parameter metadata is richer and less Ozon-like than a simple `dictionary_id` clone, so forced symmetry may create brittle abstractions
- Generalizing `save_dictionary_mappings()` without a clear marketplace helper boundary could spread Ozon assumptions deeper into the codebase
- If plans do not reserve time for tests around saved-mapping reuse, Phase 3 preview work will inherit hidden regressions

## Validation Architecture

Phase 2 can keep the current pytest-centered loop with focused subsets after each plan and a full regression at the end.

- Quick metadata tests: `python -m pytest tests/test_yandex_market_client.py -k categories`
- Quick mapping tests: `python -m pytest tests/test_dictionary_mappings.py tests/test_transfer_preview.py -k mapping`
- Full suite: `python -m pytest`

## Sources

- Yandex Market category tree: https://yandex.ru/dev/market/partner-api/doc/en/reference/categories/getCategoriesTree
- Yandex Market category parameters: https://yandex.ru/dev/market/partner-api/doc/en/reference/content/getCategoryContentParameters
- Yandex Market parameter value rules: https://yandex.ru/dev/market/partner-api/doc/ru/step-by-step/parameter-values
- Yandex Market offer update and mapping context: https://yandex.ru/dev/market/partner-api/doc/en/reference/business-assortment/updateOfferMappings
- Yandex Market error code reference for category misuse: https://yandex.ru/dev/market/partner-api/doc/en/concepts/error-codes
