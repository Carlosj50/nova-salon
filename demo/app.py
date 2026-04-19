from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import quote_plus

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

from .core.appointment_service import (
    AppointmentServiceError,
    create_customer_appointment,
    update_customer_appointment,
)
from .core.db import init_db
from .core.models import APPOINTMENT_STATES
from .core.repositories import (
    create_service_config,
    create_staff_member,
    find_customer_by_phone,
    get_appointment,
    get_customer,
    get_service_config,
    get_staff_member,
    is_valid_phone,
    list_staff_members,
    list_appointments,
    list_customer_appointments,
    list_customers,
    list_services_config,
    set_service_active,
    set_staff_active,
    update_category_capacities,
    update_appointment_status,
    update_customer,
    update_service_config,
    update_staff_member,
)
from .web.context import (
    BASE_DIR,
    DB_PATH,
    get_auth_settings,
    get_business,
    require_admin_access,
    csrf_failed,
    templates,
)
from .web.routes_config import router as config_router
from .web.routes_public import router as public_router
from .web.view_helpers import (
    AGENDA_FILTERS,
    MANUAL_APPOINTMENT_STATES,
    agenda_filter_links,
    agenda_view_links,
    appointment_summary,
    apply_agenda_filter,
    build_agenda_operational_focus,
    build_agenda_url,
    build_month_overview,
    build_quick_reschedule_actions,
    build_visual_planner,
    business_today,
    customer_form_context,
    format_date_label,
    manual_appointment_context,
    normalize_return_to,
    parse_optional_date,
    prepare_appointments,
    prepare_categories,
    prepare_customer,
    prepare_customers,
    prepare_service_records,
    prepare_staff_records,
    build_repeat_context,
    read_form_data,
    read_form_lists,
    redirect_with_saved,
    redirect_with_updated,
    resolve_month_anchor,
    service_catalog_options,
    service_category_options,
    service_form_context,
    service_id_for_name,
    service_map,
    sort_agenda_appointments,
    staff_form_context,
)

