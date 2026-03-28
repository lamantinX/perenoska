---
description: Конвенции API и shared-интерфейсы — кросс-сервисные соглашения
standard: specs/.instructions/docs/conventions/standard-conventions.md
standard-version: v1.1
---

# Конвенции API

## Формат ответов

Все API возвращают JSON. Content-Type: `application/json`.

**Единичный объект (пример — job):**
```json
{"job_id": "job-abc123", "status": "pending", "product_count": 1}
```

**Список с пагинацией (пример — бренды):**
```json
{
  "items": [
    {"id": 1000, "name": "Nike"},
    {"id": 1001, "name": "Nike Sport"}
  ],
  "total": 2
}
```

**Даты:** ISO 8601 с timezone (`2026-03-01T12:00:00Z`).

## Формат ошибок

Все ошибки возвращаются в едином формате через `detail`:

```json
{
  "detail": {
    "code": "WB_API_UNAVAILABLE",
    "message": "WB API unavailable"
  }
}
```

**Стандартные коды ошибок:**

| HTTP Status | Код | Когда |
|-------------|-----|-------|
| 400 | `TRANSFER_NOT_READY` | `ready_to_import=false`, перенос заблокирован |
| 400 | *(без кода)* | marketplace != ozon (catalog/brands), нет credentials — FastAPI default 400 |
| 401 | `UNAUTHORIZED` | Отсутствует или невалидный Bearer-токен |
| 404 | `NOT_FOUND` | Ресурс не найден |
| 422 | `VALIDATION_ERROR` | Валидация полей Pydantic не прошла |
| 502 | `WB_API_UNAVAILABLE` | Недоступен WB API (ConnectionError) |
| 502 | `OZON_API_UNAVAILABLE` | Недоступен Ozon API (ConnectionError) |

**Реализация в FastAPI:**
```python
from fastapi import HTTPException

raise HTTPException(
    status_code=502,
    detail={"code": "WB_API_UNAVAILABLE", "message": "WB API unavailable"}
)
```

## Пагинация

Списочные endpoint-ы принимают:

| Параметр | Тип | Default | Max | Описание |
|----------|-----|---------|-----|----------|
| q | str | — | — | Поисковый запрос (для брендов) |
| limit | int | 20 | 100 | Количество записей на страницу |

Ответ содержит `items` и `total`.

**Пример — `GET /api/v1/catalog/{marketplace}/brands`:**
```python
@router.get("/catalog/{marketplace}/brands")
async def list_brands(
    marketplace: str,
    q: str,
    limit: int = Query(default=20, ge=1, le=100),
    ...
):
    ...
```

## Аутентификация

**Заголовок:** `Authorization: Bearer {token}`

**Тип токена:** `secrets.token_urlsafe(32)` (не JWT). Хранится в таблице `sessions` (SQLite).

- Время жизни: `APP_SESSION_TTL_HOURS` (по умолчанию 24 часа)
- Передаётся всеми endpoint-ами кроме публичных

**Публичные endpoint-ы (без токена):** `POST /api/v1/auth/register`, `POST /api/v1/auth/login`

**Все остальные endpoint-ы** требуют валидный Bearer-токен. Dependency `get_current_user` проверяет токен через `AuthService`.

## Версионирование API

Все endpoint-ы: `/api/v1/...`

**Правила:**
- Добавление нового поля в response — совместимо, не требует новой версии
- Удаление или переименование поля — несовместимо, требует v2
- Добавление опционального query-параметра — совместимо
- Изменение формата существующего поля — несовместимо

## Shared-пакеты

*Shared-пакеты будут добавлены при появлении переиспользуемого кода между сервисами.*

## Логирование

Логирование через стандартный Python `logging`. Каждое значимое событие логируется на уровне INFO или ERROR.

**Уровни:**

| Уровень | Когда использовать | Пример |
|---------|-------------------|----|
| INFO | Успешные операции: карточка создана, job запущен | `transfer.launched job_id=job-abc123` |
| WARNING | Восстановимые проблемы: LLM вернул низкую уверенность, graceful degradation | `category.low_confidence product_id=12345678 confidence=0.45` |
| ERROR | Сбои: недоступен WB/Ozon API, ошибка создания карточки | `wb_api.unavailable error=ConnectionError` |

**Обязательные поля:**

| Поле | Источник | Описание |
|------|---------|----------|
| `level` | logging (auto) | DEBUG / INFO / WARNING / ERROR |
| `message` | код | Описание события в формате `{domain}.{action}` |
| `job_id` / `product_id` | контекст запроса | ID объекта для трассировки (не данные пользователя) |

**Базовый паттерн:**

```python
import logging

logger = logging.getLogger(__name__)

# В сервисе:
def launch_transfer(job_id: str, product_count: int):
    logger.info("transfer.launching", extra={"job_id": job_id, "product_count": product_count})
    try:
        result = do_launch(job_id)
        logger.info("transfer.launched", extra={"job_id": job_id})
    except MarketplaceAPIError as e:
        logger.error("transfer.failed", extra={"job_id": job_id, "error": str(e)})
        raise
```

**Запрещено логировать:** пароли, API-ключи маркетплейсов (хранятся зашифрованными через Fernet), Bearer-токены сессий.

## Требования по уровням критичности

Конвенции отказоустойчивости и логирования зависят от уровня критичности сервиса. Уровень определяется в `{svc}.md` (поле `criticality`). Сервис `perenoska` имеет уровень `critical-high`.

**Отказоустойчивость:**

| Критерий | critical-high | critical-medium | critical-low |
|----------|--------------|-----------------|--------------|
| Retry policy | Aggressive (3-5 retries, exponential backoff) | Moderate (2-3 retries) | Basic (1 retry) |
| Circuit breaker | Обязателен | Обязателен | Рекомендуется |
| Fallback strategy | Обязательна (graceful degradation) | Рекомендуется | Не требуется |
| Replicas (min) | ≥3 | ≥2 | ≥1 |
| Auto-scaling | Обязательно | Обязательно | Опционально |

**Логирование:**

| Критерий | critical-high | critical-medium | critical-low |
|----------|--------------|-----------------|--------------|
| Уровень логирования | Structured, все операции | Structured, ошибки + ключевые операции | Ошибки |
| Retention | ≥90 дней | ≥30 дней | ≥14 дней |
| Tracing | Distributed tracing обязателен | Рекомендуется | Не требуется |
| Audit log | Обязателен для мутаций | Рекомендуется | Не требуется |
