---
description: perenoska — монолитное FastAPI-приложение для переноса карточек товаров между Wildberries и Ozon с корректным маппингом полей, категорий и брендов.
standard: specs/.instructions/docs/service/standard-service.md
criticality: critical-high
---

# perenoska

## Назначение

Монолитное FastAPI-приложение, реализующее перенос карточек товаров между Wildberries и Ozon через API обоих маркетплейсов. Сервис обеспечивает корректный маппинг полей (`description↔annotation`, `name`, `vendor_code`, `brand`/`brand_id`, `images`, атрибуты), LLM-подбор категорий через OpenRouter и многошаговый поиск брендов через Ozon API `/v1/brand/list`. Основной потребитель — frontend через REST API; сервис является единственной точкой оркестрации переноса и не имеет аналогов в системе.

**Обоснование критичности:** Уровень `critical-high` — сервис реализует ключевую бизнес-функцию продукта: перенос карточек товаров между маркетплейсами. При недоступности сервиса пользователи полностью теряют возможность выполнять переносы, что означает revenue = 0 для основного сценария использования. Обходных путей нет — перенос карточек выполняется только через этот сервис.

## API контракты

Сервис предоставляет REST API из 4 endpoint-ов, сгруппированных в два домена: `transfers` (preview, запуск переноса, синхронизация статуса) и `catalog` (поиск брендов). Все endpoint-ы требуют Bearer token и следуют конвенциям из [conventions.md](../.system/conventions.md).

### POST /api/v1/transfers/preview

Возвращает предварительный просмотр переноса: маппинг категорий (через LLM), подбор brand_id (через Ozon API) и поля, требующие ручного ввода.

- **Auth:** Bearer token (обязательно)
- **Паттерн:** sync | **Протокол:** REST/JSON

**Request:**
```json
{
  "source_marketplace": "wb",
  "target_marketplace": "ozon",
  "product_ids": ["12345678"],
  "product_overrides": {
    "12345678": {
      "category_id": 17028726,
      "brand_id": 1000,
      "price": "1500"
    }
  }
}
```

**Response 200:**
```json
{
  "source_marketplace": "wb",
  "target_marketplace": "ozon",
  "ready_to_import": false,
  "items": [{
    "product_id": "12345678",
    "title": "Футболка мужская",
    "source_category_id": 50,
    "target_category_id": 17028726,
    "target_category_name": "Футболки",
    "category_confidence": 0.85,
    "category_requires_manual": false,
    "brand_id_suggestion": 1000,
    "brand_id_requires_manual": false,
    "payload": {},
    "mapped_attributes": {},
    "missing_required_attributes": [],
    "missing_critical_fields": [],
    "warnings": []
  }]
}
```

**Errors:** 401 Unauthorized, 400 Bad Request (нет credentials), 502 Bad Gateway (недоступен WB/Ozon API)

---

### POST /api/v1/transfers

Запускает перенос товаров. Блокируется если `missing_required_attributes` непустой и `attributes` override не передан, или если `brand_id_requires_manual=true`/`category_requires_manual=true` без override.

- **Auth:** Bearer token (обязательно)
- **Паттерн:** sync | **Протокол:** REST/JSON

**Request:**
```json
{
  "source_marketplace": "wb",
  "target_marketplace": "ozon",
  "product_ids": ["12345678"],
  "product_overrides": {
    "12345678": {
      "category_id": 17028726,
      "brand_id": 1000,
      "attributes": [
        {"id": 85, "complex_id": 0, "values": [{"value": "Белый", "dictionary_value_id": 0}]}
      ]
    }
  }
}
```

**Response 200:**
```json
{"job_id": "job-abc123", "status": "pending", "product_count": 1}
```

**Errors:** 401 Unauthorized, 400 Bad Request (not ready_to_import или missing_required_attributes непустой), 502 Bad Gateway

---

### POST /api/v1/transfers/{job_id}/sync

Синхронизирует статус задачи переноса с целевым маркетплейсом.