app = FastAPI(title="Demo de atención automatizada")
auth_config = get_auth_settings()
app.add_middleware(
    SessionMiddleware,
    secret_key=auth_config["session_secret"],
    session_cookie=auth_config["session_cookie"],
    same_site="lax",
    max_age=60 * 60 * 10,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
MEDIA_DIR = BASE_DIR / "data" / "uploads"
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
init_db(DB_PATH)

app.include_router(public_router)
app.include_router(config_router)


@app.get("/agenda", response_class=HTMLResponse)
def agenda_page(
    request: Request,
    filtro: str = "todas",
    fecha: str | None = None,
    mes: str | None = None,
    saved: int = 0,
    moved: int = 0,
    error_move: str | None = None,
) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    appointments = prepare_appointments(sort_agenda_appointments(list_appointments(DB_PATH), business_today(business)))
    today = business_today(business)
    active_filter = filtro if filtro in {value for value, _ in AGENDA_FILTERS} else "todas"
    filtered_appointments = apply_agenda_filter(appointments, active_filter, today)
    selected_date = parse_optional_date(fecha)
    fallback_day = selected_date or date.fromisoformat(today)
    month_anchor = resolve_month_anchor(mes, fallback_day)
    month_token = month_anchor.strftime("%Y-%m")
    focus_date = selected_date.isoformat() if selected_date else None
    visible_appointments = [
        item for item in filtered_appointments if not focus_date or item.get("fecha") == focus_date
    ]
    current_path = build_agenda_url(
        filtro=active_filter,
        selected_date=focus_date,
        month_token=month_token,
    )
    for appointment in visible_appointments:
        appointment["reschedule_actions"] = build_quick_reschedule_actions(int(appointment["id"]), current_path)
    month_overview = build_month_overview(
        filtered_appointments,
        month_anchor=month_anchor,
        active_filter=active_filter,
        selected_date=focus_date,
        today=today,
        route_path="/agenda",
    )
    primary_date = focus_date or today
    primary_appointments = [item for item in visible_appointments if item.get("fecha") == primary_date]
    secondary_appointments = [] if focus_date else [item for item in visible_appointments if item.get("fecha") != today]
    return templates.TemplateResponse(
        request,
        "agenda.html",
        {
            "business": business,
            "appointments": visible_appointments,
            "today_appointments": primary_appointments,
            "other_appointments": secondary_appointments,
            "today": today,
            "today_display": format_date_label(today),
            "summary": appointment_summary(appointments, today),
            "appointment_states": APPOINTMENT_STATES,
            "agenda_filters": [
                {
                    **link,
                    "href": build_agenda_url(
                        filtro=str(link["value"]),
                        selected_date=focus_date,
                        month_token=month_token,
                        route_path="/agenda",
                    ),
                }
                for link in agenda_filter_links(active_filter, route_path="/agenda")
            ],
            "agenda_views": agenda_view_links(
                active_view="list",
                active_filter=active_filter,
                selected_date=focus_date,
                month_token=month_token,
            ),
            "active_filter": active_filter,
            "current_path": current_path,
            "operational_focus": build_agenda_operational_focus(
                visible_appointments,
                today=today,
                focus_date=focus_date,
                current_path=current_path,
            ),
            "focus_date": focus_date,
            "focus_date_display": format_date_label(focus_date) if focus_date else "",
            "month_overview": month_overview,
            "saved": bool(saved),
            "moved": bool(moved),
            "error_move": error_move or "",
            "active_page": "agenda",
        },
    )


@app.get("/agenda/visual", response_class=HTMLResponse)
def agenda_visual_page(
    request: Request,
    filtro: str = "todas",
    fecha: str | None = None,
    mes: str | None = None,
    saved: int = 0,
    moved: int = 0,
    error_move: str | None = None,
) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    today = business_today(business)
    appointments = prepare_appointments(sort_agenda_appointments(list_appointments(DB_PATH), today))
    active_filter = filtro if filtro in {value for value, _ in AGENDA_FILTERS} else "todas"
    filtered_appointments = apply_agenda_filter(appointments, active_filter, today)
    selected_date = parse_optional_date(fecha)
    fallback_day = selected_date or date.fromisoformat(today)
    month_anchor = resolve_month_anchor(mes, fallback_day)
    month_token = month_anchor.strftime("%Y-%m")
    focus_date = selected_date.isoformat() if selected_date else None
    current_path = build_agenda_url(
        filtro=active_filter,
        selected_date=focus_date,
        month_token=month_token,
        route_path="/agenda/visual",
    )
    for appointment in filtered_appointments:
        appointment["reschedule_actions"] = build_quick_reschedule_actions(int(appointment["id"]), current_path)
    month_overview = build_month_overview(
        filtered_appointments,
        month_anchor=month_anchor,
        active_filter=active_filter,
        selected_date=focus_date,
        today=today,
        route_path="/agenda/visual",
    )
    visual_planner = build_visual_planner(
        filtered_appointments,
        business=business,
        active_filter=active_filter,
        focus_date=focus_date,
        month_token=month_token,
        current_path=current_path,
    )
    return templates.TemplateResponse(
        request,
        "agenda_visual.html",
        {
            "business": business,
            "appointments": filtered_appointments,
            "today": today,
            "today_display": format_date_label(today),
            "summary": appointment_summary(appointments, today),
            "agenda_filters": [
                {
                    **link,
                    "href": build_agenda_url(
                        filtro=str(link["value"]),
                        selected_date=focus_date,
                        month_token=month_token,
                        route_path="/agenda/visual",
                    ),
                }
                for link in agenda_filter_links(active_filter, route_path="/agenda/visual")
            ],
            "agenda_views": agenda_view_links(
                active_view="visual",
                active_filter=active_filter,
                selected_date=focus_date,
                month_token=month_token,
            ),
            "active_filter": active_filter,
            "current_path": current_path,
            "operational_focus": build_agenda_operational_focus(
                filtered_appointments,
                today=today,
                focus_date=focus_date,
                current_path=current_path,
            ),
            "focus_date": focus_date,
            "focus_date_display": format_date_label(focus_date) if focus_date else "",
            "month_overview": month_overview,
            "visual_planner": visual_planner,
            "saved": bool(saved),
            "moved": bool(moved),
            "error_move": error_move or "",
            "active_page": "agenda",
        },
    )


@app.post("/citas/{appointment_id}/estado", response_model=None)
async def change_appointment_status(request: Request, appointment_id: int, estado: str, return_to: str | None = None) -> RedirectResponse | HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    data = await read_form_data(request)
    if invalid := csrf_failed(request, data.get("csrf_token")):
        return invalid
    if not update_appointment_status(DB_PATH, appointment_id, estado):
        raise HTTPException(status_code=400, detail="Estado de cita no válido")
    return RedirectResponse(normalize_return_to(return_to), status_code=303)


@app.post("/citas/{appointment_id}/reprogramar", response_model=None)
async def quick_reschedule_appointment(
    request: Request,
    appointment_id: int,
    move: str,
    return_to: str | None = None,
) -> RedirectResponse | HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    data = await read_form_data(request)
    if invalid := csrf_failed(request, data.get("csrf_token")):
        return invalid

    appointment = get_appointment(DB_PATH, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    try:
        base_dt = datetime.fromisoformat(f"{appointment['fecha']}T{appointment['hora']}")
    except (KeyError, TypeError, ValueError):
        target = normalize_return_to(return_to)
        separator = "&" if "?" in target else "?"
        return RedirectResponse(
            f"{target}{separator}error_move=No+he+podido+reprogramar+esa+cita.",
            status_code=303,
        )

    delta_by_move = {
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
        "7d": timedelta(days=7),
    }
    delta = delta_by_move.get(move)
    if not delta:
        raise HTTPException(status_code=400, detail="Movimiento no válido")

    target_dt = base_dt + delta
    try:
        update_customer_appointment(
            DB_PATH,
            business=get_business(),
            appointment_id=appointment_id,
            date=target_dt.date().isoformat(),
            time=target_dt.strftime("%H:%M"),
            service_id=str(appointment.get("servicio_id") or "") or None,
            service=str(appointment.get("servicio") or ""),
            status=str(appointment.get("estado") or "pendiente"),
            notes=str(appointment.get("notas") or "").strip() or None,
            part_of_day=str(appointment.get("franja") or "").strip() or None,
        )
    except AppointmentServiceError as exc:
        target = normalize_return_to(return_to)
        separator = "&" if "?" in target else "?"
        return RedirectResponse(
            f"{target}{separator}error_move={quote_plus(exc.message)}",
            status_code=303,
        )

    target = normalize_return_to(return_to)
    separator = "&" if "?" in target else "?"
    return RedirectResponse(f"{target}{separator}moved=1", status_code=303)


@app.get("/clientes", response_class=HTMLResponse)
def customers_page(request: Request) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    return templates.TemplateResponse(
        request,
        "clientes.html",
        {
            "business": get_business(),
            "customers": prepare_customers(list_customers(DB_PATH)),
            "active_page": "clientes",
        },
    )


@app.get("/clientes/{customer_id}", response_class=HTMLResponse)
def customer_detail_page(request: Request, customer_id: int, saved: int = 0, updated: int = 0) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    customer = get_customer(DB_PATH, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    prepared_customer = prepare_customer(customer)
    appointments = prepare_appointments(list_customer_appointments(DB_PATH, customer_id))
    for appointment in appointments:
        params = [
            f"customer_id={customer_id}",
            f"return_to=/clientes/{customer_id}",
        ]
        if appointment.get("servicio_id"):
            params.append(f"servicio_id={appointment['servicio_id']}")
            if appointment.get("fecha"):
                params.append(f"repeat_from={appointment['fecha']}")
        if appointment.get("hora"):
            params.append(f"hora={appointment['hora']}")
        appointment["repeat_href"] = "/citas/nueva?" + "&".join(params)

    return templates.TemplateResponse(
        request,
        "cliente_detalle.html",
        {
            "business": get_business(),
            "customer": prepared_customer,
            "appointments": appointments,
            "appointment_states": APPOINTMENT_STATES,
            "saved": bool(saved),
            "updated": bool(updated),
            "active_page": "clientes",
        },
    )


@app.get("/clientes/{customer_id}/editar", response_class=HTMLResponse)
def edit_customer_page(request: Request, customer_id: int) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    customer = get_customer(DB_PATH, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    form_data = {
        "nombre": customer.get("nombre", ""),
        "telefono": customer.get("telefono", ""),
        "email": customer.get("email") or "",
        "notas": customer.get("notas") or "",
        "return_to": f"/clientes/{customer_id}",
    }
    return templates.TemplateResponse(
        request,
        "cliente_editar.html",
        customer_form_context(
            request,
            business=business,
            customer=prepare_customer(customer),
            form_data=form_data,
            form_action=f"/clientes/{customer_id}/editar",
            page_title="Editar cliente",
            page_subtitle="Corrige nombre, teléfono o completa la ficha sin rodeos.",
            submit_label="Guardar cliente",
        ),
    )


@app.post("/clientes/{customer_id}/editar", response_class=HTMLResponse, response_model=None)
async def save_customer_edit(request: Request, customer_id: int) -> HTMLResponse | RedirectResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    customer = get_customer(DB_PATH, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    data = await read_form_data(request)
    if invalid := csrf_failed(request, data.get("csrf_token")):
        return invalid
    form_data = {
        "nombre": (data.get("nombre") or "").strip(),
        "telefono": (data.get("telefono") or "").strip(),
        "email": (data.get("email") or "").strip(),
        "notas": (data.get("notas") or "").strip(),
        "return_to": normalize_return_to(data.get("return_to"), customer_id),
    }

    def edit_response(error: str, status_code: int = 400) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "cliente_editar.html",
            customer_form_context(
                request,
                business=business,
                customer=prepare_customer(customer),
                form_data=form_data,
                form_action=f"/clientes/{customer_id}/editar",
                page_title="Editar cliente",
                page_subtitle="Corrige nombre, teléfono o completa la ficha sin rodeos.",
                submit_label="Guardar cliente",
                error=error,
            ),
            status_code=status_code,
        )

    if not form_data["nombre"]:
        return edit_response("Necesito al menos un nombre para guardar la ficha.")

    if not is_valid_phone(form_data["telefono"]):
        return edit_response("Indica un teléfono válido. Puedes escribirlo con espacios o +34 y lo normalizo al guardar.")

    existing_customer = find_customer_by_phone(
        DB_PATH,
        form_data["telefono"],
        exclude_customer_id=customer_id,
    )
    if existing_customer:
        return edit_response(
            f"Ese teléfono ya está en la ficha de {existing_customer['nombre']}. Usa esa ficha para evitar duplicados."
        )

    update_customer(
        DB_PATH,
        customer_id=customer_id,
        name=form_data["nombre"],
        phone=form_data["telefono"],
        email=form_data["email"] or None,
        notes=form_data["notas"] or None,
    )
    return redirect_with_updated(form_data["return_to"])


@app.get("/servicios", response_class=HTMLResponse)
def services_page(request: Request, saved: int = 0) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    return templates.TemplateResponse(
        request,
        "servicios.html",
        {
            "business": get_business(),
            "services": prepare_service_records(list_services_config(DB_PATH)),
            "active_page": "config",
            "config_section": "services",
            "saved": bool(saved),
        },
    )


@app.get("/servicios/nuevo", response_class=HTMLResponse)
def new_service_page(request: Request) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    form_data = {
        "nombre": "",
        "categoria_id": "",
        "duracion_minutos": "45",
        "precio": "",
        "activo": "on",
    }
    return templates.TemplateResponse(
        request,
        "servicio_editar.html",
        service_form_context(
            request,
            business=business,
            categories=prepare_categories(service_category_options(active_only=False)),
            form_data=form_data,
            form_action="/servicios/nuevo",
            page_title="Nuevo servicio",
            page_subtitle="Añade un servicio sin tocar archivos ni código.",
            submit_label="Guardar servicio",
        ),
    )


@app.post("/servicios/nuevo", response_class=HTMLResponse, response_model=None)
async def create_service_page(request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    data = await read_form_data(request)
    if invalid := csrf_failed(request, data.get("csrf_token")):
        return invalid
    categories = prepare_categories(service_category_options(active_only=False))
    form_data = {
        "nombre": (data.get("nombre") or "").strip(),
        "categoria_id": (data.get("categoria_id") or "").strip(),
        "duracion_minutos": (data.get("duracion_minutos") or "").strip(),
        "precio": (data.get("precio") or "").strip(),
        "activo": "on" if data.get("activo") == "on" else "",
    }

    def service_response(error: str, status_code: int = 400) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "servicio_editar.html",
            service_form_context(
                request,
                business=business,
                categories=categories,
                form_data=form_data,
                form_action="/servicios/nuevo",
                page_title="Nuevo servicio",
                page_subtitle="Añade un servicio sin tocar archivos ni código.",
                submit_label="Guardar servicio",
                error=error,
            ),
            status_code=status_code,
        )

    if not form_data["nombre"]:
        return service_response("Necesito un nombre para crear el servicio.")
    if not any(category["id"] == form_data["categoria_id"] for category in categories):
        return service_response("Elige una categoría válida.")
    try:
        duration_minutes = int(form_data["duracion_minutos"])
    except ValueError:
        return service_response("Indica una duración válida en minutos.")
    if duration_minutes <= 0:
        return service_response("La duración debe ser mayor que cero.")
    if not form_data["precio"]:
        return service_response("Indica un precio orientativo.")

    create_service_config(
        DB_PATH,
        name=form_data["nombre"],
        category_id=form_data["categoria_id"],
        duration_minutes=duration_minutes,
        price=form_data["precio"],
        active=form_data["activo"] == "on",
        timezone=business.get("timezone", "Atlantic/Canary"),
    )
    return redirect_with_saved("/servicios")


@app.get("/servicios/{service_id}/editar", response_class=HTMLResponse)
def edit_service_page(request: Request, service_id: str) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    service = get_service_config(DB_PATH, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    form_data = {
        "nombre": service.get("name", ""),
        "categoria_id": service.get("category", ""),
        "duracion_minutos": str(service.get("duration_minutes") or ""),
        "precio": service.get("price", ""),
        "activo": "on" if service.get("active", True) else "",
    }
    return templates.TemplateResponse(
        request,
        "servicio_editar.html",
        service_form_context(
            request,
            business=business,
            categories=prepare_categories(service_category_options(active_only=False)),
            form_data=form_data,
            form_action=f"/servicios/{service_id}/editar",
            page_title="Editar servicio",
            page_subtitle="Cambia nombre, duración, precio o estado de forma rápida.",
            submit_label="Guardar servicio",
        ),
    )


@app.post("/servicios/{service_id}/editar", response_class=HTMLResponse, response_model=None)
async def save_service_page(request: Request, service_id: str) -> HTMLResponse | RedirectResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    service = get_service_config(DB_PATH, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    data = await read_form_data(request)
    if invalid := csrf_failed(request, data.get("csrf_token")):
        return invalid
    categories = prepare_categories(service_category_options(active_only=False))
    form_data = {
        "nombre": (data.get("nombre") or "").strip(),
        "categoria_id": (data.get("categoria_id") or "").strip(),
        "duracion_minutos": (data.get("duracion_minutos") or "").strip(),
        "precio": (data.get("precio") or "").strip(),
        "activo": "on" if data.get("activo") == "on" else "",
    }

    def service_response(error: str, status_code: int = 400) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "servicio_editar.html",
            service_form_context(
                request,
                business=business,
                categories=categories,
                form_data=form_data,
                form_action=f"/servicios/{service_id}/editar",
                page_title="Editar servicio",
                page_subtitle="Cambia nombre, duración, precio o estado de forma rápida.",
                submit_label="Guardar servicio",
                error=error,
            ),
            status_code=status_code,
        )

    if not form_data["nombre"]:
        return service_response("Necesito un nombre para guardar el servicio.")
    if not any(category["id"] == form_data["categoria_id"] for category in categories):
        return service_response("Elige una categoría válida.")
    try:
        duration_minutes = int(form_data["duracion_minutos"])
    except ValueError:
        return service_response("Indica una duración válida en minutos.")
    if duration_minutes <= 0:
        return service_response("La duración debe ser mayor que cero.")
    if not form_data["precio"]:
        return service_response("Indica un precio orientativo.")

    update_service_config(
        DB_PATH,
        service_id=service_id,
        name=form_data["nombre"],
        category_id=form_data["categoria_id"],
        duration_minutes=duration_minutes,
        price=form_data["precio"],
        active=form_data["activo"] == "on",
    )
    return redirect_with_saved("/servicios")


@app.post("/servicios/{service_id}/activo", response_model=None)
async def change_service_active(request: Request, service_id: str, activo: int) -> RedirectResponse | HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    data = await read_form_data(request)
    if invalid := csrf_failed(request, data.get("csrf_token")):
        return invalid
    set_service_active(DB_PATH, service_id, bool(activo))
    return RedirectResponse("/servicios", status_code=303)


@app.get("/personal", response_class=HTMLResponse)
def staff_page(request: Request, saved: int = 0, capacity_saved: int = 0) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    categories = prepare_categories(service_category_options(active_only=False))
    staff_members = prepare_staff_records(list_staff_members(DB_PATH))
    active_staff = [member for member in staff_members if member.get("active")]
    category_summary: list[dict[str, Any]] = []
    for category in categories:
        active_count = sum(1 for member in active_staff if category["id"] in member.get("service_categories", []))
        category_summary.append(
            {
                **category,
                "active_staff_count": active_count,
            }
        )
    return templates.TemplateResponse(
        request,
        "personal.html",
        {
            "business": get_business(),
            "staff_members": staff_members,
            "category_summary": category_summary,
            "saved": bool(saved),
            "capacity_saved": bool(capacity_saved),
            "active_page": "config",
            "config_section": "personal",
        },
    )


@app.post("/personal/capacidad", response_model=None)
async def save_capacity_page(request: Request) -> RedirectResponse:
    if redirect := require_admin_access(request):
        return redirect
    data = await read_form_data(request)
    if invalid := csrf_failed(request, data.get("csrf_token")):
        return invalid
    categories = service_category_options(active_only=False)
    capacities: dict[str, int] = {}
    for category in categories:
        raw_value = (data.get(f"capacity_{category['id']}") or "").strip()
        try:
            capacities[category["id"]] = max(0, int(raw_value or category["capacity"]))
        except ValueError:
            capacities[category["id"]] = int(category["capacity"])
    update_category_capacities(DB_PATH, capacities)
    return RedirectResponse("/personal?capacity_saved=1", status_code=303)


@app.get("/personal/nuevo", response_class=HTMLResponse)
def new_staff_page(request: Request) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    form_data = {
        "nombre": "",
        "rol": "",
        "service_categories": [],
        "activo": "on",
    }
    return templates.TemplateResponse(
        request,
        "personal_editar.html",
        staff_form_context(
            request,
            business=business,
            categories=prepare_categories(service_category_options(active_only=False)),
            form_data=form_data,
            form_action="/personal/nuevo",
            page_title="Nueva persona",
            page_subtitle="Configura quién trabaja y qué categorías puede atender.",
            submit_label="Guardar persona",
        ),
    )


@app.post("/personal/nuevo", response_class=HTMLResponse, response_model=None)
async def create_staff_page(request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    values = await read_form_lists(request)
    if invalid := csrf_failed(request, values.get("csrf_token", [""])[-1]):
        return invalid
    categories = prepare_categories(service_category_options(active_only=False))
    selected_categories = [value for value in values.get("service_categories", []) if value]
    form_data = {
        "nombre": (values.get("nombre", [""])[-1]).strip(),
        "rol": (values.get("rol", [""])[-1]).strip(),
        "service_categories": selected_categories,
        "activo": "on" if values.get("activo", [""])[-1] == "on" else "",
    }

    def staff_response(error: str, status_code: int = 400) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "personal_editar.html",
            staff_form_context(
                request,
                business=business,
                categories=categories,
                form_data=form_data,
                form_action="/personal/nuevo",
                page_title="Nueva persona",
                page_subtitle="Configura quién trabaja y qué categorías puede atender.",
                submit_label="Guardar persona",
                error=error,
            ),
            status_code=status_code,
        )

    if not form_data["nombre"]:
        return staff_response("Necesito un nombre para guardar la ficha.")
    valid_category_ids = {category["id"] for category in categories}
    if not selected_categories or any(category_id not in valid_category_ids for category_id in selected_categories):
        return staff_response("Marca al menos una categoría válida.")

    create_staff_member(
        DB_PATH,
        name=form_data["nombre"],
        role=form_data["rol"] or None,
        category_ids=selected_categories,
        active=form_data["activo"] == "on",
        timezone=business.get("timezone", "Atlantic/Canary"),
    )
    return redirect_with_saved("/personal")


@app.get("/personal/{staff_id}/editar", response_class=HTMLResponse)
def edit_staff_page(request: Request, staff_id: str) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    staff_member = get_staff_member(DB_PATH, staff_id)
    if not staff_member:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    form_data = {
        "nombre": staff_member.get("name", ""),
        "rol": staff_member.get("role", ""),
        "service_categories": staff_member.get("service_categories", []),
        "activo": "on" if staff_member.get("active", True) else "",
    }
    return templates.TemplateResponse(
        request,
        "personal_editar.html",
        staff_form_context(
            request,
            business=business,
            categories=prepare_categories(service_category_options(active_only=False)),
            form_data=form_data,
            form_action=f"/personal/{staff_id}/editar",
            page_title="Editar persona",
            page_subtitle="Ajusta categorías, estado o rol sin enredarte.",
            submit_label="Guardar persona",
        ),
    )


@app.post("/personal/{staff_id}/editar", response_class=HTMLResponse, response_model=None)
async def save_staff_page(request: Request, staff_id: str) -> HTMLResponse | RedirectResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    staff_member = get_staff_member(DB_PATH, staff_id)
    if not staff_member:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    values = await read_form_lists(request)
    if invalid := csrf_failed(request, values.get("csrf_token", [""])[-1]):
        return invalid
    categories = prepare_categories(service_category_options(active_only=False))
    selected_categories = [value for value in values.get("service_categories", []) if value]
    form_data = {
        "nombre": (values.get("nombre", [""])[-1]).strip(),
        "rol": (values.get("rol", [""])[-1]).strip(),
        "service_categories": selected_categories,
        "activo": "on" if values.get("activo", [""])[-1] == "on" else "",
    }

    def staff_response(error: str, status_code: int = 400) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "personal_editar.html",
            staff_form_context(
                request,
                business=business,
                categories=categories,
                form_data=form_data,
                form_action=f"/personal/{staff_id}/editar",
                page_title="Editar persona",
                page_subtitle="Ajusta categorías, estado o rol sin enredarte.",
                submit_label="Guardar persona",
                error=error,
            ),
            status_code=status_code,
        )

    if not form_data["nombre"]:
        return staff_response("Necesito un nombre para guardar la ficha.")
    valid_category_ids = {category["id"] for category in categories}
    if not selected_categories or any(category_id not in valid_category_ids for category_id in selected_categories):
        return staff_response("Marca al menos una categoría válida.")

    update_staff_member(
        DB_PATH,
        staff_id=staff_id,
        name=form_data["nombre"],
        role=form_data["rol"] or None,
        category_ids=selected_categories,
        active=form_data["activo"] == "on",
    )
    return redirect_with_saved("/personal")


@app.post("/personal/{staff_id}/activo", response_model=None)
async def change_staff_active(request: Request, staff_id: str, activo: int) -> RedirectResponse | HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    data = await read_form_data(request)
    if invalid := csrf_failed(request, data.get("csrf_token")):
        return invalid
    set_staff_active(DB_PATH, staff_id, bool(activo))
    return RedirectResponse("/personal", status_code=303)


@app.get("/citas/nueva", response_class=HTMLResponse)
def new_appointment_page(
    request: Request,
    customer_id: int | None = None,
    fecha: str | None = None,
    servicio_id: str | None = None,
    hora: str | None = None,
    repeat_from: str | None = None,
) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    customers = prepare_customers(list_customers(DB_PATH))
    selected_customer = get_customer(DB_PATH, customer_id) if customer_id else None
    if customer_id and not selected_customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    repeat_context = build_repeat_context(
        business=business,
        service_id=servicio_id,
        repeat_from=repeat_from,
        time=hora,
    )
    prefilled_date = fecha if parse_optional_date(fecha) else (
        repeat_context["recommended_date"] if repeat_context else business_today(business)
    )
    prefilled_service_id = (servicio_id or "").strip()
    service_ids = {str(service.get("id") or "") for service in service_catalog_options(active_only=True)}
    if prefilled_service_id not in service_ids:
        prefilled_service_id = ""
    prefilled_time = (hora or "").strip()
    try:
        datetime.strptime(prefilled_time, "%H:%M")
    except ValueError:
        prefilled_time = ""

    form_data = {
        "customer_id": str(customer_id or ""),
        "fecha": prefilled_date,
        "hora": prefilled_time,
        "servicio_id": prefilled_service_id,
        "estado": "confirmada",
        "notas": "",
        "nombre": "",
        "telefono": "",
        "return_to": normalize_return_to(request.query_params.get("return_to"), customer_id),
    }
    return templates.TemplateResponse(
        request,
        "cita_nueva.html",
        manual_appointment_context(
            request,
            business=business,
            customers=customers,
            services=service_catalog_options(active_only=True),
            form_data=form_data,
            selected_customer=prepare_customer(selected_customer) if selected_customer else None,
            mode="create",
            form_action="/citas/nueva",
            page_title="Nueva cita",
            page_subtitle="Alta rápida para mostrador, teléfono o próxima visita.",
            submit_label="Guardar cita",
            repeat_context=repeat_context,
        ),
    )


@app.post("/citas/nueva", response_class=HTMLResponse, response_model=None)
async def create_manual_appointment(request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    data = await read_form_data(request)
    if invalid := csrf_failed(request, data.get("csrf_token")):
        return invalid
    customers = prepare_customers(list_customers(DB_PATH))
    services = service_catalog_options(active_only=True)
    services_by_id = service_map(business)

    raw_customer_id = (data.get("customer_id") or "").strip()
    selected_customer = None
    customer_id: int | None = None
    if raw_customer_id:
        try:
            customer_id = int(raw_customer_id)
        except ValueError:
            customer_id = None
        else:
            selected_customer = get_customer(DB_PATH, customer_id)

    if raw_customer_id and not selected_customer:
        return templates.TemplateResponse(
            request,
            "cita_nueva.html",
            manual_appointment_context(
                request,
                business=business,
                customers=customers,
                services=services,
                form_data=data,
                selected_customer=None,
                mode="create",
                error="No encuentro ese cliente. Elige uno de la lista o crea uno nuevo rápido.",
            ),
            status_code=400,
        )

    raw_service_id = (data.get("servicio_id") or "").strip()
    service = services_by_id.get(raw_service_id)
    if not service:
        return templates.TemplateResponse(
            request,
            "cita_nueva.html",
            manual_appointment_context(
                request,
                business=business,
                customers=customers,
                services=services,
                form_data=data,
                selected_customer=prepare_customer(selected_customer) if selected_customer else None,
                mode="create",
                error="Elige un servicio para guardar la cita.",
            ),
            status_code=400,
        )

    raw_date = (data.get("fecha") or "").strip()
    raw_time = (data.get("hora") or "").strip()
    try:
        appointment_date = date.fromisoformat(raw_date)
    except ValueError:
        appointment_date = None
    if not appointment_date:
        return templates.TemplateResponse(
            request,
            "cita_nueva.html",
            manual_appointment_context(
                request,
                business=business,
                customers=customers,
                services=services,
                form_data=data,
                selected_customer=prepare_customer(selected_customer) if selected_customer else None,
                mode="create",
                error="Indica una fecha válida para la cita.",
            ),
            status_code=400,
        )

    if appointment_date < date.fromisoformat(business_today(business)):
        return templates.TemplateResponse(
            request,
            "cita_nueva.html",
            manual_appointment_context(
                request,
                business=business,
                customers=customers,
                services=services,
                form_data=data,
                selected_customer=prepare_customer(selected_customer) if selected_customer else None,
                mode="create",
                error="No puedo guardar una cita en una fecha pasada.",
            ),
            status_code=400,
        )

    try:
        datetime.strptime(raw_time, "%H:%M")
    except ValueError:
        return templates.TemplateResponse(
            request,
            "cita_nueva.html",
            manual_appointment_context(
                request,
                business=business,
                customers=customers,
                services=services,
                form_data=data,
                selected_customer=prepare_customer(selected_customer) if selected_customer else None,
                mode="create",
                error="Indica una hora válida con formato HH:MM.",
            ),
            status_code=400,
        )

    status = (data.get("estado") or "confirmada").strip()
    if status not in MANUAL_APPOINTMENT_STATES:
        status = "confirmada"

    customer = selected_customer
    customer_name = ""
    customer_phone = ""
    if not selected_customer:
        name = (data.get("nombre") or "").strip()
        phone = (data.get("telefono") or "").strip()
        if not name or not phone:
            return templates.TemplateResponse(
                request,
                "cita_nueva.html",
                manual_appointment_context(
                    request,
                    business=business,
                    customers=customers,
                    services=services,
                    form_data=data,
                    selected_customer=None,
                    mode="create",
                    error="Si no eliges un cliente existente, necesito al menos nombre y teléfono.",
                ),
                status_code=400,
            )
        if not is_valid_phone(phone):
            return templates.TemplateResponse(
                request,
                "cita_nueva.html",
                manual_appointment_context(
                    request,
                    business=business,
                    customers=customers,
                    services=services,
                    form_data=data,
                    selected_customer=None,
                    mode="create",
                    error="Indica un teléfono válido. Puedes escribirlo con espacios o +34 y lo normalizo al guardar.",
                ),
                status_code=400,
            )
        customer_name = name
        customer_phone = phone

    try:
        result = create_customer_appointment(
            DB_PATH,
            business=business,
            customer_id=int(customer["id"]) if customer else None,
            customer_name=customer_name or None,
            customer_phone=customer_phone or None,
            date=raw_date,
            time=raw_time,
            service_id=service["id"],
            service=service["name"],
            status=status,
            notes=(data.get("notas") or "").strip() or None,
        )
    except AppointmentServiceError as exc:
        return templates.TemplateResponse(
            request,
            "cita_nueva.html",
            manual_appointment_context(
                request,
                business=business,
                customers=customers,
                services=services,
                form_data=data,
                selected_customer=prepare_customer(customer) if customer else None,
                mode="create",
                error=exc.message,
            ),
            status_code=400,
        )
    customer = result["customer"]
    customer_id = int(customer["id"])
    return redirect_with_saved(normalize_return_to(data.get("return_to"), customer_id))


@app.get("/citas/{appointment_id}/editar", response_class=HTMLResponse)
def edit_appointment_page(
    request: Request,
    appointment_id: int,
    return_to: str | None = None,
) -> HTMLResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    appointment = get_appointment(DB_PATH, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    customer = get_customer(DB_PATH, int(appointment["cliente_id"]))
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    form_data = {
        "customer_id": str(appointment["cliente_id"]),
        "fecha": appointment.get("fecha", ""),
        "hora": appointment.get("hora", ""),
        "servicio_id": str(appointment.get("servicio_id") or "") or service_id_for_name(business, appointment.get("servicio")),
        "estado": appointment.get("estado", "pendiente"),
        "notas": appointment.get("notas") or "",
        "nombre": "",
        "telefono": "",
        "return_to": normalize_return_to(return_to, int(appointment["cliente_id"])),
    }
    return templates.TemplateResponse(
        request,
        "cita_nueva.html",
        manual_appointment_context(
            request,
            business=business,
            customers=prepare_customers(list_customers(DB_PATH)),
            services=service_catalog_options(
                active_only=True,
                include_service_name=appointment.get("servicio"),
            ),
            form_data=form_data,
            selected_customer=prepare_customer(customer),
            mode="edit",
            form_action=f"/citas/{appointment_id}/editar",
            page_title="Editar cita",
            page_subtitle="Corrige hora, fecha, servicio, estado o nota sin salir del flujo.",
            submit_label="Guardar cambios",
        ),
    )


@app.post("/citas/{appointment_id}/editar", response_class=HTMLResponse, response_model=None)
async def save_appointment_edit(
    request: Request,
    appointment_id: int,
) -> HTMLResponse | RedirectResponse:
    if redirect := require_admin_access(request):
        return redirect
    business = get_business()
    appointment = get_appointment(DB_PATH, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    customer = get_customer(DB_PATH, int(appointment["cliente_id"]))
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    data = await read_form_data(request)
    if invalid := csrf_failed(request, data.get("csrf_token")):
        return invalid
    services = service_catalog_options(
        active_only=True,
        include_service_name=appointment.get("servicio"),
    )
    services_by_id = {str(service.get("id", "")): service for service in services if service.get("id")}
    raw_service_id = (data.get("servicio_id") or "").strip()
    service = services_by_id.get(raw_service_id)
    form_data = {
        "customer_id": str(appointment["cliente_id"]),
        "fecha": (data.get("fecha") or "").strip(),
        "hora": (data.get("hora") or "").strip(),
        "servicio_id": raw_service_id,
        "estado": (data.get("estado") or appointment.get("estado") or "pendiente").strip(),
        "notas": data.get("notas") or "",
        "nombre": "",
        "telefono": "",
        "return_to": normalize_return_to(data.get("return_to"), int(appointment["cliente_id"])),
    }

    def edit_response(error: str, status_code: int = 400) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "cita_nueva.html",
            manual_appointment_context(
                request,
                business=business,
                customers=prepare_customers(list_customers(DB_PATH)),
                services=services,
                form_data=form_data,
                selected_customer=prepare_customer(customer),
                mode="edit",
                form_action=f"/citas/{appointment_id}/editar",
                page_title="Editar cita",
                page_subtitle="Corrige hora, fecha, servicio, estado o nota sin salir del flujo.",
                submit_label="Guardar cambios",
                error=error,
            ),
            status_code=status_code,
        )

    if not service:
        return edit_response("Elige un servicio para guardar la cita.")

    raw_date = form_data["fecha"]
    raw_time = form_data["hora"]
    try:
        appointment_date = date.fromisoformat(raw_date)
    except ValueError:
        appointment_date = None
    if not appointment_date:
        return edit_response("Indica una fecha válida para la cita.")

    if appointment_date < date.fromisoformat(business_today(business)):
        return edit_response("No puedo guardar una cita en una fecha pasada.")

    try:
        datetime.strptime(raw_time, "%H:%M")
    except ValueError:
        return edit_response("Indica una hora válida con formato HH:MM.")

    status = form_data["estado"]
    if status not in APPOINTMENT_STATES:
        return edit_response("Elige un estado válido para la cita.")

    try:
        update_customer_appointment(
            DB_PATH,
            business=business,
            appointment_id=appointment_id,
            date=raw_date,
            time=raw_time,
            service_id=service["id"],
            service=service["name"],
            status=status,
            notes=form_data["notas"].strip() or None,
        )
    except AppointmentServiceError as exc:
        return edit_response(exc.message)
    return redirect_with_saved(form_data["return_to"])
