---
description: Инфраструктура Perenoska — платформа, окружения, хранилища, сервисы.
standard: specs/.instructions/docs/infrastructure/standard-infrastructure.md
standard-version: v1.1
---

# Инфраструктура

## Локальный запуск

Все команды определены в [Makefile](/Makefile) (SSOT). Полный список: `make help`.

**Порядок запуска (локально без Docker):**
```bash
python -m venv .venv && .venv/Scripts/activate
pip install -e .[dev]
cp .env.example .env   # заполнить APP_SECRET_KEY и OPENROUTER_API_KEY
uvicorn app.main:app
```

**Порядок запуска (Docker):**
```bash
cp platform/docker/.env.example platform/docker/.env   # заполнить секреты
docker compose -f platform/docker/docker-compose.yml up
```

**Переменные окружения:** скопировать `.env.example` → `.env` (локально) или `platform/docker/.env.example` → `platform/docker/.env` (Docker). Описание каждой переменной — в `platform/docker/.env.example`. Для dev-окружения `.env.example` содержит безопасные defaults.

## Сервисы и порты

| Сервис | Хост (docker) | Хост (local) | Порт | URL | Healthcheck |
|--------|--------------|-------------|------|-----|-------------|
| perenoska | perenoska | localhost | 8000 | http://localhost:8000 | GET /health |

**Swagger UI:** http://localhost:8000/docs

Порт хоста задаётся через `PERENOSKA_PORT` (default: 8000). Внутри контейнера сервис всегда слушает порт 8000.

## Хранилища

### SQLite (основное хранилище данных)

| Параметр | Значение (dev) | Env-переменная |
|----------|---------------|----------------|
| Путь (локально) | data/perenositsa.db | `APP_DATABASE_PATH` |
| Путь (docker) | /app/data/perenositsa.db | `APP_DATABASE_PATH` |

**Connection string:** `sqlite:///${APP_DATABASE_PATH}`

Данные в Docker хранятся в именованном volume `perenoska_data` (`/app/data`).

**4 таблицы:** `users`, `sessions`, `marketplace_connections`, `transfer_jobs`. Каждый метод открывает соединение отдельно (нет connection pool). Поля `payload_json`/`result_json` — JSON-строки, десериализуются при чтении.

## Message Broker

*Брокер сообщений не используется.*

## Service Discovery

Perenoska — единственный сервис. Внешние зависимости (WB API, Ozon API, OpenRouter API) задаются через env-переменные.

| Сервис-источник | Сервис-цель | Механизм | Значение (dev) | Env-переменная |
|----------------|------------|----------|---------------|----------------|
| perenoska | WB API | env var (локально) / hardcoded default (docker) | https://content-api.wildberries.ru | `WB_BASE_URL` (только .env.example корня; в docker-compose не прокинута) |
| perenoska | Ozon API | env var (локально) / hardcoded default (docker) | https://api-seller.ozon.ru | `OZON_BASE_URL` (только .env.example корня; в docker-compose не прокинута) |
| perenoska | OpenRouter API | hardcoded в container.py (docker env var опциональна) | https://openrouter.ai/api/v1 | `LLM_BASE_URL` (platform/docker/.env.example; захардкожен в container.py) |

## Окружения

| Параметр | dev | docker |
|----------|-----|--------|
| Реплики сервисов | 1 | 1 |
| БД | data/perenositsa.db (local) | volume perenoska_data |
| Секреты | .env файл | .env файл (platform/docker/) |
| Домен | localhost:8000 | localhost:${PERENOSKA_PORT} |
| TLS | нет | нет |
| Логирование | stdout | stdout (docker logs perenoska) |

## Мониторинг и логи

**Формат логов:** текстовый stdout

**Где смотреть:**

| Окружение | Логи |
|-----------|------|
| dev | stdout (uvicorn консоль) |
| docker | `docker compose -f platform/docker/docker-compose.yml logs -f perenoska` |

**Healthcheck (docker-compose):**
```
test: python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
interval: 30s
timeout: 10s
start_period: 15s
retries: 3
```

**Стандарт логирования:** см. [conventions.md](./conventions.md) секция Логирование.

## Секреты

**Правило:** секреты НИКОГДА не коммитятся. Только `.env.example` и `platform/docker/.env.example` с пустыми/безопасными значениями.

| Секрет | Env-переменная | Источник (dev) | Обязательно |
|--------|---------------|----------------|-------------|
| Ключ шифрования Fernet для API-ключей в БД | `APP_SECRET_KEY` | .env | Да |
| API-ключ OpenRouter для LLM-маппинга категорий | `OPENROUTER_API_KEY` | .env | Да (для preview) |
| Путь к SQLite | `APP_DATABASE_PATH` | .env (optional) | Нет |
| TTL сессии (часы) | `APP_SESSION_TTL_HOURS` | .env (optional, default 24) | Нет |
| LLM-модель | `LLM_MODEL` | .env (optional, default mistralai/mistral-7b-instruct:free) | Нет |
| Таймаут HTTP-запросов (сек) | `HTTP_TIMEOUT_SECONDS` | .env (optional, default 30) | Нет |
| Базовый URL OpenRouter | `LLM_BASE_URL` | platform/docker/.env (optional) | Нет (захардкожен в container.py) |
| Порт хоста perenoska (docker) | `PERENOSKA_PORT` | .env (optional, default 8000) | Нет |

API-ключи маркетплейсов (WB token, Ozon client_id/api_key) хранятся в БД в зашифрованном виде (Fernet, ключ = `APP_SECRET_KEY`). В env не передаются.
