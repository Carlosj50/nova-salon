from __future__ import annotations

from pathlib import Path
from time import time
from typing import Any
from urllib.parse import urlencode

from fastapi.templating import Jinja2Templates
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
INTERNAL_PATH_PREFIXES = (
    "/agenda",
    "/clientes",
    "/citas",
    "/servicios",
    "/personal",
    "/config",
)
PUBLIC_PATHS = {"/", "/login", "/logout", "/api/chat", "/health"}


def get_business() -> dict:
    return load_business_config(CONFIG_PATH, DB_PATH)


def get_auth_settings() -> dict[str, str]:
    return load_auth_config(CONFIG_PATH)


def is_authenticated(request: Request) -> bool:
    session = request.scope.get("session", {})
    return bool(session.get("is_authenticated"))


def get_authenticated_user(request: Request) -> str:
    session = request.scope.get("session", {})
    return str(session.get("auth_user") or "")


def is_internal_path(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in INTERNAL_PATH_PREFIXES)


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


def require_admin_access(request: Request) -> RedirectResponse | None:
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/static/"):
        return None
    if is_internal_path(path) and not is_authenticated(request):
        return login_redirect_response(request_target(request))
    return None


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
