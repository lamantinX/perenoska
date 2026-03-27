---
description: Стандарт кодирования Python — конвенции именования, паттерны, типизация, антипаттерны.
standard: specs/.instructions/docs/technology/standard-technology.md
technology: python
---

# Стандарт Python v1.0

## Версия и настройка

| Параметр | Значение |
|----------|----------|
| Версия | Python 3.11 |
| Ключевые библиотеки | pydantic 2.10 (валидация/сериализация), ruff 0.8 (линтер+форматтер), pytest 8.x (тесты) |
| Конфигурация | `pyproject.toml` — секции `[tool.ruff]`, `[tool.pytest.ini_options]`, `[project]` |

## Конвенции именования

| Объект | Конвенция | Пример |
|--------|----------|--------|
| Модуль (файл) | snake_case | `auth_service.py`, `marketplace_client.py` |
| Пакет (директория) | snake_case | `app/clients/`, `app/services/` |
| Класс | PascalCase | `AuthService`, `MarketplaceClient` |
| Исключение | PascalCase + `Error` | `NotFoundError`, `ValidationError` |
| Функция / метод | snake_case, глагол + сущ. | `create_user`, `get_transfer_status` |
| Переменная | snake_case | `user_id`, `transfer_job` |
| Константа | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TTL_HOURS` |
| Приватный атрибут | `_` префикс | `_session`, `_client` |
| Параметр типа (TypeVar) | PascalCase + `T` | `ItemT`, `ModelT` |
| Файл тестов | `test_` префикс | `test_auth_service.py` |
| Тестовая функция | `test_` префикс | `test_register_returns_201` |

## Паттерны кода

### Типизация функций и переменных

Все публичные функции и методы ОБЯЗАТЕЛЬНО типизированы. `from __future__ import annotations` не используется — современный синтаксис Union доступен через `X | Y`.

```python
from uuid import UUID


def get_user_by_id(user_id: UUID) -> dict | None:
    """Вернуть пользователя по ID или None если не найден."""
    # ...
    return None


def create_transfer(source: str, target: str, item_ids: list[str]) -> dict:
    """Создать задание на перенос товаров."""
    job: dict = {"source": source, "target": target, "items": item_ids}
    return job
```

### Классы с `__slots__` и датаклассы

Для data-контейнеров использовать `dataclass` или Pydantic `BaseModel`. Для сервисных классов — обычные классы с явной типизацией атрибутов.

```python
from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class TransferJob:
    id: UUID
    source_marketplace: str
    target_marketplace: str
    status: str = "pending"
    item_ids: list[str] = field(default_factory=list)

    def is_complete(self) -> bool:
        return self.status in ("completed", "failed")
```

### Обработка исключений

Создавать собственные исключения от `Exception`. Всегда логировать с контекстом. Никогда не глотать исключения молча.

```python
import logging

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    """Ресурс не найден."""


class ExternalAPIError(Exception):
    """Ошибка внешнего API."""

    def __init__(self, service: str, status_code: int, detail: str) -> None:
        self.service = service
        self.status_code = status_code
        super().__init__(f"{service} returned {status_code}: {detail}")


def fetch_product(product_id: str) -> dict:
    """Получить товар; выбросить NotFoundError если нет."""
    try:
        # ... обращение к API
        result: dict = {}
        return result
    except KeyError as exc:
        logger.warning("product_not_found product_id=%s", product_id)
        raise NotFoundError(f"Product {product_id} not found") from exc
```

### Контекстные менеджеры для ресурсов

Все ресурсы (файлы, соединения, клиенты) открывать через `with` / `async with`.

```python
import sqlite3
from pathlib import Path


def read_jobs(db_path: Path) -> list[dict]:
    """Читать задания из SQLite через контекстный менеджер."""
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM transfer_jobs WHERE status = ?", ("pending",))
        return [dict(row) for row in cursor.fetchall()]
```

### Конфигурация через переменные окружения

Все настройки через `os.environ` с явными дефолтами. Для сложных конфигов — Pydantic `BaseSettings`.

```python
import os
from pathlib import Path


class Settings:
    """Конфигурация приложения из переменных окружения."""

    def __init__(self) -> None:
        self.secret_key: str = os.environ.get("APP_SECRET_KEY", "change-me-in-production")
        self.database_path: Path = Path(os.environ.get("APP_DATABASE_PATH", "data/app.db"))
        self.session_ttl_hours: int = int(os.environ.get("APP_SESSION_TTL_HOURS", "24"))

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
```

### Логирование

Каждый модуль объявляет свой logger через `__name__`. Никаких `print()` в продакшн-коде.

```python
import logging

logger = logging.getLogger(__name__)


def process_transfer(job_id: str) -> None:
    logger.info("transfer_started job_id=%s", job_id)
    try:
        # ... обработка
        logger.info("transfer_completed job_id=%s", job_id)
    except Exception as exc:
        logger.error("transfer_failed job_id=%s error=%s", job_id, exc)
        raise
