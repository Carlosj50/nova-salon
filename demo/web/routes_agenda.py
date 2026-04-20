from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import quote_plus

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..core.appointment_service import AppointmentServiceError, update_customer_appointment
from ..core.models import APPOINTMENT_STATES
from ..core.repositories import get_appointment, list_appointments, update_appointment_status
from . import context as web_context
from . import view_helpers


router = APIRouter()


@router.get("/agenda", response_class=HTMLResponse)
def agenda_page(
    request: Request,
    filtro: str = "todas",
    fecha: str | None = None,
    mes: str | None = None,
    saved: int = 0,
    moved: int = 0,
    error_move: str | None = None,
    forbidden: int = 0,
) -> HTMLResponse:
    if redirect := web_context.require_panel_access(request):
        return redirect
    business = web_context.get_business()
    appointments = view_helpers.prepare_appointments(
        view_helpers.sort_agenda_appointments(
            list_appointments(web_context.DB_PATH),
            view_helpers.business_today(business),
        )
    )
    today = view_helpers.business_today(business)
    active_filter = filtro if filtro in {value for value, _ in view_helpers.AGENDA_FILTERS} else "todas"
    filtered_appointments = view_helpers.apply_agenda_filter(appointments, active_filter, today)
    selected_date = view_helpers.parse_optional_date(fecha)
    fallback_day = selected_date or date.fromisoformat(today)
    month_anchor = view_helpers.resolve_month_anchor(mes, fallback_day)
    month_token = month_anchor.strftime("%Y-%m")
    focus_date = selected_date.isoformat() if selected_date else None
    visible_appointments = [
        item for item in filtered_appointments if not focus_date or item.get("fecha") == focus_date
    ]
    current_path = view_helpers.build_agenda_url(
        filtro=active_filter,
        selected_date=focus_date,
        month_token=month_token,
    )
    for appointment in visible_appointments:
        appointment["reschedule_actions"] = view_helpers.build_quick_reschedule_actions(
            int(appointment["id"]),
            current_path,
        )
    month_overview = view_helpers.build_month_overview(
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
    return web_context.templates.TemplateResponse(
        request,
        "agenda.html",
        {
            "business": business,
            "appointments": visible_appointments,
            "today_appointments": primary_appointments,
            "other_appointments": secondary_appointments,
            "today": today,
            "today_display": view_helpers.format_date_label(today),
            "summary": view_helpers.appointment_summary(appointments, today),
            "forbidden": bool(forbidden),
            "appointment_states": APPOINTMENT_STATES,
            "agenda_filters": [
                {
                    **link,
                    "href": view_helpers.build_agenda_url(
                        filtro=str(link["value"]),
                        selected_date=focus_date,
                        month_token=month_token,
                        route_path="/agenda",
                    ),
                }
                for link in view_helpers.agenda_filter_links(active_filter, route_path="/agenda")
            ],
            "agenda_views": view_helpers.agenda_view_links(
                active_view="list",
                active_filter=active_filter,
                selected_date=focus_date,
                month_token=month_token,
            ),
            "active_filter": active_filter,
            "current_path": current_path,
            "operational_focus": view_helpers.build_agenda_operational_focus(
                visible_appointments,
                today=today,
                focus_date=focus_date,
                current_path=current_path,
            ),
            "focus_date": focus_date,
            "focus_date_display": view_helpers.format_date_label(focus_date) if focus_date else "",
            "month_overview": month_overview,
            "saved": bool(saved),
            "moved": bool(moved),
            "error_move": error_move or "",
            "active_page": "agenda",
        },
    )


@router.get("/agenda/visual", response_class=HTMLResponse)
def agenda_visual_page(
    request: Request,
    filtro: str = "todas",
    fecha: str | None = None,
    mes: str | None = None,
    saved: int = 0,
    moved: int = 0,
    error_move: str | None = None,
    forbidden: int = 0,
) -> HTMLResponse:
    if redirect := web_context.require_panel_access(request):
        return redirect
    business = web_context.get_business()
    today = view_helpers.business_today(business)
    appointments = view_helpers.prepare_appointments(
        view_helpers.sort_agenda_appointments(list_appointments(web_context.DB_PATH), today)
    )
    active_filter = filtro if filtro in {value for value, _ in view_helpers.AGENDA_FILTERS} else "todas"
    filtered_appointments = view_helpers.apply_agenda_filter(appointments, active_filter, today)
    selected_date = view_helpers.parse_optional_date(fecha)
    fallback_day = selected_date or date.fromisoformat(today)
    month_anchor = view_helpers.resolve_month_anchor(mes, fallback_day)
    month_token = month_anchor.strftime("%Y-%m")
    focus_date = selected_date.isoformat() if selected_date else None
    current_path = view_helpers.build_agenda_url(
        filtro=active_filter,
        selected_date=focus_date,
        month_token=month_token,
        route_path="/agenda/visual",
    )
    for appointment in filtered_appointments:
        appointment["reschedule_actions"] = view_helpers.build_quick_reschedule_actions(
            int(appointment["id"]),
            current_path,
        )
    month_overview = view_helpers.build_month_overview(
        filtered_appointments,
        month_anchor=month_anchor,
        active_filter=active_filter,
        selected_date=focus_date,
        today=today,
        route_path="/agenda/visual",
    )
    visual_planner = view_helpers.build_visual_planner(
        filtered_appointments,
        business=business,
        active_filter=active_filter,
        focus_date=focus_date,
        month_token=month_token,
        current_path=current_path,
    )
    return web_context.templates.TemplateResponse(
        request,
        "agenda_visual.html",
        {
            "business": business,
            "appointments": filtered_appointments,
            "today": today,
            "today_display": view_helpers.format_date_label(today),
            "summary": view_helpers.appointment_summary(appointments, today),
            "forbidden": bool(forbidden),
            "agenda_filters": [
                {
                    **link,
                    "href": view_helpers.build_agenda_url(
                        filtro=str(link["value"]),
                        selected_date=focus_date,
                        month_token=month_token,
                        route_path="/agenda/visual",
                    ),
                }
                for link in view_helpers.agenda_filter_links(active_filter, route_path="/agenda/visual")
            ],
            "agenda_views": view_helpers.agenda_view_links(
                active_view="visual",
                active_filter=active_filter,
                selected_date=focus_date,
                month_token=month_token,
            ),
            "active_filter": active_filter,
            "current_path": current_path,
            "operational_focus": view_helpers.build_agenda_operational_focus(
                filtered_appointments,
                today=today,
                focus_date=focus_date,
                current_path=current_path,
            ),
            "focus_date": focus_date,
            "focus_date_display": view_helpers.format_date_label(focus_date) if focus_date else "",
            "month_overview": month_overview,
            "visual_planner": visual_planner,
            "saved": bool(saved),
            "moved": bool(moved),
            "error_move": error_move or "",
            "active_page": "agenda",
        },
    )


@router.post("/citas/{appointment_id}/estado", response_model=None)
async def change_appointment_status(
    request: Request,
    appointment_id: int,
    estado: str,
    return_to: str | None = None,
) -> RedirectResponse | HTMLResponse:
    if redirect := web_context.require_panel_access(request):
        return redirect
    data = await view_helpers.read_form_data(request)
    if invalid := web_context.csrf_failed(request, data.get("csrf_token")):
        return invalid
    if not update_appointment_status(web_context.DB_PATH, appointment_id, estado):
        raise HTTPException(status_code=400, detail="Estado de cita no válido")
    return RedirectResponse(view_helpers.normalize_return_to(return_to), status_code=303)


@router.post("/citas/{appointment_id}/reprogramar", response_model=None)
async def quick_reschedule_appointment(
    request: Request,
    appointment_id: int,
    move: str,
    return_to: str | None = None,
) -> RedirectResponse | HTMLResponse:
    if redirect := web_context.require_panel_access(request):
        return redirect
    data = await view_helpers.read_form_data(request)
    if invalid := web_context.csrf_failed(request, data.get("csrf_token")):
        return invalid

    appointment = get_appointment(web_context.DB_PATH, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    try:
        base_dt = datetime.fromisoformat(f"{appointment['fecha']}T{appointment['hora']}")
    except (KeyError, TypeError, ValueError):
        target = view_helpers.normalize_return_to(return_to)
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
            web_context.DB_PATH,
            business=web_context.get_business(),
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
        target = view_helpers.normalize_return_to(return_to)
        separator = "&" if "?" in target else "?"
        return RedirectResponse(
            f"{target}{separator}error_move={quote_plus(exc.message)}",
            status_code=303,
        )

    target = view_helpers.normalize_return_to(return_to)
    separator = "&" if "?" in target else "?"
    return RedirectResponse(f"{target}{separator}moved=1", status_code=303)
