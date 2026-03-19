# Research: Pitfalls

## Pitfall 1: Treating Yandex Market as “just another token”

- Risk: implementation ignores the business/campaign context required by many Market operations.
- Warning signs:
  - credentials model only adds a raw token field
  - request builders start hard-coding IDs
- Prevention:
  - design explicit credential/context fields in schemas early
  - keep Market context normalized in the client layer
- Phase impact:
  - must be addressed in the first integration phase

## Pitfall 2: Underestimating category/parameter complexity

- Risk: connection and product listing work, but preview/import remain unusable because required Market parameters are not modeled.
- Warning signs:
  - successful read-only demo but no reliable preview readiness
  - missing required-field reporting for Market target imports
- Prevention:
  - treat categories/attributes/parameter dictionaries as a first-class requirement
  - design preview warnings and manual mapping support early
- Phase impact:
  - core to preview/mapping phase

## Pitfall 3: Hard-coding Ozon/WB assumptions in mapping logic

- Risk: current mapping layer already has marketplace-specific shortcuts; adding a third marketplace could make logic brittle fast.
- Warning signs:
  - more underscore-helper cross-calls
  - branching spreads across routes and services instead of central payload builders
- Prevention:
  - refactor marketplace-specific payload logic behind clearer public helpers
  - keep route layer thin
- Phase impact:
  - appears during preview/import implementation

## Pitfall 4: Shipping source-only support while claiming full-cycle parity

- Risk: Yandex Market can be selected as a source, but not realistically used as a target with preview/import/status.
- Warning signs:
  - no import status semantics defined
  - no Market target required-attribute checks
- Prevention:
  - keep requirements explicitly symmetric
  - verify both directions in tests and roadmap traceability
- Phase impact:
  - roadmap and verification concern

## Pitfall 5: Forgetting the built-in UI contract

- Risk: backend supports Market, but UI cannot configure or exercise it cleanly.
- Warning signs:
  - new backend enum values without corresponding `app/static/app.js` updates
  - preview payload shape changes not reflected in frontend handling
- Prevention:
  - treat frontend changes as mandatory, not optional polish
  - test end-to-end API/UI assumptions from the existing SPA flow
- Phase impact:
  - every phase touching routes or schemas

## Pitfall 6: Trying to solve full marketplace completeness in MVP

- Risk: project stalls on rare category or edge-case parity before shipping the core integration.
- Warning signs:
  - requirements expand toward exhaustive schema support
  - no explicit boundaries around rare categories/edge cases
- Prevention:
  - define near-parity and MVP boundaries in requirements
  - prioritize typical transfer paths first
- Phase impact:
  - planning and scope control

## Confidence

- High: category/parameter complexity is the central delivery risk.
- High: the biggest false-success mode is “connection works, transfer doesn’t”.
- Medium: exact Market edge cases will depend on the chosen endpoint coverage during implementation.

## Sources

- Official Yandex Market developer docs inspected on 2026-03-17
- https://yandex.ru/dev/market/partner-api/
