# Perenoska

FastAPI-сервис для переноса карточек товаров между Wildberries и Ozon с встроенным веб-интерфейсом.

## Что есть сейчас

- регистрация, логин и сессии пользователей;
- хранение подключений WB/Ozon в SQLite;
- шифрование токенов и API-ключей перед записью в БД;
- клиенты WB/Ozon для каталога, категорий и импорта;
- встроенный SPA без отдельного frontend build-процесса;
- preview переноса с авто-маппингом категорий и атрибутов;
- запуск задач переноса и синхронизация статуса;
- тесты для auth, connections и preview/import сценариев.

## Структура проекта

- `app/` — приложение FastAPI, сервисы, API-роуты, клиенты маркетплейсов
- `app/static/` — встроенный интерфейс
- `tests/` — тесты на `pytest`
- `docs/codex/` — локальная документация для работы через Codex
- `main.md`, `mozg.md` — проектные заметки и справочный контекст

## Локальный запуск

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

После запуска:

- UI: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`

## Проверка

```powershell
python -m pytest
```

Или:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

## Основные API endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/connections`
- `PUT /api/v1/connections/{marketplace}`
- `GET /api/v1/catalog/products?marketplace=...`
- `GET /api/v1/catalog/categories?marketplace=...`
- `GET /api/v1/catalog/categories/{category_id}/attributes?marketplace=...`
- `POST /api/v1/transfers/preview`
- `POST /api/v1/transfers`
- `GET /api/v1/transfers`
- `GET /api/v1/transfers/{job_id}`
- `POST /api/v1/transfers/{job_id}/sync`

## Ограничения MVP

- маппинг атрибутов местами эвристический;
- нет очередей, retry-механик и rate limiting;
- нет полноценной категорийной матрицы и истории ручных сопоставлений;
- интеграционные тесты с реальными sandbox-кабинетами пока не настроены.

## Git

Локальный `origin` для этого репозитория должен указывать на форк:

- `https://github.com/lamantinX/perenoska`

## Для Codex

Стартовая точка для новой сессии:

1. открыть `AGENTS.md`;
2. при необходимости прочитать `docs/codex/project-overview.md`;
3. использовать `docs/codex/file-map.md` и `docs/codex/workflow.md` для навигации и проверки изменений.
