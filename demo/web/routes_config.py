from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..core.channels import CHANNEL_MODES, default_channel, get_channel, list_channels, upsert_channel
from ..core.config import upsert_business_overrides
from ..core.repositories import is_valid_phone, list_services_config, list_staff_members
from . import context as web_context
from . import view_helpers


router = APIRouter()

MEDIA_DIR = web_context.BASE_DIR / "data" / "uploads"
BRANDING_DIR = MEDIA_DIR / "branding"
BRANDING_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_LOGO_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}
MAX_LOGO_BYTES = 5 * 1024 * 1024


def is_logo_upload(value: Any) -> bool:
    return isinstance(value, UploadFile) and bool((value.filename or "").strip())


def remove_branding_logo(logo_path: str | None) -> None:
    if not logo_path or not logo_path.startswith("/media/branding/"):
        return
    logo_file = BRANDING_DIR / Path(logo_path).name
    if logo_file.exists():
        logo_file.unlink()


async def save_branding_logo(upload: UploadFile, existing_logo_path: str | None = None) -> tuple[str | None, str | None]:
    filename = Path(upload.filename or "").name
    extension = Path(filename).suffix.lower()
    content_type = str(upload.content_type or "").lower()
    try:
        if extension not in ALLOWED_LOGO_EXTENSIONS:
            return None, "El logo debe ser PNG, JPG/JPEG o WEBP."
        if content_type and content_type not in ALLOWED_LOGO_CONTENT_TYPES:
            return None, "No he podido aceptar ese tipo de imagen. Usa PNG, JPG/JPEG o WEBP."

        content = await upload.read()
        if not content:
            return None, "No he podido leer el logo que has subido."
        if len(content) > MAX_LOGO_BYTES:
            return None, "El logo es demasiado grande. Usa una imagen de hasta 5 MB."

        stored_name = f"logo-{uuid4().hex}{extension}"
        target = BRANDING_DIR / stored_name
        target.write_bytes(content)
        remove_branding_logo(existing_logo_path)
        return f"/media/branding/{stored_name}", None
    finally:
        await upload.close()


@router.get("/config", response_class=HTMLResponse)
def config_hub_page(request: Request) -> HTMLResponse:
    if redirect := web_context.require_admin_access(request):
        return redirect
    business = web_context.get_business()
    services = list_services_config(web_context.DB_PATH)
    staff_members = list_staff_members(web_context.DB_PATH)
    return web_context.templates.TemplateResponse(
        request,
        "canales.html",
        {
            "business": business,
            "channels": list_channels(web_context.DB_PATH),
            "whatsapp_channel": get_channel(web_context.DB_PATH, "whatsapp") or default_channel("whatsapp"),
            "config_summary": {
                "services_total": len(services),
                "services_active": sum(1 for service in services if service.get("active", True)),
                "staff_total": len(staff_members),
                "staff_active": sum(1 for member in staff_members if member.get("active", True)),
            },
            "active_page": "config",
            "config_section": "hub",
        },
    )


@router.get("/config/canales", response_class=HTMLResponse)
def channel_config_page(request: Request) -> RedirectResponse:
    if redirect := web_context.require_admin_access(request):
        return redirect
    return RedirectResponse("/config", status_code=303)


