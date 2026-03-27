---
description: Корректный перенос карточек товаров между Wildberries и Ozon — маппинг полей (name, description→annotation, vendor_code, brand, status=draft), категорий (авто через LLM + ручной выбор), брендов (WB→Ozon через API, нечёткий поиск), фото и атрибутов. Приоритет WB→Ozon. Товары с вариантами вне scope. — проектирование распределения ответственностей между сервисами. — план тестов.
standard: specs/.instructions/analysis/plan-test/standard-plan-test.md
standard-version: v1.4
index: specs/analysis/README.md
parent: design.md
children: [plan-dev.md]
status: RUNNING
milestone: v1.0.0
---

# 0002: Wb ozon product transfer — Plan Tests

## Резюме

Документ покрывает **1 сервис** — монолитное FastAPI-приложение `perenoska` (SVC-1). Всего **37 TC-N**: 30 per-service (SVC-1) + 7 системных. Покрыты все **7 STS-N** и все **19 REQ-N** из Discussion.

**Scope:** маппинг полей WB↔Ozon (`description↔annotation`, `name`, `vendor_code`, `brand`/`brand_id`, `images`, атрибуты), LLM-маппинг категорий через OpenRouter, многошаговый поиск брендов (`exact → case-insensitive → substring`), блокировка переноса при неразрешённых ручных полях, обработка ошибок внешних API.

**Применимые типы тестов:** unit, integration, e2e.

**Неприменимые типы:**
- **load** — в Discussion и Design нет SLA по RPS или конкурентности; критерий успеха упоминает только latency preview < 10s и transfer < 30s для одиночного переноса, что покрывается integration-тестом, а не нагрузочным.
- **smoke** — нет CI/CD деплоя и health-endpoint в scope данной цепочки; smoke-тесты актуальны после деплоя в production-среде, которая вне scope v1.0.0.

**Ключевые тестовые решения:**
- WB/Ozon API мокируются через `container.client_factory.register_override(marketplace, FakeClient())` — изоляция от внешних систем.
- LLM (OpenRouter/AsyncOpenAI) мокируется через `unittest.mock.AsyncMock` — детерминированные ответы на LLM-запросы в unit/integration тестах.
- SQLite разворачивается через `create_app(settings)` с `tmp_path` pytest-фикстурой — полная изоляция БД между тестами.
- `TransferService` stateless — тестируется per-request через `TestClient`.

## SVC-1: perenoska

### Acceptance-сценарии