```

## Антипаттерны

| Антипаттерн | Почему плохо | Правильно |
|-------------|-------------|-----------|
| Мутабельный default-аргумент `def f(items=[])` | При каждом вызове без аргумента используется один и тот же список — runtime-баг со случайными данными | `def f(items: list \| None = None): items = items or []` |
| `except Exception: pass` | Скрывает ошибки, приложение молча ломается | Логировать и повторно выбрасывать: `logger.error(...); raise` |
| `import *` | Засоряет namespace, ломает статический анализ и автодополнение | Явный импорт: `from app.models import User, Product` |
| `print()` в production-коде | Не попадает в structured logs, нет уровней, нет контекста | `logger.info(...)` |
| `type(x) == SomeClass` | Не работает с наследованием | `isinstance(x, SomeClass)` |
| `os.system(cmd)` / `subprocess.call(cmd, shell=True)` | Shell injection, непредсказуемое поведение | `subprocess.run([cmd, arg1], check=True)` |
| Голые строки вместо Path | `"/some" + "/" + "path"` — платформо-зависимо, ошибки в разделителях | `Path("/some") / "path"` |
| Глобальные переменные-состояние | Трудно тестировать, race conditions | Инкапсулировать в класс или передавать явно |

## Структура файлов

```
app/
├── main.py                 # Точка входа, фабрика приложения create_app()
├── config.py               # Settings: переменные окружения
├── db.py                   # Database: инициализация SQLite
├── security.py             # CredentialVault, PasswordManager
├── api/
│   ├── deps.py             # FastAPI Depends-функции (get_container, get_current_user)
│   └── v1/
│       └── {domain}.py     # Роутер по домену (auth.py, transfers.py)
├── clients/
│   ├── base.py             # MarketplaceClient ABC
│   ├── wb.py               # WBClient
│   └── ozon.py             # OzonClient
└── services/
    ├── container.py        # ServiceContainer (DI-корень)
    ├── auth.py             # AuthService
    └── {domain}.py         # Остальные сервисы

tests/
├── conftest.py             # Фикстуры (app, client, tmp_db)
└── test_{domain}.py        # Тесты по доменам
```

## Валидация

*Скрипт валидации кода не создан. Валидация выполняется вручную по чек-листу из [validation-technology.md](../../.instructions/docs/technology/validation-technology.md).*

Линтинг и форматирование через ruff:

```bash
# Линтинг
ruff check app/ tests/

# Форматирование (проверка)
ruff format --check app/ tests/

# Авто-форматирование
ruff format app/ tests/
```

## Тестирование

### Фреймворк и плагины

| Компонент | Пакет | Назначение |
|-----------|-------|-----------|
| Фреймворк | `pytest 8.x` | Основной test runner |
| HTTP-клиент | `httpx` + `TestClient` (fastapi) | Тесты endpoint'ов |
| Coverage | `pytest-cov` | Покрытие кода |

### Фикстуры

Фикстуры используют `tmp_path` pytest для изолированной БД. Приложение создаётся через `create_app(settings)`.

```python
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from app.main import create_app
from app.config import Settings


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    """Settings с базой данных во временной директории."""
    return Settings(
        secret_key="test-secret-key-32-bytes-minimum!",
        database_path=tmp_path / "test.db",
        session_ttl_hours=1,
    )


@pytest.fixture
def app(tmp_settings: Settings):
    """FastAPI приложение с тестовыми настройками."""
    return create_app(tmp_settings)


@pytest.fixture
def client(app) -> TestClient:
    """HTTP-клиент для тестов."""
    return TestClient(app)
```

### Мокирование

- **Unit-тесты:** мокировать внешние зависимости (`unittest.mock.patch`, `MagicMock`).
- **Integration-тесты:** использовать реальное приложение с `tmp_path` для БД.
- **Внешние API:** регистрировать фейк через `container.client_factory.register_override()`.

```python
from unittest.mock import MagicMock, patch


class FakeMarketplaceClient:
    """Фейк маркетплейс-клиент для тестов."""

    async def get_products(self, limit: int = 50) -> list[dict]:
        return [{"id": "test-1", "name": "Test Product", "price": 100}]

    async def create_products(self, products: list[dict]) -> dict:
        return {"task_id": "fake-task-123", "status": "queued"}

    async def get_import_status(self, task_id: str) -> dict:
        return {"status": "completed", "success_count": 1, "fail_count": 0}
```

### Паттерны тестов

```python
import pytest
from fastapi.testclient import TestClient


def test_register_and_login(client: TestClient) -> None:
    """Регистрация нового пользователя и получение токена."""
    # Регистрация
    resp = client.post("/api/v1/auth/register", json={"email": "user@test.com", "password": "Pass1234!"})
    assert resp.status_code == 201

    # Логин
    resp = client.post("/api/v1/auth/login", json={"email": "user@test.com", "password": "Pass1234!"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    assert token


def test_unauthorized_without_token(client: TestClient) -> None:
    """Запрос без токена возвращает 401."""
    resp = client.get("/api/v1/transfers")
    assert resp.status_code == 401
```

## Логирование

| Событие | Уровень | Пример сообщения |
|---------|---------|-----------------|
| Запуск приложения | INFO | `app.startup version="1.0.0" env="production"` |
| Создание ресурса | INFO | `transfer.created job_id="abc-123" source="wb" target="ozon"` |
| Валидационная ошибка | WARNING | `auth.invalid_credentials email="user@test.com"` |
| Ошибка внешнего API | ERROR | `wb_client.request_failed status=503 retries=3` |
| Необработанное исключение | ERROR | `unhandled_exception path="/api/v1/transfers" error="..."` |
| Медленная операция | WARNING | `transfer.slow_operation job_id="abc" duration_ms=3200` |

```python
import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Настройка логирования для приложения."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Снизить шум от внешних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```