@router.get("/config/negocio", response_class=HTMLResponse)
def business_config_page(request: Request, saved: int = 0) -> HTMLResponse:
    if redirect := web_context.require_admin_access(request):
        return redirect

    business = web_context.get_business()
    form_data = {
        "name": business.get("name", ""),
        "sector": business.get("sector", ""),
        "phone": business.get("phone", ""),
        "address": business.get("address", ""),
        "logo_path": business.get("logo_path", ""),
        "hours_summary": business.get("hours", {}).get("summary", ""),
        "hours_monday_friday": business.get("hours", {}).get("monday_friday", ""),
        "hours_saturday": business.get("hours", {}).get("saturday", ""),
        "hours_sunday": business.get("hours", {}).get("sunday", ""),
        "welcome_message": business.get("messages", {}).get("welcome", ""),
        "fallback_message": business.get("messages", {}).get("fallback", ""),
    }

    return web_context.templates.TemplateResponse(
        request,
        "config_negocio.html",
        view_helpers.business_form_context(
            request,
            business=business,
            form_data=form_data,
            form_action="/config/negocio",
            page_title="Datos del negocio",
            page_subtitle="Lo básico del salón para no tener que tocar archivos en cambios normales.",
            submit_label="Guardar negocio",
            saved=bool(saved),
        ),
    )


