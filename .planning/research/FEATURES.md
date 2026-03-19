# Research: Features

## Table stakes for this expansion

For this product, adding Yandex Market at MVP-near-parity implies these user-visible capabilities are table stakes:

- Save and validate Yandex Market credentials
- See Yandex Market in marketplace selectors everywhere the UI currently supports WB/Ozon
- Load Yandex Market catalog items for selection as transfer sources
- Load Yandex Market category structure and required parameters for preview/mapping
- Build preview from Yandex Market to WB/Ozon
- Build preview from WB/Ozon to Yandex Market
- Launch imports where Yandex Market is the target
- Read import/publication status back from Yandex Market into the job list/status UI
- Support manual category mapping where auto-match is insufficient
- Support manual attribute/value mapping where marketplace dictionaries or enumerations require it

## Near-parity expectations

“Almost parity” with current WB/Ozon support implies:

- The main transfer workflow remains symmetric
- User should not need a separate UX branch just because one side is Yandex Market
- Preview should surface missing required fields and warnings before import
- Mapping persistence should work across repeated runs

## Differentiators not required for this phase

These may be useful later but are not required to satisfy the current request:

- Post-import synchronization between marketplaces
- Bulk editing after preview as a standalone feature
- Rich diagnostics dashboard for marketplace-specific errors
- Multi-campaign routing logic in the UI
- Automated continuous sync jobs

## Anti-features / explicit de-priorities

- Trying to cover every rare category or schema before shipping the first Yandex Market version
- Building a parallel product-management suite instead of a transfer workflow
- Re-architecting the application while adding the third marketplace

## Complexity notes

- Product source support is easier than target support; target support requires valid import payload generation and status semantics.
- Category/parameter support is the real complexity center, not just credentials.
- “Full cycle in both directions” means requirements must cover both source normalization and target payload construction for Yandex Market.

## Dependency observations

- UI support depends on backend enum/schema changes landing first.
- Preview readiness for Yandex Market depends on category and attribute metadata retrieval.
- Manual mappings depend on being able to represent Yandex-specific parameter contexts in the generalized mapping store.

## Confidence

- High: connection/catalog/preview/import/mapping/UI are all mandatory for this initiative.
- High: category and attribute handling will determine whether the integration feels real or superficial.
- Medium: some Yandex Market-specific product metadata may need scoped fallback behavior to stay within MVP boundaries.

## Sources

- Official Yandex Market developer docs inspected on 2026-03-17
- https://yandex.ru/dev/market/partner-api/
