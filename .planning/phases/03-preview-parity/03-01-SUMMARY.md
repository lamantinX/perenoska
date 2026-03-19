# Plan 03-01 Summary

## Outcome

- Added explicit hybrid preview readiness via `TransferPreviewItem.readiness` with values `ready`, `needs_mapping`, and `blocked`.
- Extended backend preview support so `wb -> yandex_market` and `ozon -> yandex_market` build Yandex-target draft payloads instead of falling back to WB payload shape.
- Kept response-level `ready_to_import` strict while making item-level status actionable.

## Key Files

- `app/schemas.py`
- `app/services/transfer.py`
- `app/services/mapping.py`
- `tests/test_transfer_preview.py`

## Verification

- `python -m pytest tests/test_transfer_preview.py -k yandex`

## Notes

- Saved mappings involving Yandex Market continue to be reused by the same preview path.
