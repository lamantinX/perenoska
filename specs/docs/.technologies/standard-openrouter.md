---
description: Стандарт кодирования OpenRouter — конвенции именования, HTTP-клиент, паттерны вызова LLM, антипаттерны.
standard: specs/.instructions/docs/technology/standard-technology.md
technology: openrouter
---

# Стандарт OpenRouter v1.0

## Версия и настройка

| Параметр | Значение |
|----------|----------|
| Версия | OpenRouter API v1 (latest) |
| Ключевые библиотеки | openai 1.x (основной SDK — openai-compatible клиент), httpx 0.27 (альтернативный HTTP-клиент), pydantic 2.10 (валидация ответов) |
| Конфигурация | `OPENROUTER_API_KEY` (env), `LLM_MODEL` (env, default: `mistralai/mistral-7b-instruct:free`) |

## Конвенции именования

| Объект | Конвенция | Пример |
|--------|----------|--------|
| Клиентский класс | PascalCase + `Client` | `OpenRouterClient` |
| Метод запроса | snake_case, глагол + сущ. | `complete_chat`, `stream_completion` |
| Модуль клиента | snake_case | `openrouter_client.py` |
| Константа модели | UPPER_SNAKE_CASE | `MODEL_GPT4O`, `MODEL_CLAUDE_3_5_SONNET` |
| Ответная Pydantic-модель | PascalCase + `Response` | `ChatCompletionResponse`, `ChatChoice` |
| Переменные окружения | `APP_OPENROUTER_` префикс | `APP_OPENROUTER_API_KEY`, `APP_OPENROUTER_BASE_URL` |
| Файл тестов | `test_` префикс | `test_openrouter_client.py` |

## Паттерны кода

### Инициализация клиента (основной паттерн — openai SDK)

Клиент инициализируется через `openai.AsyncOpenAI` с `base_url` override. Создаётся один раз в `ServiceContainer`, инжектируется через зависимости. API-ключ и модель читаются из `Settings`.

```python
from openai import AsyncOpenAI
from app.config import Settings


def create_openrouter_client(settings: Settings) -> AsyncOpenAI:
    """Создать AsyncOpenAI-клиент для OpenRouter. Вызывается в ServiceContainer."""
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )
```

В `ServiceContainer`:

```python
from openai import AsyncOpenAI
from app.config import Settings


class ServiceContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm_client: AsyncOpenAI = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        # llm_client инжектируется в MappingService
```

### Chat completion (основной запрос)

Стандартный паттерн для одиночного LLM-запроса через openai SDK. Клиент (`AsyncOpenAI`) передаётся через конструктор сервиса.

```python
from openai import AsyncOpenAI


class MappingService:
    def __init__(self, llm_client: AsyncOpenAI, llm_model: str) -> None:
        self._llm_client = llm_client
        self._llm_model = llm_model

    async def complete_chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 256,
    ) -> str:
        """Отправить список сообщений, вернуть текст ответа."""
        response = await self._llm_client.chat.completions.create(
            model=self._llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
```

### Structured output / JSON mode

Ключевой паттерн для Design 0002: LLM возвращает `{"category_id": N, "confidence": 0.0..1.0}`. Используется `response_format={"type": "json_object"}` и `json.loads` с fallback при `JSONDecodeError`.

```python
import json
import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


async def match_category_llm(
    llm_client: AsyncOpenAI,
    llm_model: str,
    source_category: str,
    target_categories: list[dict],  # [{"id": int, "name": str}, ...]
) -> tuple[int | None, float]:
    """LLM-маппинг категорий. Возвращает (category_id | None, confidence)."""
    prompt = (
        f"Source category: {source_category}\n"
        f"Target categories: {json.dumps(target_categories, ensure_ascii=False)}\n"
        "Return JSON: {\"category_id\": <int>, \"confidence\": <0.0..1.0>}"
    )
    try:
        response = await llm_client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=128,
        )
        content = response.choices[0].message.content or ""
        data = json.loads(content)
        category_id = int(data["category_id"])
        confidence = float(data["confidence"])
        return category_id, confidence
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("llm.parse_error model=%s error=%s", llm_model, exc)
        return None, 0.0
    except Exception as exc:
        logger.error("llm.request_failed model=%s error=%s", llm_model, exc)
        return None, 0.0
```

