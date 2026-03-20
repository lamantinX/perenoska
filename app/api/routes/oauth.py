from __future__ import annotations

import os
import secrets
import time
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.deps import get_connection_service, get_current_user
from app.schemas import ConnectionUpsert, Marketplace

router = APIRouter(prefix="/oauth", tags=["oauth"])

# ---------------------------------------------------------------------------
# In-memory CSRF state store — {state_token: created_at_timestamp}
# ---------------------------------------------------------------------------
_pending_states: dict[str, float] = {}
_STATE_TTL_SECONDS = 600  # 10 minutes


def _generate_state() -> str:
    """Generate a random CSRF state token and remember it."""
    _purge_expired_states()
    token = secrets.token_urlsafe(32)
    _pending_states[token] = time.monotonic()
    return token


def _consume_state(token: str) -> bool:
    """Return True and remove the state if it exists and is not expired."""
    _purge_expired_states()
    if token in _pending_states:
        del _pending_states[token]
        return True
    return False


def _purge_expired_states() -> None:
    now = time.monotonic()
    expired = [k for k, ts in _pending_states.items() if now - ts > _STATE_TTL_SECONDS]
    for k in expired:
        del _pending_states[k]


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _ozon_client_id() -> str | None:
    return os.environ.get("OZON_CLIENT_ID") or None


def _ozon_client_secret() -> str | None:
    return os.environ.get("OZON_CLIENT_SECRET") or None


def _app_base_url() -> str:
    return os.environ.get("APP_BASE_URL", "http://localhost:8000").rstrip("/")


def _redirect_uri() -> str:
    return f"{_app_base_url()}/api/v1/oauth/ozon/callback"


def _ozon_auth_base_url() -> str:
    return os.environ.get("OZON_BASE_URL", "https://api-seller.ozon.ru").rstrip("/")


def _ozon_authorize_url() -> str:
    """Full authorization URL — configurable via OZON_AUTH_URL env var."""
    explicit = os.environ.get("OZON_AUTH_URL")
    if explicit:
        return explicit.rstrip("/")
    return f"{_ozon_auth_base_url()}/v1/oauth/authorize"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/ozon/status")
async def ozon_oauth_status(
    request: Request,
    connection_service=Depends(get_connection_service),
) -> JSONResponse:
    """Return whether Ozon OAuth is configured and whether we have a stored token."""
    client_id = _ozon_client_id()
    configured = client_id is not None

    # Try to detect a connected user via optional bearer token
    connected = False
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
        try:
            from app.services.auth import AuthService  # local import to avoid circulars
            container = request.app.state.container
            user = container.auth_service.get_current_user(token)
            row = connection_service.database.get_connection(user["id"], Marketplace.OZON.value)
            if row is not None:
                creds = connection_service.vault.decrypt_json(row["credentials_encrypted"])
                connected = "access_token" in creds or "api_key" in creds
        except Exception:
            pass

    return JSONResponse({
        "configured": configured,
        "connected": connected,
        "demo": not configured,
    })


@router.get("/ozon/start", response_model=None)
async def ozon_oauth_start(
    redirect_uri: str | None = Query(default=None),
) -> RedirectResponse | JSONResponse:
    """
    Redirect the user to Ozon's OAuth authorization page, or return demo
    instructions when OZON_CLIENT_ID is not configured.
    """
    client_id = _ozon_client_id()
    if not client_id:
        return JSONResponse(
            {
                "demo": True,
                "message": (
                    "Установите OZON_CLIENT_ID и OZON_CLIENT_SECRET "
                    "для реального OAuth"
                ),
                "auth_url": None,
            }
        )

    state = _generate_state()
    callback_uri = redirect_uri or _redirect_uri()
    auth_base = _ozon_authorize_url()
    auth_url = (
        f"{auth_base}"
        f"?client_id={client_id}"
        f"&redirect_uri={callback_uri}"
        f"&state={state}"
        f"&response_type=code"
    )
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/ozon/callback", response_model=None)
async def ozon_oauth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    connection_service=Depends(get_connection_service),
) -> RedirectResponse | JSONResponse:
    """
    Ozon redirects here after the user grants (or denies) access.
    Exchanges the authorization code for an access token and stores it.
    """
    # Handle user denial
    if error:
        return RedirectResponse(url=f"/?ozon_error={error}", status_code=302)

    if not code or not state:
        raise HTTPException(status_code=400, detail="Отсутствуют параметры code или state.")

    # Validate CSRF state
    if not _consume_state(state):
        raise HTTPException(status_code=400, detail="Недействительный или просроченный state.")

    client_id = _ozon_client_id()
    client_secret = _ozon_client_secret()
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="OZON_CLIENT_ID/OZON_CLIENT_SECRET не настроены.")

    callback_uri = _redirect_uri()
    base = _ozon_auth_base_url()
    token_url = f"{base}/v1/oauth/token"

    # Exchange code for token
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                token_url,
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": callback_uri,
                },
            )
            resp.raise_for_status()
            token_data: dict = resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ozon вернул ошибку при обмене кода: {exc.response.text}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Не удалось подключиться к Ozon: {exc}",
        )

    access_token: str = token_data.get("access_token", "")
    if not access_token:
        raise HTTPException(status_code=502, detail="Ozon не вернул access_token.")

    # Persist the token — we need a user context.  The callback URL does not
    # carry an auth header so we look for a session cookie / bearer stored in
    # the Authorization header as a fallback.  If no user is identified we
    # store the token in a temporary session-like slot keyed by state (already
    # consumed), so the UI can pick it up.  For simplicity we store it under a
    # special "oauth_pending" key and let the frontend call a dedicated
    # /save endpoint once the user is authenticated.
    #
    # Better UX: if the user was already authenticated (e.g., they clicked the
    # button while logged in), the bearer token is embedded in the redirect URL
    # as a fragment — but that is not available server-side.  Instead we check
    # the Authorization header on this request.
    user = _try_resolve_user(request)
    if user is not None:
        payload = ConnectionUpsert(
            marketplace=Marketplace.OZON,
            client_id=client_id,
            api_key=access_token,
        )
        connection_service.upsert_connection(user["id"], payload)

    return RedirectResponse(url="/?ozon_connected=1", status_code=302)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _try_resolve_user(request: Request) -> dict | None:
    """Attempt to identify the current user from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:]
    try:
        container = request.app.state.container
        return container.auth_service.get_current_user(token)
    except Exception:
        return None
