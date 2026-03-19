# Phase 4 Research

## Existing code constraints

- `TransferService.launch()` уже умеет создавать job, брать preview payloads и вызывать `target_client.create_products()`.
- `TransferService.sync_status()` уже умеет опрашивать `target_client.get_import_status()` и маппить result status в `JobStatus`.
- `MappingService` после Phase 3 уже строит Yandex-ready payload c `marketCategoryId`, `offer`, `parameterValues`, `pictures`.
- Значит Phase 4 не требует нового orchestration слоя; достаточно дописать Yandex client contract и слегка укрепить UI jobs list.

## API approach

- Для submit выбран business endpoint обновления offer mappings.
- Для polling выбран business endpoint чтения offer mappings c фильтрацией по `offerIds`.
- Внутренний tracking key хранится как comma-separated `shopSku`, потому что текущая job schema имеет одно поле `external_task_id`.

## Risk points

- Yandex status не похож на Ozon task lifecycle; нужен локальный агрегатор поверх offer-level states.
- Часть ответов может отдавать notes/messages как массив строк или объектов.
- Важно не ломать существующий launch/sync контракт для WB/Ozon.

## Validation target

- Client tests покрывают submit endpoint и status aggregation.
- Integration tests покрывают `submitted -> processing -> completed` и `submitted -> failed`.
- Полный pytest и проектный verify остаются обязательными.
