# Stack

## Runtime and packaging

- Python `>=3.14`, packaged via `setuptools` from `pyproject.toml`.
- Single application package: `app/`.
- Local env is expected via `.venv/`; dependencies are installed with `pip install -e .[dev]`.
- Entry point for local run: `uvicorn app.main:app --reload`.

## Core backend stack

- FastAPI serves both JSON API and built-in static SPA from `app/main.py`.
- Pydantic v2 models live in `app/schemas.py` and are shared across routes, services, and clients.
- HTTP integrations use `httpx.AsyncClient` in `app/clients/wb.py` and `app/clients/ozon.py`.
- SQLite is used directly through `sqlite3` in `app/db.py`; there is no ORM and no migration tool.
- Security primitives come from `cryptography` (`Fernet`) plus stdlib hashing/HMAC in `app/security.py`.

## Main dependencies

- `fastapi>=0.116.0`
- `pydantic>=2.11.0`
- `httpx>=0.28.0`
- `cryptography>=45.0.0`
- `uvicorn[standard]>=0.35.0`
- Dev: `pytest>=8.4.0`

## Configuration model

- Environment loading is centralized in `app/config.py`.
- Main variables from `.env.example`:
  - `APP_SECRET_KEY`
  - `APP_DATABASE_PATH`
  - `APP_SESSION_TTL_HOURS`
  - `WB_BASE_URL`
  - `OZON_BASE_URL`
  - `HTTP_TIMEOUT_SECONDS`
- Defaults are development-friendly; notable fallback is `unsafe-local-development-secret`.

## Persistence and security

- SQLite file default path: `data/perenositsa.db`.
- DB schema is created at app startup by `Database.initialize()` in `app/db.py`.
- Passwords are hashed with PBKDF2-HMAC-SHA256 (`600_000` iterations).
- Marketplace credentials are encrypted before DB storage using `Fernet`, with a key derived from `APP_SECRET_KEY`.
- Sessions are stored server-side in SQLite and addressed by opaque bearer tokens.

## Frontend stack

- No separate frontend build toolchain.
- Static files are served from `app/static/`:
  - `app/static/index.html`
  - `app/static/app.js`
  - `app/static/app.css`
- The SPA depends on stable JSON contracts from `/api/v1/*`.

## Tooling and local workflow

- Tests run with `python -m pytest`.
- Lightweight verification script: `scripts/verify.ps1`.
- Repo also contains local Codex/GSD docs under `docs/codex/` and `docs/superpowers/`.

## Observed stack constraints

- No background job runner, queue, Redis, or task broker.
- No Alembic or schema migration history.
- No lint/format/typecheck commands are declared in `pyproject.toml`.
- No CI configuration was inspected in the repository root.