| ID | Описание | Тип | Источник | Данные |
|----|----------|-----|----------|--------|
| TC-1 | `MappingService.build_import_payload()` для направления WB→Ozon помещает значение поля `description` из WB-карточки в поле `annotation` payload Ozon, а не в `description` | unit | REQ-1, SVC-1 § 9 | wb_card_with_description |
| TC-2 | `MappingService.build_import_payload()` для WB→Ozon переносит поле `vendorCode` WB в поле `offer_id` payload Ozon | unit | REQ-2, SVC-1 § 9 | wb_card_with_description |
| TC-3 | `MappingService.build_import_payload()` для WB→Ozon переносит поле `title` WB в поле `name` payload Ozon | unit | REQ-12, SVC-1 § 9 | wb_card_with_description |
| TC-4 | `MappingService.build_import_payload()` для WB→Ozon переносит список URL из `mediaFiles` WB-карточки в поле `images` payload Ozon | unit | REQ-4, SVC-1 § 9 | wb_card_with_images |
| TC-5 | `MappingService.build_import_payload()` для направления Ozon→WB помещает значение поля `annotation` из Ozon-карточки в поле `description` payload WB | unit | REQ-3, SVC-1 § 9 | ozon_card_with_annotation |
| TC-6 | `MappingService.build_import_payload()` для Ozon→WB переносит поле `name` Ozon в поле `title` payload WB | unit | REQ-13, SVC-1 § 9 | ozon_card_with_annotation |
| TC-7 | Payload Ozon, сформированный `build_import_payload()`, не содержит явного поля `is_visible` или `status` — карточка создаётся в черновике по умолчанию | unit | REQ-14, SVC-1 § 9 | wb_card_with_description |
| TC-8 | Payload WB, сформированный `build_import_payload()` для Ozon→WB, не содержит явного поля статуса публикации | unit | REQ-14, SVC-1 § 9 | ozon_card_with_annotation |
| TC-9 | `MappingService.build_import_payload()` для WB→Ozon маппирует сопоставимые атрибуты из `characteristics` WB в `attributes` payload Ozon; несопоставленные атрибуты присутствуют в результирующем поле `missing_attributes` | unit | REQ-5, SVC-1 § 9 | wb_card_with_attributes |
| TC-10 | `MappingService.build_import_payload()` для Ozon→WB маппирует атрибуты Ozon в `characteristics` WB; несопоставленные атрибуты отражены в `missing_attributes` | unit | REQ-15, SVC-1 § 9 | ozon_card_with_attributes |
| TC-11 | `MappingService.find_brand_id()` возвращает `brand_id` при точном совпадении имени бренда (case-sensitive) из справочника Ozon API | unit | REQ-10, SVC-1 § 4 | ozon_brands_exact_match |
| TC-12 | `MappingService.find_brand_id()` возвращает `brand_id` при регистронезависимом совпадении, когда точное совпадение не найдено | unit | REQ-10, SVC-1 § 4 | ozon_brands_case_insensitive |
| TC-13 | `MappingService.find_brand_id()` возвращает `brand_id` при совпадении по подстроке, когда ни точное, ни регистронезависимое совпадение не найдено | unit | REQ-10, SVC-1 § 4 | ozon_brands_substring_match |
| TC-14 | `MappingService.find_brand_id()` возвращает `(None, False)` когда бренд не найден ни одним из способов поиска | unit | REQ-11, SVC-1 § 4 | ozon_brands_no_match |
| TC-15 | `MappingService.auto_match_category_llm()` возвращает `(CategoryNode, confidence)` где `confidence >= 0.7` при успешном LLM-ответе с валидным `category_id` из справочника | unit | REQ-7, SVC-1 § 4 | llm_response_high_confidence, ozon_categories |
| TC-16 | `MappingService.auto_match_category_llm()` возвращает `confidence < 0.7` когда LLM возвращает низкую уверенность — сигнал для `category_requires_manual=true` | unit | REQ-7, SVC-1 § 4 | llm_response_low_confidence, ozon_categories |
| TC-17 | `MappingService.auto_match_category_llm()` отбрасывает ответ LLM если `category_id` из JSON-ответа отсутствует в справочнике категорий и возвращает `(None, 0.0)` | unit | REQ-7, SVC-1 § 4 | llm_response_invalid_category_id, ozon_categories |
| TC-18 | `POST /api/v1/transfers/preview` с WB→Ozon: при пустом списке `mediaFiles` у товара ответ содержит предупреждение в `warnings`, `ready_to_import=false` | integration | REQ-4, SVC-1 § 2 | preview_request_wb_to_ozon, wb_card_no_images |
| TC-19 | `POST /api/v1/transfers/preview` с WB→Ozon: бренд не найден в Ozon API (FakeOzonClient возвращает пустой список брендов) — ответ содержит `brand_id_requires_manual=true`, `ready_to_import=false` | integration | REQ-11, REQ-17, SVC-1 § 2 | preview_request_wb_to_ozon, ozon_brands_no_match |
| TC-20 | `POST /api/v1/transfers/preview` с WB→Ozon: LLM возвращает низкую confidence — ответ содержит `category_requires_manual=true`, `ready_to_import=false` | integration | REQ-7, REQ-16, SVC-1 § 2 | preview_request_wb_to_ozon, llm_response_low_confidence |
| TC-21 | `POST /api/v1/transfers/preview` с WB→Ozon: в `product_overrides` передан `category_id` — LLM не вызывается (mock не получает вызов), `category_requires_manual=false`, `ready_to_import` зависит только от бренда | integration | REQ-9, SVC-1 § 4 | preview_request_with_category_override |
| TC-22 | `POST /api/v1/transfers/preview` с WB→Ozon: в `product_overrides` передан `brand_id` — `brand_id_requires_manual=false` независимо от результата поиска по справочнику | integration | REQ-17, SVC-1 § 2 | preview_request_with_brand_override |
| TC-23 | `POST /api/v1/transfers` блокирует запуск переноса и возвращает 400 если `category_requires_manual=true` и `category_id` override не передан | integration | REQ-16, SVC-1 § 2 | transfer_request_no_category_override |
| TC-24 | `POST /api/v1/transfers` блокирует запуск переноса и возвращает 400 если `brand_id_requires_manual=true` и `brand_id` override не передан | integration | REQ-17, SVC-1 § 2 | transfer_request_no_brand_override |
| TC-25 | `POST /api/v1/transfers` успешно создаёт job (status=pending) когда `ready_to_import=true` — FakeOzonClient принимает payload и возвращает task_id | integration | REQ-1, REQ-2, REQ-12, REQ-14, SVC-1 § 2 | transfer_request_ready, wb_card_with_description |
| TC-26 | `POST /api/v1/transfers` для Ozon→WB создаёт job и FakeWBClient получает payload с `description` (из `annotation`), `title`, `brand` как строкой | integration | REQ-3, REQ-13, REQ-14, SVC-1 § 2 | transfer_request_ozon_to_wb, ozon_card_with_annotation |
| TC-27 | `GET /api/v1/catalog/ozon/brands?q=Nike` возвращает список брендов из FakeOzonClient с полями `id` и `name` | integration | SVC-1 § 2, INT-2 | catalog_brands_request |
| TC-28 | `GET /api/v1/catalog/ozon/brands` с `marketplace=wb` возвращает 400 Bad Request | integration | SVC-1 § 2 | catalog_brands_request_invalid_marketplace |
| TC-29 | `POST /api/v1/transfers/preview` без Authorization заголовка возвращает 401 Unauthorized | integration | SVC-1 § 2 | preview_request_no_auth |
| TC-37 | `POST /api/v1/transfers/preview` вызывает `OzonClient.list_categories()` ровно один раз при каждом запросе preview (spy через pytest-mock), а не использует кэшированный хардкод | integration | REQ-6, SVC-1 § 4 | preview_request_wb_to_ozon, spy_categories_called |

