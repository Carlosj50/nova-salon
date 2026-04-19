from __future__ import annotations

from secrets import compare_digest
from time import time
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..core.bot_logic import handle_message
from ..core.channels import get_channel
from . import context as web_context
from . import view_helpers


router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    channel: str | None = None
    incoming_phone: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    appointment_created: bool = False


@router.get("/login", response_class=HTMLResponse, response_model=None)
def login_page(request: Request, next: str | None = None, logged_out: int = 0) -> HTMLResponse | RedirectResponse:
    next_path = web_context.normalize_next_path(next)
    if web_context.is_authenticated(request):
        return RedirectResponse(next_path, status_code=303)

    return web_context.templates.TemplateResponse(
        request,
        "login.html",
        view_helpers.login_form_context(
            request,
            business=web_context.get_business(),
            next_path=next_path,
            logged_out=bool(logged_out),
        ),
    )


@router.post("/login", response_class=HTMLResponse, response_model=None)
async def login_submit(request: Request) -> HTMLResponse | RedirectResponse:
    data = await view_helpers.read_form_data(request)
    if invalid := web_context.csrf_failed(request, data.get("csrf_token")):
        return invalid
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    next_path = web_context.normalize_next_path(data.get("next"))
    auth_settings = web_context.get_auth_settings()

    if compare_digest(username, auth_settings["admin_username"]) and compare_digest(password, auth_settings["admin_password"]):
        request.session.clear()
        request.session["is_authenticated"] = True
        request.session["auth_user"] = auth_settings["admin_username"]
        request.session["auth_at"] = int(time())
        return RedirectResponse(next_path, status_code=303)

    return web_context.templates.TemplateResponse(
        request,
        "login.html",
        view_helpers.login_form_context(
            request,
            business=web_context.get_business(),
            next_path=next_path,
            error="No he podido entrar con esos datos. Revisa usuario y contraseña.",
        ),
        status_code=400,
    )


@router.get("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/login?logged_out=1", status_code=303)


@router.get("/", response_class=HTMLResponse)
def chat_page(request: Request) -> HTMLResponse:
    return web_context.templates.TemplateResponse(
        request,
        "chat.html",
        {
            "business": web_context.get_business(),
            "whatsapp_channel": get_channel(web_context.DB_PATH, "whatsapp"),
            "active_page": "chat",
        },
    )


@router.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> dict:
    session_id = payload.session_id or str(uuid4())
    state = web_context.get_chat_state(session_id)
    business = web_context.get_business()
    result = handle_message(
        payload.message,
        business,
        state,
        web_context.DB_PATH,
        channel_type=payload.channel,
        incoming_phone=payload.incoming_phone,
    )
    state.last_seen_at = time()
    return {
        "session_id": session_id,
        "reply": result["reply"],
        "intent": result["intent"],
        "appointment_created": result.get("appointment_created", False),
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
