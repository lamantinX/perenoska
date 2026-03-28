---
description: Тестирование Perenoska — типы тестов, мокирование, системные сценарии, покрытие.
standard: specs/.instructions/docs/testing/standard-testing.md
standard-version: v1.1
---

# Тестирование

## Типы тестов

В проекте применяются 3 типа тестов. Unit — основа: быстрые, изолированные, покрывают бизнес-логику `MappingService`. Integration — проверяют HTTP-эндпоинты через `TestClient` с изолированной SQLite. E2E — полные сценарии через HTTP API с FakeWBClient/FakeOzonClient и AsyncMock LLM.

**Неприменимые типы:**
- **load** — нет SLA по RPS или конкурентности; latency preview < 10s и transfer < 30s покрываются integration-тестами.
- **smoke** — нет CI/CD деплоя и health-endpoint в scope v1.0.0; актуальны после деплоя в production-среде.

| Тип | Что проверяет | Scope | Внешние зависимости | Когда запускается |
|-----|--------------|-------|--------------------|--------------------|
| Unit | Бизнес-логика: маппинг полей, маппинг атрибутов, поиск брендов, LLM-маппинг категорий | Один модуль/функция (`MappingService`) | Все мокаются (`AsyncMock`, `MagicMock`) | При каждом коммите (pre-commit), в CI |
| Integration | HTTP-эндпоинты: preview, transfers, catalog/brands; аутентификация | `TestClient` + SQLite (tmp_path) | WB/Ozon API мокируются через `register_override`; LLM через `AsyncMock` | В CI на каждый PR |
| E2E | Полные сценарии: preview+launch WB→Ozon, Ozon→WB, двухшаговые override, ошибки API | Полная система через HTTP | FakeWBClient, FakeOzonClient, AsyncMock LLM | В CI перед merge в main |

## Структура файлов

Unit и integration тесты живут в `/tests/` рядом с app-кодом. E2E тесты также в `/tests/`. Именование: файл `test_{module}.py`, функция `test_{тип_tc_действие}`.

```
/
├── src/                              # (нет — монолит, код в /app/)
├── app/                              # FastAPI приложение (бизнес-логика)
│   ├── services/mapping.py           # MappingService — тестируется в BLOCK-1, BLOCK-2
│   ├── services/transfer.py          # TransferService — тестируется в BLOCK-3, BLOCK-4
│   └── api/routes/catalog.py         # CatalogService — тестируется в BLOCK-3
└── tests/                            # Все тесты
    ├── test_mapping_payload.py        # Unit TC-1..TC-10: MappingService.build_import_payload()
    ├── test_mapping_llm.py            # Unit TC-11..TC-17: find_brand_id, auto_match_category_llm
    ├── test_transfer_preview.py       # Integration TC-18..TC-24, TC-29, TC-37: preview/transfer endpoints
    ├── test_transfer_service_integration.py  # Integration TC-25..TC-26: TransferService launch
    ├── test_catalog_brands.py         # Integration TC-27..TC-28: GET /catalog/{marketplace}/brands
    ├── test_system_e2e.py             # E2E TC-30..TC-36: системные сценарии
    └── test_auth_and_connections.py   # Integration: auth + connections
```

## Стратегия мокирования

Принцип: WB API и Ozon API всегда мокируются через `container.client_factory.register_override(marketplace, FakeClient())`. LLM (OpenRouter/AsyncOpenAI) мокируется через `unittest.mock.AsyncMock`. SQLite разворачивается через `create_app(settings)` с `tmp_path` pytest-фикстурой — полная изоляция БД между тестами.

| Уровень | БД | Message Broker | Другие сервисы | Shared-код | Внешние API |
|---------|-----|---------------|---------------|------------|-------------|
| Unit | Нет (не требуется) | Нет (не используется) | Нет (монолит) | Реальный | Мок (AsyncMock/MagicMock) |
| Integration | SQLite (tmp_path) | Нет (не используется) | Нет (монолит) | Реальный | FakeClient через register_override; AsyncMock LLM |
| E2E | SQLite (tmp_path) | Нет (не используется) | Нет (монолит) | Реальный | FakeClient через register_override; AsyncMock LLM |

**Паттерн изоляции:**
```python
settings = Settings(..., database_path=tmp_path / "test.db")
app = create_app(settings)
app.state.container.client_factory.register_override(Marketplace.WB, FakeWBClient())
app.state.container.client_factory.register_override(Marketplace.OZON, FakeOzonClient())
mocker.patch.object(
    app.state.container.mapping_service,
    "auto_match_category_llm",
    new=AsyncMock(return_value=({"id": 17028727, "name": "Футболки"}, 0.92)),
)
client = TestClient(app)
```

## Системные тест-сценарии