- **Auth:** Bearer token (обязательно)
- **Паттерн:** sync | **Протокол:** REST/JSON

**Response 200:**
```json
{"job_id": "job-abc123", "status": "completed|processing|failed", "product_count": 1}
```

**Errors:** 401 Unauthorized, 404 Not Found

---

### GET /api/v1/catalog/{marketplace}/brands

Поиск брендов в справочнике Ozon для ручного выбора пользователем.

- **Auth:** Bearer token (обязательно)
- **Паттерн:** sync | **Протокол:** REST/JSON

| Параметр | Тип | Обязательный | Описание |
|----------|-----|-------------|----------|
| marketplace | string | да (path) | Маркетплейс (только `ozon`) |
| q | string | да | Поисковый запрос |
| limit | int | нет (default 20, max 100) | Лимит результатов |

**Response 200:**
```json
{
  "items": [
    {"id": 1000, "name": "Nike"},
    {"id": 1001, "name": "Nike Sport"}
  ],
  "total": 2
}
```

**Errors:** 401 Unauthorized, 400 Bad Request (marketplace != ozon), 502 Bad Gateway

## Data Model

Сервис использует SQLite через `app/db.py`. Изменений в Data Model данный Design не требует — существующие таблицы остаются без изменений.

### users (SQLite)

| Колонка | Тип | Constraints | Описание |
|---------|-----|------------|----------|
| id | INTEGER | PK, NOT NULL | Идентификатор пользователя |
| email | TEXT | NOT NULL, UNIQUE | Email пользователя |
| password_hash | TEXT | NOT NULL | PBKDF2/SHA-256 хэш пароля |
| created_at | TEXT | NOT NULL | Дата создания (ISO8601) |

### sessions (SQLite)

| Колонка | Тип | Constraints | Описание |
|---------|-----|------------|----------|
| id | INTEGER | PK, NOT NULL | Идентификатор сессии |
| user_id | INTEGER | FK(users.id), NOT NULL | Ссылка на пользователя |
| token | TEXT | NOT NULL, UNIQUE | Bearer-токен (`secrets.token_urlsafe(32)`) |
| expires_at | TEXT | NOT NULL | Время истечения сессии (ISO8601) |

### marketplace_connections (SQLite)

| Колонка | Тип | Constraints | Описание |
|---------|-----|------------|----------|
| id | INTEGER | PK, NOT NULL | Идентификатор подключения |
| user_id | INTEGER | FK(users.id), NOT NULL | Ссылка на пользователя |
| marketplace | TEXT | NOT NULL, CHECK(wb, ozon) | Маркетплейс |
| credentials_encrypted | TEXT | NOT NULL | Fernet-зашифрованные API-ключи |

### transfer_jobs (SQLite)

| Колонка | Тип | Constraints | Описание |
|---------|-----|------------|----------|
| id | TEXT | PK, NOT NULL | UUID задачи |
| user_id | INTEGER | FK(users.id), NOT NULL | Ссылка на пользователя |
| status | TEXT | NOT NULL, CHECK(pending, submitted, processing, completed, failed) | Статус задачи |
| payload_json | TEXT | NOT NULL | JSON-строка с параметрами переноса |
| result_json | TEXT | | JSON-строка с результатом |
| created_at | TEXT | NOT NULL | Дата создания (ISO8601) |
| updated_at | TEXT | NOT NULL | Дата обновления (ISO8601) |

## Потоки

Запросы принимаются в `app/api/routes/`, передаются в сервисный слой (`app/services/`), который оркестрирует вызовы клиентов (`app/clients/`). Для добавления нового endpoint-а: создать схемы в `app/schemas.py`, добавить роут в `app/api/routes/`, реализовать логику в нужном сервисе, зарегистрировать зависимость в `app/api/deps.py`.

### Preview WB→Ozon

