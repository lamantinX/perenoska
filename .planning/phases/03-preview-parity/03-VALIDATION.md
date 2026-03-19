# Validation Strategy

**Phase:** 03 - preview-parity  
**Date:** 2026-03-18

## Planning Validation Targets

1. Every Phase 3 requirement ID is covered by at least one executable plan.
2. The resulting plans cover all four preview directions involving Yandex Market.
3. Backend preview semantics, media warnings, and UI rendering are separated into waves that minimize file conflicts.
4. Plans require concrete test coverage, not only manual smoke checks.
5. The UI plan depends on backend readiness and issue structures instead of redefining them.

## Required Evidence In Plans

- At least one plan modifies `tests/test_transfer_preview.py`.
- At least one plan modifies `app/services/transfer.py`.
- At least one plan modifies `app/static/app.js`.
- At least one plan explicitly mentions media warning or preservation behavior.
- At least one plan explicitly mentions saved mapping reuse in later preview runs.

## Failure Modes To Catch

- A plan that claims symmetry but only covers `Yandex -> Ozon` or `WB/Ozon -> Yandex`.
- A plan that treats media as import-only and skips preview warnings.
- A plan that relies on subjective acceptance criteria like "UI looks correct".
- Same-wave plans editing `app/services/transfer.py` or `app/static/app.js` in parallel.

## Checker Notes

- Treat missing explicit direction coverage as a verification failure.
- Treat missing `read_first` or weak `acceptance_criteria` as a verification failure.
- Treat omitted media warnings as a verification failure because `MEDIA-05` is in-scope for this phase.
