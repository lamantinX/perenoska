# Phase 4 Validation

## Requirements trace

- `MEDIA-04`: import payload to Yandex keeps pictures from preview payload.
- `IMPT-01..06`: launch and sync work for Yandex-target jobs, including failure surfacing.
- `UI-05`: jobs list remains usable and readable for Yandex-related jobs.
- `QUAL-01`, `QUAL-02`: targeted regressions plus full suite stay green.

## Evidence plan

1. Add failing tests for `YandexMarketClient.create_products()`.
2. Add failing tests for `YandexMarketClient.get_import_status()`.
3. Add failing integration tests for transfer launch/sync against Yandex target.
4. Implement minimal code to satisfy tests.
5. Re-run targeted tests.
6. Run full `pytest`.
7. Run `scripts/verify.ps1`.

## Exit criteria

- Yandex import/status tests pass.
- Existing WB/Ozon regression suite stays green.
- UI JS syntax check passes after jobs list hardening.