### Альтернативный клиент через httpx

Использовать только если openai SDK недоступен или требуется кастомный транспорт.

```python
import httpx


class OpenRouterHttpxClient:
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str) -> None:
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    async def close(self) -> None:
        await self._http.aclose()
```

### Обработка ошибок

OpenRouter возвращает HTTP 4xx/5xx с телом `{"error": {"message": ..., "code": ...}}`. Всегда оборачивать в доменное исключение. Логировать статус и тело ответа.

```python
import logging

logger = logging.getLogger(__name__)


class OpenRouterError(Exception):
    """Базовое исключение OpenRouter."""
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenRouterRateLimitError(OpenRouterError):
    """HTTP 429 — превышен лимит запросов."""


class OpenRouterAuthError(OpenRouterError):
    """HTTP 401/403 — неверный ключ или нет доступа к модели."""


async def safe_complete_chat(client: "OpenRouterClient", messages: list[dict], model: str) -> str:
    """Обёртка с обработкой HTTP-ошибок OpenRouter."""
    try:
        return await client.complete_chat(messages=messages, model=model)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        try:
            detail = exc.response.json().get("error", {}).get("message", str(exc))
        except Exception:
            detail = str(exc)
        logger.error(
            "openrouter.request_failed status=%d model=%s error=%s",
            status, model, detail,
        )
        if status == 429:
            raise OpenRouterRateLimitError(detail, status_code=status) from exc
        if status in (401, 403):
            raise OpenRouterAuthError(detail, status_code=status) from exc
        raise OpenRouterError(detail, status_code=status) from exc
    except httpx.TimeoutException as exc:
        logger.error("openrouter.timeout model=%s", model)
        raise OpenRouterError("Request timed out") from exc
```

### Повтор с экспоненциальной задержкой (retry)

Использовать для rate-limit ошибок (429). Не повторять 401/403 — они не самоустраняются.

```python
import asyncio


async def complete_with_retry(
    client: "OpenRouterClient",
    messages: list[dict],
    model: str,
    max_retries: int = 3,
) -> str:
    """Запрос с автоматическим повтором при rate-limit."""
    for attempt in range(max_retries):
        try:
            return await client.complete_chat(messages=messages, model=model)
        except OpenRouterRateLimitError:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(
                "openrouter.rate_limit_retry attempt=%d wait=%ds", attempt + 1, wait
            )
            await asyncio.sleep(wait)
    raise OpenRouterError("Max retries exceeded")
```

### Связь с SDD процессом

| Момент SDD | Действие с OpenRouter |
|------------|----------------------|
| Design (SVC-N § Tech Stack) | OpenRouter указан как LLM-провайдер; модель конфигурируется через `Settings.llm_model` |
| Design (INT-3) | Описывает вызов `POST /chat/completions` через openai SDK с `response_format: json_object`, `temperature: 0.1` |
| INFRA-блок (wave 0) | Dev-agent добавляет `openrouter_api_key`, `llm_model` в `Settings`; создаёт `AsyncOpenAI` в `ServiceContainer` |
| Per-service блок | Dev-agent реализует `auto_match_category_llm()` в `MappingService`, передаёт `llm_client: AsyncOpenAI` через конструктор |
| Тесты | Мокировать `AsyncOpenAI` через `AsyncMock` или создать `FakeLLMClient` с фиксированными ответами |

