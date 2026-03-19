# Summary 04-01

- В `YandexMarketClient` реализованы `create_products()` и `get_import_status()`.
- Submit использует business offer-mappings update endpoint.
- Status строится по `shopSku` из `external_task_id` и агрегируется в `completed` / `processing` / `failed`.
- Добавлены unit tests на submit payload и status aggregation.