### Тестовые данные

| Fixture | Описание | Поля |
|---------|----------|------|
| wb_card_with_description | WB-карточка с описанием, именем и артикулом | nmID: 12345678, vendorCode: "ART-001", title: "Футболка мужская", description: "Лёгкая хлопковая футболка", brand: "Nike", subjectID: 315, subjectName: "Футболки", mediaFiles: [{"big": "https://basket-01.wbbasket.ru/test/1.webp"}], characteristics: [] |
| wb_card_with_images | WB-карточка с несколькими фото | nmID: 12345679, vendorCode: "ART-002", title: "Футболка", description: "Описание", brand: "Adidas", mediaFiles: [{"big": "https://basket-01.wbbasket.ru/test/1.webp"}, {"big": "https://basket-01.wbbasket.ru/test/2.webp"}] |
| wb_card_no_images | WB-карточка без фотографий | nmID: 12345680, vendorCode: "ART-003", title: "Товар без фото", description: "Описание", brand: "BrandX", mediaFiles: [] |
| wb_card_with_attributes | WB-карточка с характеристиками | nmID: 12345681, vendorCode: "ART-004", title: "Футболка с атрибутами", description: "Описание", brand: "Nike", characteristics: [{"id": 1, "name": "Цвет", "value": ["Белый"]}, {"id": 2, "name": "Состав", "value": ["Хлопок 100%"]}] |
| ozon_card_with_annotation | Ozon-карточка с annotation, именем и артикулом | offer_id: "ART-001", name: "Футболка мужская Ozon", annotation: "Описание товара из Ozon", brand: "Nike", description_category_id: 17028727, images: ["https://cdn.ozon.ru/test/1.jpg"] |
| ozon_card_with_attributes | Ozon-карточка с атрибутами | offer_id: "ART-002", name: "Футболка с атрибутами", annotation: "Описание", attributes: [{"id": 85, "name": "Бренд", "values": [{"value": "Nike"}]}, {"id": 10096, "name": "Цвет", "values": [{"value": "Белый"}]}] |
| ozon_brands_exact_match | Список брендов Ozon с точным совпадением | result: [{"id": 1000, "name": "Nike"}, {"id": 1001, "name": "Adidas"}] |
| ozon_brands_case_insensitive | Список брендов Ozon с совпадением по регистру | result: [{"id": 1000, "name": "NIKE"}, {"id": 1001, "name": "adidas"}] |
| ozon_brands_substring_match | Список брендов Ozon с совпадением по подстроке | result: [{"id": 1000, "name": "Nike Sport Collection"}, {"id": 1001, "name": "Adidas Original"}] |
| ozon_brands_no_match | Список брендов Ozon без совпадений | result: [] |
| ozon_categories | Дерево категорий Ozon | result: [{"description_category_id": 17028726, "category_name": "Одежда", "children": [{"description_category_id": 17028727, "category_name": "Футболки", "type_id": 94765}]}] |
| llm_response_high_confidence | Mock-ответ LLM с высокой уверенностью | content: '{"category_id": 17028727, "confidence": 0.92}' |
| llm_response_low_confidence | Mock-ответ LLM с низкой уверенностью | content: '{"category_id": 17028727, "confidence": 0.45}' |
| llm_response_invalid_category_id | Mock-ответ LLM с несуществующим category_id | content: '{"category_id": 99999999, "confidence": 0.85}' |
| preview_request_wb_to_ozon | Запрос preview WB→Ozon без overrides | source_marketplace: "wb", target_marketplace: "ozon", product_ids: ["12345678"] |
| preview_request_with_category_override | Запрос preview с явным category_id | source_marketplace: "wb", target_marketplace: "ozon", product_ids: ["12345678"], product_overrides: {"12345678": {"category_id": 17028727}} |
| preview_request_with_brand_override | Запрос preview с явным brand_id | source_marketplace: "wb", target_marketplace: "ozon", product_ids: ["12345678"], product_overrides: {"12345678": {"brand_id": 1000}} |
| transfer_request_ready | Запрос переноса WB→Ozon готовый к запуску | source_marketplace: "wb", target_marketplace: "ozon", product_ids: ["12345678"], product_overrides: {"12345678": {"category_id": 17028727, "brand_id": 1000}} |
| transfer_request_no_category_override | Запрос переноса без обязательного category_id | source_marketplace: "wb", target_marketplace: "ozon", product_ids: ["12345678"], product_overrides: {} |
| transfer_request_no_brand_override | Запрос переноса без обязательного brand_id | source_marketplace: "wb", target_marketplace: "ozon", product_ids: ["12345678"], product_overrides: {"12345678": {"category_id": 17028727}} |
| transfer_request_ozon_to_wb | Запрос переноса Ozon→WB | source_marketplace: "ozon", target_marketplace: "wb", product_ids: ["ART-001"] |
| catalog_brands_request | Запрос поиска брендов Ozon | marketplace: "ozon", q: "Nike", limit: 20 |
| catalog_brands_request_invalid_marketplace | Запрос поиска брендов с неверным маркетплейсом | marketplace: "wb", q: "Nike" |
| preview_request_no_auth | Запрос preview без токена авторизации | source_marketplace: "wb", target_marketplace: "ozon", product_ids: ["12345678"], headers: {} |
| spy_categories_called | pytest-mock spy на OzonClient.list_categories() для проверки факта вызова | mocker.spy(ozon_client_instance, 'list_categories') |

