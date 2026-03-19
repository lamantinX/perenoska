# Workflow

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
Copy-Item .env.example .env
```

## Run

```powershell
uvicorn app.main:app --reload
```

UI: `http://127.0.0.1:8000/`  
Swagger: `http://127.0.0.1:8000/docs`

## Tests

```powershell
python -m pytest
```

Или единый локальный прогон:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

## Safe edit flow

1. Прочитать `AGENTS.md` и релевантные файлы из `docs/codex/`.
2. Найти затрагиваемые сервисы, роуты и тесты.
3. Если меняется поведение, сначала обновить тест.
4. Внести минимальные правки.
5. Прогнать `python -m pytest`.
6. Прогнать `scripts/verify.ps1`.
7. Проверить `git status --short --branch`.

## Git

Локальный `origin` должен быть:

```text
https://github.com/lamantinX/perenoska
```

Проверка:

```powershell
git remote -v
```

Обновление при необходимости:

```powershell
git remote set-url origin https://github.com/lamantinX/perenoska
```