```python
# Мок AsyncOpenAI для unit-тестов MappingService
from unittest.mock import AsyncMock, MagicMock
from openai import AsyncOpenAI


def make_fake_llm_client(category_id: int = 42, confidence: float = 0.9) -> AsyncOpenAI:
    """AsyncOpenAI-мок с фиксированным JSON-ответом."""
    mock_client = MagicMock(spec=AsyncOpenAI)
    choice = MagicMock()
    choice.message.content = f'{{"category_id": {category_id}, "confidence": {confidence}}}'
    completion = MagicMock()
    completion.choices = [choice]
    mock_client.chat.completions.create = AsyncMock(return_value=completion)
    return mock_client
```

## Антипаттерны

| Антипаттерн | Почему плохо | Правильно |
|-------------|-------------|-----------|
| Хранить `api_key` в коде или в `config.py` как строку | API-ключ попадает в git-историю, утечка credentials | Читать только из env через `Settings` |
| Создавать `httpx.AsyncClient` на каждый запрос | Overhead установки TCP-соединения, исчерпание сокетов | Один `AsyncClient` на lifetime сервиса, закрывать в `shutdown` |
| Не вызывать `response.raise_for_status()` | Ошибки 4xx/5xx игнорируются, возвращается мусор | Всегда `raise_for_status()` перед парсингом ответа |
| Передавать `temperature=1.0` для детерминированных задач | Недетерминированные ответы, нестабильное поведение маппинга | `temperature=0.0–0.2` для структурированных/детерминированных задач |
| Парсить `response.json()["choices"][0]["message"]["content"]` без валидации | KeyError при изменении схемы ответа — runtime crash | Использовать Pydantic-модель `ChatCompletionResponse.model_validate(...)` |
| Не ставить `timeout` на `AsyncClient` | Запрос висит вечно при сбое сети, worker зависает | Явно указывать `timeout=60.0` (или настраиваемый через Settings) |
| Повторять 401/403 ошибки | Ключ невалиден — повторы бессмысленны, расходуют квоту | Повторять только 429 и 5xx |

## Структура файлов

```
app/
├── clients/
│   ├── base.py                # MarketplaceClient ABC (существующий)
│   └── openrouter_client.py   # OpenRouterClient — HTTP-клиент + retry
├── services/
│   └── mapping_service.py     # Использует OpenRouterClient для LLM-маппинга
└── config.py                  # APP_OPENROUTER_API_KEY, APP_OPENROUTER_BASE_URL
tests/
└── test_openrouter_client.py  # Unit-тесты с мок-клиентом
```

## Валидация

*Скрипт валидации кода не создан. Валидация выполняется вручную по чек-листу из [validation-technology.md](./validation-technology.md).*

## Тестирование

Unit-тесты мокируют `httpx.AsyncClient` через `unittest.mock`. Integration-тесты с реальным API не запускаются в CI (требуют ключ). Используется `pytest` с `pytest-asyncio`.

### Фреймворк и плагины

| Компонент | Пакет | Назначение |
|-----------|-------|-----------|
| Фреймворк | `pytest 8.x` | Основной test runner |
| Async | `pytest-asyncio 0.23` | Поддержка async/await |
| HTTP-мок | `unittest.mock` (stdlib) | Мокирование `httpx.AsyncClient` |
| HTTP-мок (опц.) | `respx 0.21` | Мокирование на уровне транспорта httpx |

### Фикстуры

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.clients.openrouter_client import OpenRouterClient


@pytest.fixture
def mock_http_client():
    """Мок httpx.AsyncClient для unit-тестов."""
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "id": "gen-abc123",
        "model": "openai/gpt-4o-mini",
        "choices": [
            {
                "message": {"role": "assistant", "content": "Электроника"},
                "finish_reason": "stop",
            }
        ],
    }
    client.post = AsyncMock(return_value=response)
    return client


@pytest.fixture
def openrouter_client(mock_http_client):
    """OpenRouterClient с замокированным HTTP."""
    client = OpenRouterClient(api_key="test-key")
    client._http = mock_http_client
    return client