```
1. Client → POST /api/v1/transfers/preview (source=wb, target=ozon, product_ids, product_overrides)
2. app/api/routes/transfers.py → TransferService.preview()
3. TransferService → CatalogService.get_product_details(wb) → ProductDetails (поле description = описание WB)
4. TransferService → CatalogService.list_categories(ozon) → список CategoryNode
5. Если product_overrides содержит category_id → использовать его, пропустить LLM
   Иначе → MappingService.auto_match_category_llm() → openai SDK → OpenRouter API
6. LLM возвращает (category_id, confidence). Если confidence < 0.7 → category_requires_manual=true
7. MappingService.find_brand_id() → OzonClient.list_brands() → POST /v1/brand/list
   exact → case-insensitive → substring. Если не найден → brand_id_requires_manual=true
8. MappingService.build_import_payload() → description→annotation, name→name, vendor_code→offer_id, images→images
9. TransferService → Client: TransferPreviewResponse (ready_to_import, поля для ручного ввода)
```

### Preview Ozon→WB

```
1. Client → POST /api/v1/transfers/preview (source=ozon, target=wb, product_ids, product_overrides)
2. app/api/routes/transfers.py → TransferService.preview()
3. TransferService → CatalogService.get_product_details(ozon) → ProductDetails (поле annotation = описание Ozon)
4. TransferService → CatalogService.list_categories(wb) → список CategoryNode
5. MappingService.auto_match_category_llm() → LLM маппинг в обратном направлении: Ozon категория → WB справочник
6. Бренд передаётся строкой (без верификации по WB-справочнику)
7. MappingService.build_import_payload() → annotation→description, name→name
8. TransferService → Client: TransferPreviewResponse
```

### Запуск переноса WB→Ozon

```
1. Client → POST /api/v1/transfers (product_overrides с category_id, brand_id, attributes)
2. app/api/routes/transfers.py → TransferService.launch()
3. TransferService: проверяет ready_to_import. Если missing_required_attributes непустой и нет override → 400
4. TransferService → db: создаёт transfer_job (status=PENDING)
5. TransferService → OzonClient.create_products() → POST /v3/product/import (annotation, brand_id, images)
6. TransferService → db: обновляет status → SUBMITTED или FAILED
7. TransferService → Client: TransferJobResponse (job_id, status=pending)
```

### Внутренний поток поиска brand_id

```
1. MappingService.find_brand_id(credentials, brand_name, ozon_client)
2. OzonClient.list_brands(credentials, query=brand_name) → POST /v1/brand/list
3. Поиск exact match по полю name (case-sensitive)
4. Если не найден → case-insensitive match
5. Если не найден → поиск по подстроке (brand_name in result.name или vice versa)
6. Возвращает (brand_id: int | None, found: bool)
```

### Внутренний поток LLM маппинга категорий

```
1. MappingService.auto_match_category_llm(source_category, target_categories)
2. Формирует промпт: категория источника + список категорий таргета (id + name)
3. openai.AsyncOpenAI(base_url=openrouter_url).chat.completions.create() → POST /chat/completions
4. Парсит JSON-ответ: {category_id: int, confidence: float}
5. Валидирует что category_id существует в полученном справочнике
6. Возвращает (CategoryNode | None, confidence: float)
   При ошибке OpenRouter → возвращает (None, 0.0) → category_requires_manual=true
```

## Code Map

### Tech Stack

| Технология | Версия | Назначение | Стандарт |
|-----------|--------|-----------|---------|
| Python | 3.11 | Язык сервиса | [standard-python.md](../.technologies/standard-python.md) |
| FastAPI | 0.115 | API-фреймворк | [standard-fastapi.md](../.technologies/standard-fastapi.md) |
| SQLite | 3.x | Хранилище данных | — |
| Pydantic | 2.x | Валидация схем | — |
| openai SDK | 1.x | LLM-клиент для OpenRouter | [standard-openrouter.md](../.technologies/standard-openrouter.md) |
| httpx | 0.27 | HTTP-клиент для WB API, Ozon API | — |

### Пакеты

Код организован по слоям: `app/api/` (роуты и DI), `app/services/` (бизнес-логика), `app/clients/` (клиенты внешних API), `app/db.py` (хранилище), `app/schemas.py` (Pydantic-схемы).

