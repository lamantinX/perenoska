# File Map

## Точки входа

- `app/main.py` — создание FastAPI-приложения и подключение UI
- `app/config.py` — настройки из окружения
- `app/db.py` — SQLite-схема и операции доступа

## HTTP-слой

- `app/api/routes/auth.py` — регистрация, логин, current user
- `app/api/routes/connections.py` — сохранение и чтение подключений
- `app/api/routes/catalog.py` — товары, категории, атрибуты
- `app/api/routes/transfers.py` — preview, запуск и синхронизация задач

## Сервисы

- `app/services/auth.py` — аутентификация и сессии
- `app/services/connections.py` — безопасное хранение credentials
- `app/services/catalog.py` — чтение каталога и атрибутов
- `app/services/mapping.py` — авто-сопоставление и сбор payload
- `app/services/transfer.py` — orchestration переноса
- `app/services/container.py` — wiring зависимостей

## Внешние интеграции

- `app/clients/base.py` — контракт marketplace client
- `app/clients/wb.py` — интеграция Wildberries
- `app/clients/ozon.py` — интеграция Ozon

## UI

- `app/static/index.html` — оболочка интерфейса
- `app/static/app.js` — клиентская логика
- `app/static/app.css` — стили

## Тесты

- `tests/test_auth_and_connections.py` — auth и connections
- `tests/test_transfer_preview.py` — preview/import/sync и связанные edge cases