## Системные тест-сценарии

| ID | Описание | Тип | Источник | Данные |
|----|----------|-----|----------|--------|
| TC-30 | Полный цикл preview WB→Ozon: LLM возвращает confidence ≥ 0.7 и бренд найден в Ozon API — ответ содержит `ready_to_import=true`, `category_requires_manual=false`, `brand_id_requires_manual=false` | e2e | STS-1, INT-2, INT-3 | preview_request_wb_to_ozon, wb_card_with_description, llm_response_high_confidence, ozon_brands_exact_match |
| TC-31 | Полный цикл перенос WB→Ozon: карточка создаётся на Ozon с полями `annotation` (из `description`), `name`, `offer_id`, `brand_id`, `images`, статус черновика (нет `is_visible`) | e2e | STS-2, INT-2 | transfer_request_ready, wb_card_with_description |
| TC-32 | Preview WB→Ozon: бренд не найден в Ozon API — `brand_id_requires_manual=true`, `ready_to_import=false`; после повторного preview с `brand_id` override — `ready_to_import=true` | integration | STS-3, INT-2 | preview_request_wb_to_ozon, ozon_brands_no_match, preview_request_with_brand_override |
| TC-33 | Preview WB→Ozon: LLM возвращает confidence < 0.7 — `category_requires_manual=true`, `ready_to_import=false`; после повторного preview с `category_id` override — `ready_to_import=true` | integration | STS-4, INT-3 | preview_request_wb_to_ozon, llm_response_low_confidence, preview_request_with_category_override |
| TC-34 | Полный цикл перенос Ozon→WB: карточка создаётся на WB с полями `description` (из `annotation`), `title`, `vendor_code` (из `offer_id`), `brand` как строкой, `images`, `subjectID` | e2e | STS-5, INT-1 | transfer_request_ozon_to_wb, ozon_card_with_annotation |
| TC-35 | Preview WB→Ozon: WB-карточка с пустым `mediaFiles` — ответ содержит предупреждение в `warnings` и `ready_to_import=false` | integration | STS-6, INT-1 | preview_request_wb_to_ozon, wb_card_no_images |
| TC-36 | Preview WB→Ozon: FakeWBClient выбрасывает исключение соединения — perenoska возвращает 502 Bad Gateway с кодом `WB_API_UNAVAILABLE`; FakeOzonClient выбрасывает исключение — 502 с кодом `OZON_API_UNAVAILABLE` | integration | STS-7, INT-1, INT-2 | preview_request_wb_to_ozon, wb_api_unavailable_error, ozon_api_unavailable_error |

