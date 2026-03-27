---
description: Корректный перенос карточек товаров между Wildberries и Ozon — маппинг полей (name, description→annotation, vendor_code, brand, status=draft), категорий (авто через LLM + ручной выбор), брендов (WB→Ozon через API, нечёткий поиск), фото и атрибутов. Приоритет WB→Ozon. Товары с вариантами вне scope. — проектирование распределения ответственностей между сервисами. — план тестов. — план разработки.
standard: specs/.instructions/analysis/plan-dev/standard-plan-dev.md
standard-version: v1.3
index: specs/analysis/README.md
parent: plan-test.md
status: RUNNING
milestone: v1.0.0
---

# 0002: Wb ozon product transfer — Plan Dev

## Резюме

Реализация корректного переноса карточек товаров WB↔Ozon затрагивает **1 сервис** — монолитное FastAPI-приложение `perenoska` (SVC-1). Всего **10 задач** (TASK-1..TASK-10), из них 3 инфраструктурных (INFRA), 6 функциональных и 1 тестовая (средняя сложность: 3.6/10). Кросс-сервисных зависимостей нет. Ключевые зависимости внутри сервиса: TASK-4, TASK-5, TASK-6, TASK-7 → TASK-9 (расширение TransferService); TASK-9 → TASK-10 (e2e системные тесты).

## Инфраструктура

### Задачи