@router.post("/config/negocio", response_class=HTMLResponse, response_model=None)
async def save_business_config_page(request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := web_context.require_admin_access(request):
        return redirect

    business = web_context.get_business()
    logo_upload: UploadFile | None = None
    content_type = str(request.headers.get("content-type") or "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        data = {key: str(form.get(key) or "") for key in form.keys() if key != "logo_file"}
        if invalid := web_context.csrf_failed(request, data.get("csrf_token")):
            return invalid
        if is_logo_upload(form.get("logo_file")):
            logo_upload = form.get("logo_file")
    else:
        data = await view_helpers.read_form_data(request)
        if invalid := web_context.csrf_failed(request, data.get("csrf_token")):
            return invalid
    form_data = {
        "name": (data.get("name") or "").strip(),
        "sector": (data.get("sector") or "").strip(),
        "phone": (data.get("phone") or "").strip(),
        "address": (data.get("address") or "").strip(),
        "logo_path": str(business.get("logo_path") or ""),
        "remove_logo": str(data.get("remove_logo") or "").strip(),
        "hours_summary": (data.get("hours_summary") or "").strip(),
        "hours_monday_friday": (data.get("hours_monday_friday") or "").strip(),
        "hours_saturday": (data.get("hours_saturday") or "").strip(),
        "hours_sunday": (data.get("hours_sunday") or "").strip(),
        "welcome_message": (data.get("welcome_message") or "").strip(),
        "fallback_message": (data.get("fallback_message") or "").strip(),
    }

    def config_response(error: str, status_code: int = 400) -> HTMLResponse:
        preview_business = dict(business)
        preview_business.update(
            {
                "name": form_data["name"] or business.get("name", ""),
                "sector": form_data["sector"] or business.get("sector", ""),
                "phone": form_data["phone"] or business.get("phone", ""),
                "address": form_data["address"] or business.get("address", ""),
                "logo_path": form_data["logo_path"] or business.get("logo_path", ""),
                "hours": {
                    **dict(business.get("hours", {})),
                    "summary": form_data["hours_summary"] or business.get("hours", {}).get("summary", ""),
                    "monday_friday": form_data["hours_monday_friday"] or business.get("hours", {}).get("monday_friday", ""),
                    "saturday": form_data["hours_saturday"] or business.get("hours", {}).get("saturday", ""),
                    "sunday": form_data["hours_sunday"] or business.get("hours", {}).get("sunday", ""),
                },
                "messages": {
                    **dict(business.get("messages", {})),
                    "welcome": form_data["welcome_message"] or business.get("messages", {}).get("welcome", ""),
                    "fallback": form_data["fallback_message"] or business.get("messages", {}).get("fallback", ""),
                },
            }
        )
        return web_context.templates.TemplateResponse(
            request,
            "config_negocio.html",
            view_helpers.business_form_context(
                request,
                business=preview_business,
                form_data=form_data,
                form_action="/config/negocio",
                page_title="Datos del negocio",
                page_subtitle="Lo básico del salón para no tener que tocar archivos en cambios normales.",
                submit_label="Guardar negocio",
                error=error,
            ),
            status_code=status_code,
        )

    if not form_data["name"]:
        return config_response("Necesito un nombre para guardar la ficha del negocio.")
    if not form_data["phone"]:
        return config_response("Indica un teléfono principal del negocio.")
    if not is_valid_phone(form_data["phone"]):
        return config_response("Indica un teléfono válido. Puedes escribirlo con espacios o +34 y lo normalizo al guardar.")
    if not form_data["address"]:
        return config_response("Indica una dirección o referencia clara para el negocio.")
    if not form_data["hours_summary"]:
        return config_response("Añade un resumen corto de horarios para que el chat lo pueda mostrar bien.")

    for field_name, raw_value in (
        ("lunes a viernes", form_data["hours_monday_friday"]),
        ("sábado", form_data["hours_saturday"]),
        ("domingo", form_data["hours_sunday"]),
    ):
        if not raw_value:
            return config_response(f"Indica el horario de {field_name} o escribe 'cerrado'.")
        if not view_helpers.is_valid_business_schedule(raw_value):
            return config_response(
                f"El horario de {field_name} debe ir como 09:30-19:30 o como 'cerrado'."
            )

    if not form_data["welcome_message"]:
        return config_response("Deja al menos un saludo base para el chat.")
    if not form_data["fallback_message"]:
        return config_response("Deja un mensaje base para cuando el chat no entienda algo.")

    logo_path = str(business.get("logo_path") or "")
    if form_data["remove_logo"] in {"1", "on", "true", "sí", "si"}:
        remove_branding_logo(logo_path)
        logo_path = ""
    if logo_upload:
        uploaded_logo_path, logo_error = await save_branding_logo(logo_upload, logo_path)
        if logo_error:
            return config_response(logo_error)
        logo_path = uploaded_logo_path or ""

    upsert_business_overrides(
        web_context.DB_PATH,
        {
            "name": form_data["name"],
            "sector": form_data["sector"],
            "phone": form_data["phone"],
            "address": form_data["address"],
            "logo_path": logo_path,
            "hours": {
                "summary": form_data["hours_summary"],
                "monday_friday": form_data["hours_monday_friday"],
                "saturday": form_data["hours_saturday"],
                "sunday": form_data["hours_sunday"],
            },
            "messages": {
                "welcome": form_data["welcome_message"],
                "fallback": form_data["fallback_message"],
            },
        },
        timezone=business.get("timezone", "Atlantic/Canary"),
    )
    return RedirectResponse("/config/negocio?saved=1", status_code=303)


@router.get("/config/canales/whatsapp", response_class=HTMLResponse)
def whatsapp_config_page(request: Request, saved: int = 0) -> HTMLResponse:
    if redirect := web_context.require_admin_access(request):
        return redirect
    return web_context.templates.TemplateResponse(
        request,
        "canal_whatsapp.html",
        {
            "business": web_context.get_business(),
            "channel": get_channel(web_context.DB_PATH, "whatsapp") or default_channel("whatsapp"),
            "modes": CHANNEL_MODES,
            "saved": bool(saved),
            "active_page": "config",
            "config_section": "whatsapp",
        },
    )


@router.post("/config/canales/whatsapp", response_model=None)
async def save_whatsapp_config(request: Request) -> RedirectResponse | HTMLResponse:
    if redirect := web_context.require_admin_access(request):
        return redirect
    data = await view_helpers.read_form_data(request)
    if invalid := web_context.csrf_failed(request, data.get("csrf_token")):
        return invalid
    business = web_context.get_business()
    upsert_channel(
        web_context.DB_PATH,
        channel_type="whatsapp",
        active=data.get("activo") == "on",
        mode=data.get("modo", "demo"),
        phone=data.get("telefono"),
        display_name=data.get("nombre_visible"),
        config_json=data.get("config_json"),
        timezone=business.get("timezone", "Atlantic/Canary"),
    )
    return RedirectResponse("/config/canales/whatsapp?saved=1", status_code=303)