### Тестовые данные

| Fixture | Описание | Поля |
|---------|----------|------|
| wb_api_unavailable_error | FakeWBClient настроен выбрасывать ConnectionError при любом вызове | side_effect: ConnectionError("WB API unavailable") |
| ozon_api_unavailable_error | FakeOzonClient настроен выбрасывать ConnectionError при любом вызове | side_effect: ConnectionError("Ozon API unavailable") |

## Матрица покрытия

| Источник | TC |
|----------|----|
| REQ-1 | TC-1, TC-25, TC-31 |
| REQ-2 | TC-2, TC-25 |
| REQ-3 | TC-5, TC-26, TC-34 |
| REQ-4 | TC-4, TC-18, TC-35 |
| REQ-5 | TC-9 |
| REQ-6 | TC-15, TC-30, TC-37 |
| REQ-7 | TC-15, TC-16, TC-17, TC-20, TC-33 |
| REQ-8 | TC-21 |
| REQ-9 | TC-21 |
| REQ-10 | TC-11, TC-12, TC-13 |
| REQ-11 | TC-14, TC-19, TC-32 |
| REQ-12 | TC-3, TC-25 |
| REQ-13 | TC-6, TC-26, TC-34 |
| REQ-14 | TC-7, TC-8, TC-25, TC-26, TC-31, TC-34 |
| REQ-15 | TC-10 |
| REQ-16 | TC-20, TC-23, TC-33 |
| REQ-17 | TC-19, TC-22, TC-24, TC-32 |
| REQ-18 | TC-23 |
| REQ-19 | TC-36 |
| STS-1 | TC-30 |
| STS-2 | TC-31 |
| STS-3 | TC-32 |
| STS-4 | TC-33 |
| STS-5 | TC-34 |
| STS-6 | TC-35 |
| STS-7 | TC-36 |

## Блоки тестирования

| BLOCK | TC | Сервисы | Dev BLOCK |
|-------|----|---------|-----------|
| BLOCK-1 | TC-1..TC-10 | perenoska (MappingService — маппинг полей и атрибутов) | BLOCK-1 |
| BLOCK-2 | TC-11..TC-17 | perenoska (MappingService — поиск брендов и LLM-маппинг категорий) | BLOCK-2 |
| BLOCK-3 | TC-18..TC-29, TC-37 | perenoska (TransferService, CatalogService — API endpoints) | BLOCK-3 |
| BLOCK-4 | TC-30..TC-36 | perenoska (e2e системные сценарии) | BLOCK-4 |

## Предложения

_Все предложения обработаны._

## Отвергнутые предложения

_Отвергнутых предложений нет._