```

### Мокирование

- **Unit-тесты:** мокировать `_http.post` — тестировать логику парсинга, обработки ошибок и retry.
- **Integration-тесты с реальным API:** пропускать при отсутствии `APP_OPENROUTER_API_KEY` через `pytest.mark.skipif`.
- Не мокировать `OpenRouterClient` целиком в тестах `MappingService` — использовать `FakeOpenRouterClient` с фиксированными ответами.

```python
from unittest.mock import AsyncMock, MagicMock
import pytest


class FakeOpenRouterClient:
    """Заменитель для тестов сервисов — возвращает заданный текст."""

    def __init__(self, fixed_response: str = "Электроника") -> None:
        self._fixed_response = fixed_response

    async def complete_chat(self, messages: list[dict], **kwargs) -> str:
        return self._fixed_response

    async def close(self) -> None:
        pass
```

### Паттерны тестов

```python
import pytest
from app.clients.openrouter_client import OpenRouterClient, OpenRouterRateLimitError
from unittest.mock import AsyncMock, MagicMock
import httpx


@pytest.mark.asyncio
async def test_complete_chat_returns_content(openrouter_client):
    """complete_chat возвращает текст из choices[0].message.content."""
    result = await openrouter_client.complete_chat(
        messages=[{"role": "user", "content": "Категория: iPhone 15"}],
        model="openai/gpt-4o-mini",
    )
    assert result == "Электроника"


@pytest.mark.asyncio
async def test_complete_chat_raises_rate_limit_error(openrouter_client, mock_http_client):
    """HTTP 429 преобразуется в OpenRouterRateLimitError."""
    error_response = MagicMock()
    error_response.status_code = 429
    error_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}
    http_error = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=error_response
    )
    error_response.raise_for_status.side_effect = http_error
    mock_http_client.post = AsyncMock(return_value=error_response)

    with pytest.raises(OpenRouterRateLimitError):
        from app.clients.openrouter_client import safe_complete_chat
        await safe_complete_chat(openrouter_client, [], "openai/gpt-4o-mini")
```

## Логирование

| Событие | Уровень | Пример сообщения |
|---------|---------|-----------------|
| Успешный запрос к LLM | DEBUG | `openrouter.request_ok model="openai/gpt-4o-mini" duration_ms=340` |
| Запрос отправлен | DEBUG | `openrouter.request_sent model="openai/gpt-4o-mini" messages=2` |
| Rate limit (429) | WARNING | `openrouter.rate_limit_retry attempt=1 wait=1s` |
| Таймаут | ERROR | `openrouter.timeout model="openai/gpt-4o-mini"` |
| HTTP-ошибка | ERROR | `openrouter.request_failed status=500 model="openai/gpt-4o-mini" error="Internal server error"` |
| Auth-ошибка (401/403) | ERROR | `openrouter.request_failed status=401 model="openai/gpt-4o-mini" error="Invalid API key"` |

```python
import logging
import time

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# Pydantic-модели ответа (определены на уровне модуля — не внутри функции)
class _ChatMessage(BaseModel):
    role: str
    content: str


class _ChatChoice(BaseModel):
    message: _ChatMessage
    finish_reason: str | None = None


class _ChatCompletionResponse(BaseModel):
    id: str
    choices: list[_ChatChoice]
    model: str


async def complete_chat_with_logging(
    http_client,  # httpx.AsyncClient
    base_url: str,
    payload: dict,
) -> str:
    """Отправить запрос с логированием времени выполнения."""
    model = payload.get("model", "unknown")
    messages = payload.get("messages", [])
    logger.debug(
        "openrouter.request_sent model=%s messages=%d", model, len(messages)
    )
    start = time.monotonic()
    response = await http_client.post(f"{base_url}/chat/completions", json=payload)
    response.raise_for_status()
    duration_ms = int((time.monotonic() - start) * 1000)
    logger.debug("openrouter.request_ok model=%s duration_ms=%d", model, duration_ms)
    data = _ChatCompletionResponse.model_validate(response.json())
    return data.choices[0].message.content
```