#### TASK-1: Добавить зависимости openai и pytest-mock в pyproject.toml
- **Сложность:** 1/10
- **Приоритет:** high
- **Зависимости:** —
- **TC:** INFRA
- **Источник:** SVC-1 § 5
- **Issue:** [#1](https://github.com/lamantinX/perenoska/issues/1)
- **Type:** infra

Подзадачи:
- [x] 1.1. Добавить `openai>=1.0` в секцию `[project] dependencies` в `pyproject.toml`
- [x] 1.2. Добавить `pytest-mock>=3.14` в секцию `[project.optional-dependencies] dev` в `pyproject.toml`
- [x] 1.3. Проверить установку зависимостей: `pip install -e .[dev]` без ошибок

#### TASK-2: Расширить app/config.py — добавить поля LLM-конфигурации в Settings
- **Сложность:** 2/10
- **Приоритет:** high
- **Зависимости:** —
- **TC:** INFRA
- **Источник:** SVC-1 § 5
- **Issue:** [#2](https://github.com/lamantinX/perenoska/issues/2)
- **Type:** infra

Подзадачи:
- [x] 2.1. Добавить поле `openrouter_api_key: str` в `Settings` (env `OPENROUTER_API_KEY`, default `""`)
- [x] 2.2. Добавить поле `llm_model: str` в `Settings` (env `LLM_MODEL`, default `mistralai/mistral-7b-instruct:free`)
- [x] 2.3. Обновить `Settings.from_env()` — считывать `OPENROUTER_API_KEY` и `LLM_MODEL` через `os.getenv`

#### TASK-3: Обновить app/services/container.py — инициализировать AsyncOpenAI и передать в MappingService
- **Сложность:** 3/10
- **Приоритет:** high
- **Зависимости:** TASK-2
- **TC:** TC-15, TC-16, TC-17
- **Источник:** SVC-1 § 5
- **Issue:** [#3](https://github.com/lamantinX/perenoska/issues/3)
- **Type:** feature

Подзадачи:
- [ ] 3.1. Импортировать `AsyncOpenAI` из `openai` в `container.py`
- [ ] 3.2. В `ServiceContainer.__init__` создать `AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=settings.openrouter_api_key)` и сохранить как `self.llm_client`
- [ ] 3.3. Обновить создание `MappingService` — передать `llm_client=self.llm_client` и `llm_model=settings.llm_model`

## SVC-1: perenoska

### Задачи

#### TASK-4: Исправить build_import_payload() в MappingService — маппинг полей WB↔Ozon
- **Сложность:** 4/10
- **Приоритет:** high
- **Зависимости:** —
- **TC:** TC-1, TC-2, TC-3, TC-4, TC-5, TC-6, TC-7, TC-8, TC-9, TC-10
- **Источник:** SVC-1 § 4, SVC-1 § 9
- **Issue:** [#4](https://github.com/lamantinX/perenoska/issues/4)
- **Type:** feature

Подзадачи:
- [x] 4.1. Для направления WB→Ozon: заменить ключ `"description"` на `"annotation"` в формируемом payload Ozon; перенести `product["description"]` → `payload["annotation"]`
- [x] 4.2. Для направления WB→Ozon: перенести `product["vendorCode"]` → `payload["offer_id"]`, `product["title"]` → `payload["name"]`
- [x] 4.3. Для направления WB→Ozon: перенести список URL из `mediaFiles` (поле `"big"`) → `payload["images"]`; если `mediaFiles` пуст — добавить предупреждение в `warnings` и установить `ready_to_import=false`
- [x] 4.4. Для направления WB→Ozon: убедиться что payload не содержит явного поля `is_visible` или `status` (карточка создаётся черновиком по умолчанию)
- [x] 4.5. Для направления Ozon→WB: перенести `product["annotation"]` → `payload["description"]`, `product["name"]` → `payload["title"]`; убедиться что payload не содержит поля статуса публикации
- [x] 4.6. Маппинг атрибутов WB→Ozon: перенести совпадающие по `FIELD_SYNONYMS` атрибуты из `characteristics` в `attributes`; несопоставленные атрибуты добавить в `missing_attributes`
- [x] 4.7. Маппинг атрибутов Ozon→WB: перенести совпадающие атрибуты из `attributes` Ozon в `characteristics` WB; несопоставленные — в `missing_attributes`

#### TASK-5: Добавить find_brand_id() в MappingService и list_brands() в OzonClient
- **Сложность:** 4/10
- **Приоритет:** high
- **Зависимости:** —
- **TC:** TC-11, TC-12, TC-13, TC-14
- **Источник:** SVC-1 § 4, SVC-1 § 5
- **Issue:** [#5](https://github.com/lamantinX/perenoska/issues/5)
- **Type:** feature

Подзадачи:
- [ ] 5.1. В `app/clients/ozon.py` добавить метод `list_brands(credentials, query: str, limit: int = 100) -> list[dict]` — POST `/v1/brand/list` с телом `{"filters": {"brand_name_search": query}, "last_id": 0, "limit": limit}`
- [ ] 5.2. В `app/services/mapping.py` добавить метод `find_brand_id(credentials, brand_name: str, ozon_client) -> tuple[int | None, bool]`
- [ ] 5.3. В `find_brand_id`: реализовать точное совпадение (case-sensitive) по полю `name` из ответа `list_brands`
- [ ] 5.4. В `find_brand_id`: если точное не найдено — регистронезависимое совпадение (`brand_name.lower() == entry["name"].lower()`)
- [ ] 5.5. В `find_brand_id`: если регистронезависимое не найдено — поиск по подстроке (`brand_name.lower() in entry["name"].lower()` или наоборот)
- [ ] 5.6. В `find_brand_id`: если ни один вариант не дал результат — вернуть `(None, False)`

#### TASK-6: Добавить auto_match_category_llm() в MappingService
- **Сложность:** 5/10
- **Приоритет:** high
- **Зависимости:** TASK-3
- **TC:** TC-15, TC-16, TC-17
- **Источник:** SVC-1 § 4, SVC-1 § 9
- **Issue:** [#6](https://github.com/lamantinX/perenoska/issues/6)
- **Type:** feature

Подзадачи:
- [ ] 6.1. Удалить (или переименовать) метод `auto_match_category()` с реализацией на `SequenceMatcher`; добавить метод `auto_match_category_llm(source_category_name: str, target_categories: list[dict]) -> tuple[dict | None, float]`
- [ ] 6.2. Обновить `MappingService.__init__` — принять параметры `llm_client: AsyncOpenAI` и `llm_model: str`; сохранить как `self.llm_client` и `self.llm_model`
- [ ] 6.3. В `auto_match_category_llm`: сформировать промпт с именем категории источника и списком категорий таргета `[{id, name}]` (не более 50 leaf-категорий); запросить JSON-ответ `{"category_id": N, "confidence": float}`
- [ ] 6.4. Вызвать `self.llm_client.chat.completions.create(model=self.llm_model, ...)` через `await`; обработать ответ: распарсить JSON из `content`
- [ ] 6.5. Валидировать `category_id` из ответа: если отсутствует в справочнике категорий — вернуть `(None, 0.0)`; если `confidence < 0.7` — вернуть `(CategoryNode, confidence)` (сигнал для `category_requires_manual=true`); если `confidence >= 0.7` — вернуть `(CategoryNode, confidence)`

#### TASK-7: Расширить app/schemas.py — TransferPreviewItem и product_overrides
- **Сложность:** 3/10
- **Приоритет:** high
- **Зависимости:** —
- **TC:** TC-19, TC-20, TC-21, TC-22
- **Источник:** SVC-1 § 2, SVC-1 § 5
- **Issue:** [#7](https://github.com/lamantinX/perenoska/issues/7)
- **Type:** task

Подзадачи:
- [ ] 7.1. В `TransferPreviewItem` добавить поля: `brand_id_suggestion: int | None = None`, `brand_id_requires_manual: bool = False`, `category_confidence: float | None = None`, `category_requires_manual: bool = False`
- [ ] 7.2. Добавить Pydantic-модель `ProductOverride` с полями: `category_id: int | None = None`, `brand_id: int | None = None`, `price: str | None = None`, `attributes: list | None = None`
- [ ] 7.3. В `TransferPreviewRequest` изменить тип поля `product_overrides` на `dict[str, ProductOverride] | None = None`
- [ ] 7.4. В `TransferRequest` аналогично расширить `product_overrides` до `dict[str, ProductOverride] | None = None`

#### TASK-8: Добавить GET /api/v1/catalog/{marketplace}/brands
- **Сложность:** 3/10
- **Приоритет:** medium
- **Зависимости:** TASK-5, TASK-7
- **TC:** TC-27, TC-28
- **Источник:** SVC-1 § 2, SVC-1 § 5
- **Issue:** [#8](https://github.com/lamantinX/perenoska/issues/8)
- **Type:** feature

Подзадачи:
- [ ] 8.1. В `app/api/routes/catalog.py` добавить endpoint `GET /api/v1/catalog/{marketplace}/brands` с query-параметрами `q: str` (обязательно) и `limit: int = Query(default=20, le=100)`
- [ ] 8.2. Проверить что `marketplace == "ozon"` — если нет, вернуть `HTTPException(status_code=400, detail="Only ozon marketplace supports brand search")`
- [ ] 8.3. Вызвать `ozon_client.list_brands(credentials, query=q, limit=limit)` и вернуть `{"items": [...], "total": len(items)}` со структурой `[{"id": ..., "name": ...}]`
- [ ] 8.4. Обработать ошибки подключения к Ozon API — вернуть 502 Bad Gateway с кодом `OZON_API_UNAVAILABLE`

#### TASK-9: Расширить TransferService.preview() и launch() — product_overrides, блокировка, LLM и бренды
- **Сложность:** 6/10
- **Приоритет:** high
- **Зависимости:** TASK-4, TASK-5, TASK-6, TASK-7
- **TC:** TC-18, TC-19, TC-20, TC-21, TC-22, TC-23, TC-24, TC-25, TC-26, TC-29, TC-37
- **Источник:** SVC-1 § 2, SVC-1 § 4, SVC-1 § 9
- **Issue:** [#10](https://github.com/lamantinX/perenoska/issues/10)
- **Type:** feature

Подзадачи:
- [ ] 9.1. В `TransferService.preview()`: если в `product_overrides[product_id]` задан `category_id` — использовать его напрямую, пропустить вызов `auto_match_category_llm()`; иначе вызвать `mapping_service.auto_match_category_llm()` и заполнить `category_confidence` и `category_requires_manual`
- [ ] 9.2. В `TransferService.preview()`: вызвать `mapping_service.find_brand_id()` для определения `brand_id_suggestion`; если в `product_overrides[product_id]` задан `brand_id` — использовать его, `brand_id_requires_manual=false`; если не найден в справочнике — `brand_id_requires_manual=true`
- [ ] 9.3. В `TransferService.preview()`: вызвать `list_categories(ozon)` для получения актуального дерева категорий при каждом запросе (не кэшировать), передать в `auto_match_category_llm()`
- [ ] 9.4. В `TransferService.preview()` для WB→Ozon: проверить `mediaFiles` — если пуст, добавить предупреждение в `warnings` и установить `ready_to_import=false`
- [ ] 9.5. В `TransferService.preview()`: вычислить `ready_to_import = not (category_requires_manual or brand_id_requires_manual)` с учётом переданных overrides
- [ ] 9.6. В `TransferService.launch()`: проверить `category_requires_manual` и `brand_id_requires_manual` — если хотя бы одно `true` и соответствующий override не передан, вернуть `HTTPException(status_code=400)`
- [ ] 9.7. Обработать ошибки подключения к WB API и Ozon API в `preview()` и `launch()` — вернуть 502 Bad Gateway с кодом `WB_API_UNAVAILABLE` или `OZON_API_UNAVAILABLE`

#### TASK-10: Написать e2e системные тесты (TC-30..TC-36)
- **Сложность:** 5/10
- **Приоритет:** high
- **Зависимости:** TASK-9
- **TC:** TC-30, TC-31, TC-32, TC-33, TC-34, TC-35, TC-36
- **Источник:** SVC-1 § 2, SVC-1 § 4, SVC-1 § 9
- **Issue:** [#11](https://github.com/lamantinX/perenoska/issues/11)
- **Type:** test

Подзадачи:
- [ ] 10.1. Создать файл `tests/test_system_e2e.py` с общей фикстурой `client` (FakeWBClient + FakeOzonClient + AsyncMock LLM) и базовыми хелперами авторизации
- [ ] 10.2. TC-30: тест полного цикла preview WB→Ozon — LLM confidence ≥ 0.7, бренд найден точным совпадением → `ready_to_import=true`, `category_requires_manual=false`, `brand_id_requires_manual=false`
- [ ] 10.3. TC-31: тест полного цикла переноса WB→Ozon — карточка создаётся на Ozon с полями `annotation`, `name`, `offer_id`, `brand_id`, `images`; payload не содержит `is_visible` или `status`
- [ ] 10.4. TC-32: двухшаговый тест — первый preview без бренда (`brand_id_requires_manual=true`, `ready_to_import=false`), затем повторный preview с `brand_id` override → `ready_to_import=true`
- [ ] 10.5. TC-33: двухшаговый тест — первый preview с LLM confidence < 0.7 (`category_requires_manual=true`, `ready_to_import=false`), затем повторный preview с `category_id` override → `ready_to_import=true`
- [ ] 10.6. TC-34: тест полного цикла переноса Ozon→WB — карточка создаётся на WB с полями `description` (из `annotation`), `title`, `vendor_code` (из `offer_id`), `brand` как строкой, `images`, `subjectID`; payload не содержит поле статуса публикации
- [ ] 10.7. TC-35: тест preview WB→Ozon с `mediaFiles=[]` — ответ содержит предупреждение в `warnings`, `ready_to_import=false`
- [ ] 10.8. TC-36: тест обработки сетевых ошибок — FakeWBClient выбрасывает ConnectionError → 502 с кодом `WB_API_UNAVAILABLE`; FakeOzonClient выбрасывает ConnectionError → 502 с кодом `OZON_API_UNAVAILABLE`

## Кросс-сервисные зависимости

*Кросс-сервисных зависимостей нет.*

## Маппинг GitHub Issues

| Элемент | Маппинг |
|---------|---------|
| TASK-N | → Issue title |
| Подзадачи | → Чек-лист в Issue body |
| Приоритет | → Label `priority/{value}` |
| Зависимости | → "Blocked by #N" в Issue body |
| TC | → Ссылка на TC-N в Issue body |
| Milestone | → Milestone из frontmatter Discussion |

## Блоки выполнения

| BLOCK | Задачи | Сервисы | Зависимости | Wave |
|-------|--------|---------|-------------|------|
| BLOCK-0 | TASK-1, TASK-2 | perenoska (INFRA) | — | 0 |
| BLOCK-1 | TASK-4 | perenoska (MappingService — маппинг полей) | BLOCK-0 | 1 |
| BLOCK-2 | TASK-3, TASK-5, TASK-6 | perenoska (MappingService — DI + бренды и LLM) | BLOCK-0 | 1 |
| BLOCK-3 | TASK-7, TASK-8, TASK-9 | perenoska (schemas, catalog endpoint, интеграционные тесты) | BLOCK-1, BLOCK-2 | 2 |
| BLOCK-4 | TASK-10 | perenoska (e2e системные тесты) | BLOCK-3 | 3 |

## Предложения

_Все предложения обработаны._

## Отвергнутые предложения

| PROP | Причина отклонения |
|------|--------------------|
| PROP-1 | TASK-1 (pyproject.toml) и TASK-2 (config.py) — разные зоны ответственности; объединение снижает атомарность коммитов. 30% INFRA обусловлено минимально необходимой инфраструктурой для монолита с новым LLM-клиентом. |