| Пакет | Назначение | Ключевые модули |
|-------|-----------|----------------|
| `app/api/routes/` | HTTP endpoint-ы | `transfers.py`, `catalog.py`, `auth.py`, `connections.py` |
| `app/api/` | DI и зависимости | `deps.py` |
| `app/services/` | Бизнес-логика | `transfer.py`, `mapping.py`, `catalog.py`, `auth.py`, `connection.py` |
| `app/services/container.py` | ServiceContainer (DI-корень) | `container.py` |
| `app/clients/` | Клиенты внешних API | `wb.py`, `ozon.py`, `base.py` |
| `app/` | Конфигурация и инфраструктура | `config.py`, `db.py`, `schemas.py`, `main.py`, `security.py` |

### Точки входа

- API: `app/main.py` — `create_app(settings?)` создаёт `ServiceContainer`, инициализирует БД, монтирует роуты
- Конфигурация: `app/config.py` — `Settings.from_env()`

### Внутренние зависимости

```
app/api/routes/ → app/api/deps.py → app/services/container.py
app/services/transfer.py → app/services/mapping.py
app/services/transfer.py → app/services/catalog.py
app/services/mapping.py → app/clients/ozon.py (find_brand_id)
app/services/mapping.py → openai SDK (auto_match_category_llm)
app/services/catalog.py → app/clients/wb.py
app/services/catalog.py → app/clients/ozon.py
app/clients/wb.py → app/clients/base.py
app/clients/ozon.py → app/clients/base.py
app/services/container.py → app/db.py
app/services/container.py → app/security.py
```

**Как добавить новый функционал:**
- Новый endpoint → добавить схемы в `app/schemas.py`, роут в `app/api/routes/{domain}.py`, логику в `app/services/{service}.py`, получение сервиса через `app/api/deps.py`
- Новый метод API маркетплейса → добавить метод в `app/clients/wb.py` или `app/clients/ozon.py`, реализующий ABC `MarketplaceClient`, вызвать из соответствующего сервиса

### Makefile таргеты

| Таргет | Команда | Описание |
|--------|---------|----------|
| test-perenoska | `make test-perenoska` | Unit + integration тесты (pytest) |
| lint-perenoska | `make lint-perenoska` | Линтинг кода |

## Зависимости

Сервис зависит от трёх внешних API: WB API (получение карточек и категорий, создание карточек WB), Ozon API (получение категорий и брендов, создание карточек Ozon), OpenRouter API (LLM-маппинг категорий). Все зависимости критические — при недоступности любой из них соответствующие операции переноса возвращают 502.

### WB API — получение и создание карточек