Системные сценарии описаны в [overview.md](overview.md#сквозные-потоки) — это SSOT сквозных потоков. Реализованы в `tests/test_system_e2e.py`.

| TC | Описание | Тип | Источник |
|----|----------|-----|----------|
| TC-30 | Полный цикл preview WB→Ozon: LLM confidence ≥ 0.7 и бренд найден — `ready_to_import=true`, `category_requires_manual=false`, `brand_id_requires_manual=false` | e2e | STS-1, INT-2, INT-3 |
| TC-31 | Полный цикл перенос WB→Ozon: payload Ozon содержит `annotation` (из `description`), `name`, `offer_id`, `brand_id`, `images`; нет `is_visible`/`status` | e2e | STS-2, INT-2 |
| TC-32 | Двухшаговый сценарий: бренд не найден → `brand_id_requires_manual=true`; повторный preview с `brand_id` override → `ready_to_import=true` | integration | STS-3, INT-2 |
| TC-33 | Двухшаговый сценарий: LLM confidence < 0.7 → `category_requires_manual=true`; повторный preview с `category_id` override → `ready_to_import=true` | integration | STS-4, INT-3 |
| TC-34 | Полный цикл перенос Ozon→WB: payload WB содержит `description` (из `annotation`), `title`, `vendorCode`, `brand` (строка), `subjectID` | e2e | STS-5, INT-1 |
| TC-35 | Preview WB→Ozon: пустой `mediaFiles` → предупреждение в `warnings`, `ready_to_import=false` | integration | STS-6, INT-1 |
| TC-36 | API unavailable: FakeWBClient выбрасывает `MarketplaceAPIError` → 502 с кодом `WB_API_UNAVAILABLE`; FakeOzonClient — 502 с `OZON_API_UNAVAILABLE` | integration | STS-7, INT-1, INT-2 |

**Arrange/Act/Assert паттерн для e2e:**
1. **Arrange:** `register_and_login(client)` → получить Bearer-токен; `setup_connections(client, headers)` → сохранить WB/Ozon credentials
2. **Act:** выполнить HTTP-запрос к `/api/v1/transfers/preview` или `/api/v1/transfers`
3. **Assert:** проверить HTTP-статус, поля ответа, опционально — payload переданный в FakeClient через `_last_items`

## Межсервисные тесты

Perenoska — монолит. Межсервисные сценарии описывают взаимодействие с внешними API (WB, Ozon, OpenRouter), которые всегда мокируются в тестах через FakeClient.

| Интеграция | Тест-сценарии | Файл |
|-----------|---------------|------|
| perenoska → WB API | TC-26, TC-34 (create_products WB), TC-35 (mediaFiles), TC-36a (WB unavailable) | test_system_e2e.py |
| perenoska → Ozon API | TC-25, TC-31 (create_products Ozon), TC-27 (list_brands), TC-32 (brand not found), TC-36b (Ozon unavailable) | test_system_e2e.py, test_catalog_brands.py |
| perenoska → OpenRouter | TC-15..TC-17 (auto_match_category_llm), TC-20, TC-30, TC-33, TC-37 (LLM вызов/пропуск) | test_mapping_llm.py, test_transfer_preview.py, test_system_e2e.py |

## Тестовые данные

Подход: pytest fixtures в файлах тестов (нет отдельного `conftest.py` с fixtures). Каждый тест создаёт изолированный SQLite через `tmp_path`. FakeClient-классы определены непосредственно в тест-файлах.

**Принципы:**
- **Минимальность:** каждый FakeClient и fixture возвращает минимальный валидный объект; тест переопределяет только нужные поля
- **Изоляция:** каждый тест очищает данные через изолированную SQLite (tmp_path) — нет переиспользования БД между тестами; нет глобального rollback/truncate, каждый тест получает чистую БД
- Каждый тест независим — порядок запуска не влияет на результат
- API-ключи маркетплейсов — тестовые строки (`"wb-secret-token"`, `"apikey"`), не из .env

**Ключевые fixtures (по Plan Tests):**

| Fixture | Описание | Файл |
|---------|----------|------|
| wb_card_with_description | WB-карточка: nmID=12345678, vendorCode="ART-001", description="Лёгкая хлопковая футболка", brand="Nike" | test_mapping_payload.py |
| wb_card_with_images | WB-карточка с двумя фото | test_mapping_payload.py |
| wb_card_with_attributes | WB-карточка с Цвет/Состав characteristics | test_mapping_payload.py |
| ozon_card_with_annotation | Ozon-карточка: offer_id="ART-001", annotation="Описание товара из Ozon" | test_mapping_payload.py |
| FakeWBClient | Возвращает ProductDetails с brand="Nike", images=[...] | test_system_e2e.py |
| FakeOzonClient | Возвращает list_brands=[Nike/Adidas], list_categories=[17028727] | test_system_e2e.py |
| FakeOzonNoBrandClient | list_brands возвращает [] | test_system_e2e.py |
| FakeWBConnectionErrorClient | get_product_details выбрасывает MarketplaceAPIError | test_system_e2e.py |
| FakeOzonConnectionErrorClient | list_categories выбрасывает MarketplaceAPIError | test_system_e2e.py |

## Покрытие

**Матрица покрытия по требованиям (Plan Tests):**

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

**Блоки тестирования:**

| BLOCK | TC | Сервисы | Файл |
|-------|----|---------|------|
| BLOCK-1 | TC-1..TC-10 | perenoska (MappingService — маппинг полей и атрибутов) | test_mapping_payload.py |
| BLOCK-2 | TC-11..TC-17 | perenoska (MappingService — поиск брендов и LLM-маппинг категорий) | test_mapping_llm.py |
| BLOCK-3 | TC-18..TC-29, TC-37 | perenoska (TransferService, CatalogService — API endpoints) | test_transfer_preview.py, test_catalog_brands.py, test_transfer_service_integration.py |
| BLOCK-4 | TC-30..TC-36 | perenoska (e2e системные сценарии) | test_system_e2e.py |

## Команды запуска

Make-таргеты для тестирования определены в [Makefile](/Makefile) (SSOT). Полный список: `make help`.

```bash
make test   # Запустить все тесты: pytest tests/ -v
```

**Прямой вызов pytest** (для запуска конкретных тестов по фильтру):

```bash
pytest tests/test_mapping_payload.py -v                              # Unit: маппинг полей
pytest tests/test_mapping_llm.py -v                                  # Unit: LLM + поиск брендов
pytest tests/test_system_e2e.py -v                                   # E2E системные сценарии
pytest tests/ -k "tc30"                                              # Конкретный TC по имени
pytest tests/test_auth_and_connections.py::test_register_login_and_save_connection  # Один тест
```
