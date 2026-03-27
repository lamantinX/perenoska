# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

**Структура:** [.structure/README.md](/.structure/README.md) — SSOT структуры проекта

**Onboarding:** [onboarding.md](/.claude/onboarding.md)

**Правила:** контекст загружается автоматически из `/.claude/rules/` при работе с файлами.

**AskUserQuestion:** При предложении вариантов выбора использовать `AskUserQuestion` tool.

## Проект

**Perenoska** — веб-сервис на FastAPI для переноса карточек товаров между Wildberries и Ozon.

| Папка | Назначение |
|-------|------------|
| `/app/` | FastAPI приложение (auth, catalog, transfers, marketplace-клиенты) |
| `/tests/` | Тесты (pytest) |
| `/specs/` | Спецификации, анализ, документация |
| `/.claude/` | Скиллы, rules, агенты, инструкции |

## Команды

```bash
make setup      # Установить pre-commit хуки
make test       # Запустить тесты (pytest)
make lint       # Линтинг
make help       # Показать все команды

# Ручной запуск
python -m venv .venv && .venv/Scripts/activate
pip install -e .[dev]
uvicorn app.main:app

# Один тест
pytest tests/test_auth_and_connections.py::test_register_login_and_save_connection
```

**Swagger UI:** `http://127.0.0.1:8000/docs`

## Архитектура

### Точка входа и DI

`app/main.py` — `create_app(settings?)` создаёт `ServiceContainer`, инициализирует БД и монтирует роуты. `app.state.container` — единственный корень зависимостей; `app/api/deps.py` достаёт сервисы через `Depends(get_container)`.

`app/services/container.py` — `ServiceContainer` владеет всеми синглтонами:
- `Database` (SQLite через `app/db.py`)
- `CredentialVault` + `PasswordManager` (шифрование через `app/security.py`)
- `MarketplaceClientFactory` — строит WB/Ozon-клиентов, поддерживает `register_override()` для тестов
- `AuthService`, `ConnectionService`, `MappingService`

`CatalogService` и `TransferService` — stateless, создаются per-request в `deps.py`.

### Маркетплейс-клиенты

`app/clients/base.py` — `MarketplaceClient` (ABC с 6 методами). Реализации: `WBClient`, `OzonClient`. Клиенты инжектируются через `MarketplaceClientFactory`; в тестах заменяются через `register_override`.

### Поток переноса

1. `POST /api/v1/transfers/preview` → `TransferService.preview()` — авто-маппинг категорий через `MappingService`, возвращает `ready_to_import`
2. `POST /api/v1/transfers` → `TransferService.launch()` — проверяет `ready_to_import`, создаёт `transfer_job` (PENDING), вызывает `target_client.create_products()`, обновляет статус → SUBMITTED или FAILED
3. `POST /api/v1/transfers/{job_id}/sync` → `sync_status()` — опрашивает `get_import_status()` у целевого маркетплейса, маппит remote status → PROCESSING / COMPLETED / FAILED

Статусы `JobStatus`: `pending → submitted → processing → completed / failed`.

### Аутентификация

Bearer-токен (не JWT): `secrets.token_urlsafe(32)`, хранится в таблице `sessions`. `PasswordManager` — PBKDF2/SHA-256 с 600 000 итерациями. `CredentialVault` — Fernet-шифрование API-ключей маркетплейсов перед записью в БД.

### БД

SQLite (`app/db.py`). Путь — `APP_DATABASE_PATH` (по умолчанию `data/perenositsa.db`). 4 таблицы: `users`, `sessions`, `marketplace_connections`, `transfer_jobs`. Каждый метод открывает соединение отдельно (нет connection pool). `payload_json`/`result_json` — JSON-строки, десериализуются при чтении.

### Конфигурация

`app/config.py` — `Settings.from_env()`. Ключевые переменные:

| Переменная | Назначение |
|------------|------------|
| `APP_SECRET_KEY` | Ключ шифрования (Fernet), по умолчанию небезопасный |
| `APP_DATABASE_PATH` | Путь к SQLite |
| `APP_SESSION_TTL_HOURS` | Срок жизни сессии (по умолчанию 24) |

### Тесты

Используют `create_app(settings)` с `tmp_path` pytest-фикстурой — SQLite в временной директории. Для изоляции от реальных API используют `container.client_factory.register_override(marketplace, FakeClient())`.

```python
settings = Settings(..., database_path=tmp_path / "test.db")
app = create_app(settings)
client = TestClient(app)
```

## Разработка

**Изменение поведения системы:** `/chain`. **Баги и хотфиксы:** `/hotfix`

| Команда | Когда |
|---------|-------|
| `/chain` | Новая фича, изменение поведения |
| `/chain --resume` | Продолжить после прерывания |
| `/hotfix` | Баги, production-инциденты |
| `/init-project` | Полная настройка GitHub, docs/, среда |

### 8 фаз процесса /chain

| Фаза | Что происходит | Ключевые скиллы/агенты |
|------|---------------|----------------------|
| 1. Analysis chain | Discussion → Design → Plan Tests → Plan Dev | `/discussion-create`, `/design-create`, `/plan-test-create`, `/plan-dev-create` |
| 2. Docs Sync | Параллельные агенты: per-service docs, per-tech стандарты | `/docs-sync` |
| 3. Запуск | Issues + Milestone + Branch | `/dev-create` |
| 4. Реализация | Код по TASK-N + коммиты | dev-agent, `/commit` |
| 5. Финальная валидация | tests/lint/build → отчёт READY/NOT READY | `/test` |
| 6. Доставка | Branch Review → PR → Merge | `/review`, `/pr-create`, `/merge` |
| 7. Завершение | RUNNING → DONE (docs AS IS) | `/chain-done` |
| 8. Поставка | Release → Deploy | `/release-create`, `/post-release` |

## Поиск

```bash
python .instructions/.scripts/search-docs.py --search "запрос"
python .instructions/.scripts/search-docs.py --type skill --search "запрос"
```

## Паттерны

- API структура: `POST /api/v1/{domain}/{action}`
- Новый маркетплейс-клиент: реализовать `MarketplaceClient` ABC, зарегистрировать в `MarketplaceClientFactory.get_client()`
- Новый сервис: добавить в `ServiceContainer`, добавить `get_*` в `deps.py`