Сервис обращается к WB API для получения карточек товаров (`POST /content/v2/get/cards/list`), справочника родительских категорий (`GET /content/v2/object/parent/all`), дочерних категорий (`GET /content/v2/object/all`) и создания карточек (`POST /content/v2/cards/upload`). Подключение через `app/clients/wb.py` (`WBClient`) с передачей credentials из `marketplace_connections`. При недоступности WB API возвращается 502 с кодом `WB_API_UNAVAILABLE`.
Паттерн: **ACL** (Anti-Corruption Layer — `WBClient` адаптирует структуры WB API к внутренним моделям).
См. [INT-1: perenoska → WB API](../analysis/0002-wb-ozon-product-transfer/design.md#int-1-perenoska--wb-api).

### Ozon API — получение и создание карточек, поиск брендов

Сервис обращается к Ozon API для получения дерева категорий (`POST /v1/description-category/tree`), поиска брендов (`POST /v1/brand/list`), создания карточек (`POST /v3/product/import`) и получения статуса импорта (`POST /v1/product/import/info`). Подключение через `app/clients/ozon.py` (`OzonClient`) с передачей credentials. При недоступности возвращается 502 с кодом `OZON_API_UNAVAILABLE`.
Паттерн: **ACL** (Anti-Corruption Layer — `OzonClient` адаптирует структуры Ozon API к внутренним моделям).
См. [INT-2: perenoska → Ozon API](../analysis/0002-wb-ozon-product-transfer/design.md#int-2-perenoska--ozon-api).

### OpenRouter API — LLM-маппинг категорий

Сервис обращается к OpenRouter API через `openai` SDK с `base_url=https://openrouter.ai/api/v1` для подбора категории целевого маркетплейса через LLM. Модель конфигурируется через `Settings.llm_model` (default `mistralai/mistral-7b-instruct:free`). При ошибке OpenRouter `MappingService` возвращает `(None, 0.0)` — preview устанавливает `category_requires_manual=true`.
Паттерн: **Conformist** (полностью следует OpenAI-совместимому API OpenRouter).
См. [INT-3: perenoska → OpenRouter API](../analysis/0002-wb-ozon-product-transfer/design.md#int-3-perenoska--openrouter-api).

## Доменная модель

Сервис реализует домен переноса карточек товаров между маркетплейсами. Основная бизнес-сущность — `TransferJob` (задача переноса), жизненный цикл: `pending → submitted → processing → completed / failed`. Операция preview предшествует переносу и обеспечивает маппинг полей, категорий и брендов с возможностью ручной корректировки.

### Агрегаты

| Агрегат | Описание |
|---------|----------|
| TransferJob | Задача переноса товаров. Атрибуты: `job_id`, `user_id`, `status`, `payload_json`, `result_json`. Жизненный цикл: `pending → submitted → processing → completed / failed` |
| TransferPreviewItem | Результат preview для одного товара. Атрибуты: `product_id`, `target_category_id`, `category_confidence`, `category_requires_manual`, `brand_id_suggestion`, `brand_id_requires_manual`, `mapped_attributes`, `missing_required_attributes`, `warnings`. Не персистируется — живёт в рамках одного запроса |

### Инварианты

- Карточка передаётся на целевой маркетплейс без явного `status` (Ozon создаёт как черновик по умолчанию; WB — аналогично)
- Перенос блокируется (`ready_to_import=false`) если хотя бы одно из полей `brand_id_requires_manual` или `category_requires_manual` равно `true` и override не предоставлен

### Доменные события

| Событие | Описание |
|---------|----------|
| TransferJobCreated | Создана задача переноса → статус `pending` |
| TransferJobSubmitted | Карточка передана в целевой маркетплейс → статус `submitted` |
| TransferJobFailed | Ошибка при передаче в целевой маркетплейс → статус `failed` |
| TransferJobCompleted | Целевой маркетплейс подтвердил обработку → статус `completed` |

## Границы автономии LLM

- **Свободно:** маппинг полей `description↔annotation` (детерминированный маппинг, покрыт тестами), передача `images` (URL-список без трансформации), маппинг атрибутов через `FIELD_SYNONYMS` (существующая логика, расширение словаря), рефакторинг внутри одного модуля без изменения публичного интерфейса
- **Флаг:** промпт для LLM маппинга категорий (изменение промпта влияет на качество маппинга), LLM-модель (`llm_model`) (смена модели влияет на поведение маппинга), логика поиска `brand_id` (exact/fuzzy) (изменение алгоритма может нарушить маппинг), порог confidence (< 0.7) (влияет на UX: слишком высокий порог = много ручного ввода)
- **CONFLICT:** изменение контракта API preview (поля ответа `TransferPreviewItem`) — breaking change для клиентов; изменение `build_import_payload()` формата Ozon — влияет на корректность создания карточки; изменение Data Model (колонки, индексы); изменение механизма аутентификации Bearer token

## Planned Changes

*Нет запланированных изменений.*

## Changelog

- **0002-wb-ozon-product-transfer** | DONE 2026-03-26 — корректный перенос карточек WB↔Ozon: LLM-маппинг категорий (OpenRouter), многошаговый поиск brand_id (Ozon API), description→annotation, GET /api/v1/catalog/{marketplace}/brands, TransferPreviewItem расширен (category_confidence, brand_id_suggestion, requires_manual-флаги).
- **Создание сервиса** | DONE 2026-03-25 — первоначальная документация.
