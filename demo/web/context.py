from __future__ import annotations

from pathlib import Path
from secrets import compare_digest, token_urlsafe
from time import time
from typing import Any
from urllib.parse import urlencode

from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..core.chat_state import ConversationState
from ..core.config import load_auth_config, load_business_config


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "data" / "negocio.json"
DB_PATH = BASE_DIR / "data" / "negocio.db"
templates = Jinja2Templates(directory=BASE_DIR / "templates")

conversations: dict[str, ConversationState] = {}
CONVERSATION_IDLE_SECONDS = 30 * 60
ROLE_LEVELS = {
    "staff": 1,
    "admin": 2,
}


def get_or_create_csrf_token(request: Request) -> str:
    session = request.scope.get("session", {})
    token = str(session.get("csrf_token") or "").strip()
    if not token:
        token = token_urlsafe(32)
        session["csrf_token"] = token
    return token


def has_valid_csrf_token(request: Request, submitted_token: str | None) -> bool:
    token = str(submitted_token or "").strip()
    if not token:
        return False
    expected_token = get_or_create_csrf_token(request)
    return compare_digest(token, expected_token)


def csrf_error_response() -> HTMLResponse:
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="es">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Formulario no válido</title>
          </head>
          <body style="font-family: Inter, system-ui, sans-serif; background:#fcf7f3; color:#342833; padding:32px;">
            <main style="max-width:520px; margin:0 auto; background:#fffdfa; border:1px solid #e9d9dc; border-radius:8px; padding:24px;">
              <h1 style="margin:0 0 10px; font-size:28px;">No he podido validar el formulario</h1>
              <p style="margin:0; line-height:1.5;">Recarga la página e inténtalo de nuevo. Si estabas editando algo, vuelve a abrir el formulario antes de guardar.</p>
            </main>
          </body>
        </html>
        """,
        status_code=403,
    )


def csrf_failed(request: Request, token: str | None) -> HTMLResponse | None:
    if has_valid_csrf_token(request, token):
        return None
    return csrf_error_response()


templates.env.globals["csrf_token"] = get_or_create_csrf_token


def get_business() -> dict:
    return load_business_config(CONFIG_PATH, DB_PATH)


def get_auth_settings() -> dict[str, Any]:
    return load_auth_config(CONFIG_PATH, DB_PATH)


def is_authenticated(request: Request) -> bool:
    session = request.scope.get("session", {})
    return bool(session.get("is_authenticated"))


def get_authenticated_user(request: Request) -> str:
    session = request.scope.get("session", {})
    return str(session.get("auth_user") or "")


def get_authenticated_role(request: Request) -> str:
    session = request.scope.get("session", {})
    return str(session.get("auth_role") or "")


def has_required_role(current_role: str, required_role: str) -> bool:
    return ROLE_LEVELS.get(current_role, 0) >= ROLE_LEVELS.get(required_role, 0)


def normalize_next_path(raw_path: str | None, default: str = "/agenda") -> str:
    if not raw_path:
        return default
    if not raw_path.startswith("/") or raw_path.startswith("//"):
        return default
    if raw_path.startswith("/login"):
        return default
    return raw_path


def request_target(request: Request) -> str:
    query = request.url.query
    if query:
        return f"{request.url.path}?{query}"
    return request.url.path


def login_redirect_response(next_path: str) -> RedirectResponse:
    target = normalize_next_path(next_path)
    return RedirectResponse(f"/login?{urlencode({'next': target})}", status_code=303)


def require_panel_access(request: Request, role: str = "staff") -> RedirectResponse | None:
    if not is_authenticated(request):
        return login_redirect_response(request_target(request))
    if not has_required_role(get_authenticated_role(request), role):
        return RedirectResponse("/agenda?forbidden=1", status_code=303)
    return None


def require_admin_access(request: Request) -> RedirectResponse | None:
    return require_panel_access(request, role="admin")


def prune_conversations(now_ts: float | None = None) -> None:
    reference = now_ts if now_ts is not None else time()
    expired = [
        session_id
        for session_id, state in conversations.items()
        if reference - getattr(state, "last_seen_at", 0) > CONVERSATION_IDLE_SECONDS
    ]
    for session_id in expired:
        conversations.pop(session_id, None)


def get_chat_state(session_id: str) -> ConversationState:
    now_ts = time()
    prune_conversations(now_ts)
    state = conversations.get(session_id)
    if not state:
        state = ConversationState()
        conversations[session_id] = state
    state.last_seen_at = now_ts
    return state
