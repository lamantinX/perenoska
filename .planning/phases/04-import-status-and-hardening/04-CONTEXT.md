# Phase 4 Context

## Phase

- Name: Import, Status, and Hardening
- Goal: довести Yandex Market до рабочего import/status контура и закрыть финальные регрессии по трем маркетплейсам.

## Locked decisions

- Текущий inline workflow сохраняется: без фоновых очередей и без отдельного worker слоя.
- Для импорта в Yandex Market используется business-side content update flow.
- Для status polling в Yandex Market источником истины считается processing state по `shopSku`.
- Агрегированный job status строится поверх per-offer статусов: `completed`, `processing`, `failed`.
- UI не получает новый раздел; hardening идёт через текущий jobs list и существующие transfer routes.

## Scope

- Реализовать `create_products()` для `yandex_market`.
- Реализовать `get_import_status()` для `yandex_market`.
- Поддержать launch/sync для `WB -> Yandex`, `Ozon -> Yandex` и уже имеющийся job lifecycle.
- Убедиться, что media из preview попадает в import payload без регресса.
- Добавить targeted regression coverage для import/status и ошибок.

## Out of scope

- Реальные background retries.
- Полный real-time sync.
- Отдельные progress dashboards.
- Глубокая post-import analytics beyond current job result payload.
