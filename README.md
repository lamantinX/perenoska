# Perenositsa

Веб-сервис на FastAPI для переноса карточек товаров между Wildberries и Ozon с минималистичным интерфейсом.

## Что уже реализовано

- регистрация и логин пользователя;
- хранение подключений WB/Ozon в SQLite;
- шифрование токенов и API-ключей перед записью в БД;
- клиенты WB/Ozon с базовыми методами для товаров, категорий и импорта;
- веб-интерфейс для авторизации, подключения маркетплейсов, выбора товаров, preview и просмотра задач;
- предпросмотр переноса с попыткой авто-маппинга атрибутов;
- запуск задачи переноса и отдельная синхронизация статуса;
- тесты для аутентификации, подключений и сценария preview/import на фейковых клиентах.

## Принятые допущения

- интерфейс реализован как встроенный SPA без отдельного frontend build-процесса;
- сложный маппинг атрибутов сделан эвристически по именам и базовым синонимам;
- для реальной прод-эксплуатации нужно доработать очереди, retry, rate limiting, аудит, RBAC и полноценную категорийную матрицу;
- часть ответов WB/Ozon обрабатывается в tolerant-режиме, потому что структуры могут отличаться между версиями API.

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
copy .env.example .env
uvicorn app.main:app
```

Swagger UI будет доступен по адресу `http://127.0.0.1:8000/docs`.

## Веб-интерфейс

- основной интерфейс: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`

В интерфейсе доступны:

- регистрация и вход;
- сохранение ключей WB и Ozon;
- загрузка каталога из WB или Ozon;
- выбор карточек для переноса;
- загрузка категорий приемника;
- preview итогового payload;
- запуск переноса и просмотр истории задач.

## Основные endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/connections`
- `PUT /api/v1/connections/{marketplace}`
- `GET /api/v1/catalog/products?marketplace=wb`
- `GET /api/v1/catalog/categories?marketplace=ozon`
- `GET /api/v1/catalog/categories/{category_id}/attributes?marketplace=ozon`
- `POST /api/v1/transfers/preview`
- `POST /api/v1/transfers`
- `GET /api/v1/transfers`
- `GET /api/v1/transfers/{job_id}`
- `POST /api/v1/transfers/{job_id}/sync`

## Что логично делать следующим шагом

- добавить Celery/RQ или другой background worker;
- вынести таблицу соответствия категорий в отдельную сущность;
- добавить загрузку медиа на свой CDN/storage;
- сохранить историю ручных корректировок маппинга для повторного использования;
- закрыть интеграционные тесты через sandbox-кабинеты WB и Ozon.
