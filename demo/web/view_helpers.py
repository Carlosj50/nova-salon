from __future__ import annotations

from calendar import Calendar
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlencode
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..core.models import APPOINTMENT_STATES
from ..core.repositories import (
    get_service_config,
    get_service_config_by_name,
    list_service_categories,
    list_services_config,
)
from .context import DB_PATH


WEEKDAY_LABELS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
MONTH_LABELS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
MANUAL_APPOINTMENT_STATES = ("confirmada", "pendiente")
AGENDA_FILTERS = (
    ("todas", "Todas"),
    ("hoy", "Hoy"),
    ("pendientes", "Pendientes"),
    ("confirmadas", "Confirmadas"),
    ("completadas", "Completadas"),
    ("canceladas", "Canceladas"),
)


def business_today(business: dict) -> str:
    timezone = business.get("timezone", "Atlantic/Canary")
    return datetime.now(ZoneInfo(timezone)).date().isoformat()


def format_date_label(raw_date: str | None) -> str:
    if not raw_date:
        return "Sin fecha"
    try:
        parsed = date.fromisoformat(raw_date)
    except ValueError:
        return raw_date
    return f"{WEEKDAY_LABELS[parsed.weekday()]} {parsed.strftime('%d/%m/%Y')}"


def format_datetime_label(raw_datetime: str | None) -> str:
    if not raw_datetime:
        return "—"
    try:
        parsed = datetime.fromisoformat(raw_datetime)
    except ValueError:
        return raw_datetime
    return f"{format_date_label(parsed.date().isoformat())} {parsed.strftime('%H:%M')}"


def quick_status_actions(status: str) -> list[tuple[str, str]]:
    if status == "pendiente":
        return [("confirmada", "Confirmar"), ("cancelada", "Cancelar")]
    if status == "confirmada":
        return [("completada", "Completar"), ("cancelada", "Cancelar")]
    if status == "cancelada":
        return [("pendiente", "Reabrir")]
    return []


def prepare_appointments(appointments: list[dict]) -> list[dict]:
    prepared = []
    for appointment in appointments:
        item = dict(appointment)
        item["fecha_display"] = format_date_label(item.get("fecha"))
        item["actions"] = quick_status_actions(item.get("estado", ""))
        item["search_text"] = " ".join(
            part.lower()
            for part in (
                str(item.get("cliente_nombre", "")).strip(),
                str(item.get("cliente_telefono", "")).strip(),
                str(item.get("servicio", "")).strip(),
                str(item.get("fecha_display", "")).strip(),
                str(item.get("hora", "")).strip(),
            )
            if part
        )
        prepared.append(item)
    return prepared


def prepare_customers(customers: list[dict]) -> list[dict]:
    prepared = []
    for customer in customers:
        item = dict(customer)
        item["fecha_alta_display"] = format_datetime_label(item.get("fecha_alta"))
        item["ultima_visita_display"] = format_date_label(item.get("ultima_visita")) if item.get("ultima_visita") else "Sin visitas"
        item["search_text"] = f"{item.get('nombre', '')} {item.get('telefono', '')}".lower()
        prepared.append(item)
    return prepared


def prepare_customer(customer: dict) -> dict:
    item = dict(customer)
    item["fecha_alta_display"] = format_datetime_label(item.get("fecha_alta"))
    item["ultima_visita_display"] = format_date_label(item.get("ultima_visita")) if item.get("ultima_visita") else "Sin visitas"
    return item


def prepare_service_records(services: list[dict]) -> list[dict]:
    prepared: list[dict] = []
    for service in services:
        item = dict(service)
        item["duration_display"] = f"{int(item.get('duration_minutes') or 0)} min"
        item["active_label"] = "activo" if item.get("active", True) else "inactivo"
        prepared.append(item)
    return prepared


def prepare_categories(categories: list[dict]) -> list[dict]:
    return [dict(category) for category in categories]


def prepare_staff_records(staff_members: list[dict]) -> list[dict]:
    prepared: list[dict] = []
    for member in staff_members:
        item = dict(member)
        item["categories_display"] = ", ".join(item.get("category_names", [])) or "Sin categorías"
        item["active_label"] = "activa" if item.get("active", True) else "inactiva"
        prepared.append(item)
    return prepared


def appointment_summary(appointments: list[dict], today: str) -> dict[str, int]:
    active = [item for item in appointments if item.get("estado") in {"pendiente", "confirmada"}]
    return {
        "today": sum(1 for item in appointments if item.get("fecha") == today and item.get("estado") != "cancelada"),
        "pending": sum(1 for item in appointments if item.get("estado") == "pendiente"),
        "confirmed": sum(1 for item in appointments if item.get("estado") == "confirmada"),
        "active": len(active),
    }


def appointment_time_sort_key(item: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(item.get("fecha") or ""),
        str(item.get("hora") or "00:00"),
        int(item.get("id") or 0),
    )


def build_agenda_operational_focus(
    appointments: list[dict],
    *,
    today: str,
    focus_date: str | None,
    current_path: str,
) -> dict[str, Any]:
    target_date = focus_date or today
    target_items = [
        item for item in appointments
        if item.get("fecha") == target_date and item.get("estado") != "cancelada"
    ]
    pending_items = sorted(
        [item for item in target_items if item.get("estado") == "pendiente"],
        key=appointment_time_sort_key,
    )
    active_items = sorted(
        [item for item in target_items if item.get("estado") in {"pendiente", "confirmada"}],
        key=appointment_time_sort_key,
    )
    upcoming_items = sorted(
        [
            item for item in appointments
            if str(item.get("fecha") or "") >= today and item.get("estado") in {"pendiente", "confirmada"}
        ],
        key=appointment_time_sort_key,
    )

    def enrich(item: dict[str, Any]) -> dict[str, Any]:
        return {
            **item,
            "edit_href": f"/citas/{item['id']}/editar?return_to={current_path}",
            "customer_href": f"/clientes/{item['cliente_id']}",
            "confirm_href": f"/citas/{item['id']}/estado?estado=confirmada&return_to={current_path}",
            "complete_href": f"/citas/{item['id']}/estado?estado=completada&return_to={current_path}",
        }

    next_item = active_items[0] if active_items else (upcoming_items[0] if upcoming_items else None)

    return {
        "target_date": target_date,
        "target_date_display": format_date_label(target_date),
        "is_today": target_date == today,
        "pending_count": len(pending_items),
        "active_count": len(active_items),
        "attention_items": [enrich(item) for item in pending_items[:3]],
        "next_item": enrich(next_item) if next_item else None,
        "has_items": bool(target_items),
        "is_future_focus": bool(focus_date and focus_date != today),
    }


def sort_agenda_appointments(appointments: list[dict], today: str) -> list[dict]:
    today_value = date.fromisoformat(today)

    def sort_key(item: dict) -> tuple[int, int, str, int]:
        raw_date = str(item.get("fecha") or "")
        try:
            item_date = date.fromisoformat(raw_date)
        except ValueError:
            item_date = today_value
        raw_time = str(item.get("hora") or "00:00")
        raw_id = -int(item.get("id") or 0)
        if item_date >= today_value:
            return (0, item_date.toordinal(), raw_time, raw_id)
        return (1, -item_date.toordinal(), raw_time, raw_id)

    return sorted(appointments, key=sort_key)


def service_options(business: dict) -> list[dict]:
    return sorted(business.get("services", []), key=lambda service: service.get("name", ""))


def service_map(business: dict) -> dict[str, dict]:
    return {str(service.get("id", "")): service for service in business.get("services", []) if service.get("id")}


def service_id_for_name(business: dict, service_name: str | None) -> str:
    for service in business.get("services", []):
        if service.get("name") == service_name:
            return str(service.get("id", ""))
    extra = get_service_config_by_name(DB_PATH, service_name)
    if extra:
        return str(extra.get("id", ""))
    return ""


def service_category_options(*, active_only: bool = False) -> list[dict]:
    return list_service_categories(DB_PATH, active_only=active_only)


def service_catalog_options(
    *,
    active_only: bool = True,
    include_service_id: str | None = None,
    include_service_name: str | None = None,
) -> list[dict]:
    services = list_services_config(DB_PATH, active_only=active_only)
    if include_service_id and not any(service["id"] == include_service_id for service in services):
        extra = get_service_config(DB_PATH, include_service_id)
        if extra:
            services.append(extra)
    if include_service_name and not any(service["name"] == include_service_name for service in services):
        extra = get_service_config_by_name(DB_PATH, include_service_name)
        if extra:
            services.append(extra)
    return sorted(services, key=lambda service: service.get("name", ""))


def normalize_return_to(raw_path: str | None, customer_id: int | None = None) -> str:
    if raw_path and raw_path.startswith("/clientes/"):
        return raw_path
    if raw_path and raw_path.startswith("/agenda"):
        return raw_path
    if customer_id:
        return f"/clientes/{customer_id}"
    return "/agenda"


def redirect_with_saved(path: str) -> RedirectResponse:
    separator = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{separator}saved=1", status_code=303)


def redirect_with_updated(path: str) -> RedirectResponse:
    separator = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{separator}updated=1", status_code=303)


def build_agenda_url(
    *,
    filtro: str = "todas",
    selected_date: str | None = None,
    month_token: str | None = None,
    route_path: str = "/agenda",
) -> str:
    params: dict[str, str] = {}
    if filtro != "todas":
        params["filtro"] = filtro
    if selected_date:
        params["fecha"] = selected_date
    if month_token:
        params["mes"] = month_token
    query = urlencode(params)
    return f"{route_path}?{query}" if query else route_path


def parse_optional_date(raw_date: str | None) -> date | None:
    if not raw_date:
        return None
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return None


def add_months(base_month: date, delta: int) -> date:
    month_index = (base_month.month - 1) + delta
    year = base_month.year + (month_index // 12)
    month = (month_index % 12) + 1
    return date(year, month, 1)


def resolve_month_anchor(raw_month: str | None, fallback: date) -> date:
    if raw_month:
        try:
            return date.fromisoformat(f"{raw_month}-01")
        except ValueError:
            pass
    return date(fallback.year, fallback.month, 1)


def manual_appointment_context(
    request: Request,
    *,
    business: dict,
    customers: list[dict],
    services: list[dict],
    form_data: dict[str, str],
    selected_customer: dict | None,
    mode: str = "create",
    form_action: str = "/citas/nueva",
    page_title: str = "Nueva cita",
    page_subtitle: str = "Alta rápida para mostrador, teléfono o próxima visita.",
    submit_label: str = "Guardar cita",
    error: str | None = None,
) -> dict:
    return {
        "request": request,
        "business": business,
        "customers": customers,
        "services": services,
        "form_data": form_data,
        "selected_customer": selected_customer,
        "appointment_states": MANUAL_APPOINTMENT_STATES,
        "mode": mode,
        "form_action": form_action,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "submit_label": submit_label,
        "error": error,
        "active_page": "agenda",
    }


def customer_form_context(
    request: Request,
    *,
    business: dict,
    customer: dict,
    form_data: dict[str, str],
    form_action: str,
    page_title: str,
    page_subtitle: str,
    submit_label: str,
    error: str | None = None,
) -> dict:
    return {
        "request": request,
        "business": business,
        "customer": customer,
        "form_data": form_data,
        "form_action": form_action,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "submit_label": submit_label,
        "error": error,
        "active_page": "clientes",
    }


def service_form_context(
    request: Request,
    *,
    business: dict,
    categories: list[dict],
    form_data: dict[str, str],
    form_action: str,
    page_title: str,
    page_subtitle: str,
    submit_label: str,
    error: str | None = None,
) -> dict:
    return {
        "request": request,
        "business": business,
        "categories": categories,
        "form_data": form_data,
        "form_action": form_action,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "submit_label": submit_label,
        "error": error,
        "active_page": "config",
        "config_section": "services",
    }


def staff_form_context(
    request: Request,
    *,
    business: dict,
    categories: list[dict],
    form_data: dict[str, Any],
    form_action: str,
    page_title: str,
    page_subtitle: str,
    submit_label: str,
    error: str | None = None,
) -> dict:
    return {
        "request": request,
        "business": business,
        "categories": categories,
        "form_data": form_data,
        "form_action": form_action,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "submit_label": submit_label,
        "error": error,
        "active_page": "config",
        "config_section": "personal",
    }


def business_form_context(
    request: Request,
    *,
    business: dict,
    form_data: dict[str, str],
    form_action: str,
    page_title: str,
    page_subtitle: str,
    submit_label: str,
    error: str | None = None,
    saved: bool = False,
) -> dict[str, Any]:
    return {
        "request": request,
        "business": business,
        "form_data": form_data,
        "form_action": form_action,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "submit_label": submit_label,
        "error": error,
        "saved": saved,
        "active_page": "config",
        "config_section": "business",
    }


def apply_agenda_filter(appointments: list[dict], filtro: str, today: str) -> list[dict]:
    if filtro == "hoy":
        return [item for item in appointments if item.get("fecha") == today]
    if filtro == "pendientes":
        return [item for item in appointments if item.get("estado") == "pendiente"]
    if filtro == "confirmadas":
        return [item for item in appointments if item.get("estado") == "confirmada"]
    if filtro == "completadas":
        return [item for item in appointments if item.get("estado") == "completada"]
    if filtro == "canceladas":
        return [item for item in appointments if item.get("estado") == "cancelada"]
    return appointments


def agenda_filter_links(active_filter: str, *, route_path: str = "/agenda") -> list[dict[str, str | bool]]:
    links: list[dict[str, str | bool]] = []
    for value, label in AGENDA_FILTERS:
        href = build_agenda_url(filtro=value, route_path=route_path)
        links.append(
            {
                "value": value,
                "label": label,
                "href": href,
                "active": value == active_filter,
            }
        )
    return links


async def read_form_data(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


async def read_form_lists(request: Request) -> dict[str, list[str]]:
    body = (await request.body()).decode("utf-8")
    return parse_qs(body, keep_blank_values=True)


def build_month_overview(
    appointments: list[dict],
    *,
    month_anchor: date,
    active_filter: str,
    selected_date: str | None,
    today: str,
    route_path: str = "/agenda",
) -> dict:
    date_counts: dict[str, int] = {}
    for appointment in appointments:
        appointment_date = str(appointment.get("fecha") or "")
        if not appointment_date:
            continue
        date_counts[appointment_date] = date_counts.get(appointment_date, 0) + 1

    calendar = Calendar(firstweekday=0)
    month_token = month_anchor.strftime("%Y-%m")
    weeks: list[list[dict | None]] = []
    for week in calendar.monthdatescalendar(month_anchor.year, month_anchor.month):
        row: list[dict | None] = []
        for day_value in week:
            if day_value.month != month_anchor.month:
                row.append(None)
                continue
            day_iso = day_value.isoformat()
            row.append(
                {
                    "iso": day_iso,
                    "label": day_value.day,
                    "count": date_counts.get(day_iso, 0),
                    "href": build_agenda_url(
                        filtro=active_filter,
                        selected_date=day_iso,
                        month_token=month_token,
                        route_path=route_path,
                    ),
                    "is_today": day_iso == today,
                    "is_selected": day_iso == selected_date,
                    "has_items": date_counts.get(day_iso, 0) > 0,
                }
            )
        weeks.append(row)

    prev_month = add_months(month_anchor, -1)
    next_month = add_months(month_anchor, 1)
    selected_day = parse_optional_date(selected_date)
    selected_in_month = bool(selected_day and selected_day.year == month_anchor.year and selected_day.month == month_anchor.month)
    clear_href = build_agenda_url(filtro=active_filter, month_token=month_token, route_path=route_path)

    return {
        "label": f"{MONTH_LABELS[month_anchor.month - 1]} {month_anchor.year}",
        "month_token": month_token,
        "weeks": weeks,
        "prev_href": build_agenda_url(filtro=active_filter, month_token=prev_month.strftime("%Y-%m"), route_path=route_path),
        "next_href": build_agenda_url(filtro=active_filter, month_token=next_month.strftime("%Y-%m"), route_path=route_path),
        "clear_href": clear_href,
        "selected_in_month": selected_in_month,
    }


def agenda_view_links(*, active_view: str, active_filter: str, selected_date: str | None, month_token: str | None) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Vista lista",
            "href": build_agenda_url(
                filtro=active_filter,
                selected_date=selected_date,
                month_token=month_token,
                route_path="/agenda",
            ),
            "active": active_view == "list",
        },
        {
            "label": "Vista visual",
            "href": build_agenda_url(
                filtro=active_filter,
                selected_date=selected_date,
                month_token=month_token,
                route_path="/agenda/visual",
            ),
            "active": active_view == "visual",
        },
    ]


def parse_schedule_range(raw_value: str | None) -> tuple[int, int] | None:
    if not raw_value or raw_value == "cerrado":
        return None
    if "-" not in raw_value:
        return None
    start, end = (item.strip() for item in raw_value.split("-", 1))
    if len(start) != 5 or len(end) != 5 or ":" not in start or ":" not in end:
        return None
    try:
        return time_to_minutes(start), time_to_minutes(end)
    except ValueError:
        return None


def is_valid_business_schedule(raw_value: str) -> bool:
    value = raw_value.strip().lower()
    if value == "cerrado":
        return True
    schedule_range = parse_schedule_range(value)
    if not schedule_range:
        return False
    start, end = schedule_range
    return end > start


def business_schedule_for_date(date_iso: str, business: dict) -> str:
    hours = business.get("hours", {})
    parsed = date.fromisoformat(date_iso)
    if parsed.weekday() <= 4:
        return str(hours.get("monday_friday") or hours.get("summary") or "horario pendiente de configurar")
    if parsed.weekday() == 5:
        return str(hours.get("saturday") or "cerrado")
    return str(hours.get("sunday") or "cerrado")


def time_to_minutes(raw_time: str) -> int:
    hours, minutes = (int(part) for part in raw_time.split(":", 1))
    return (hours * 60) + minutes


def minutes_to_time(total_minutes: int) -> str:
    hours = max(0, total_minutes // 60)
    minutes = max(0, total_minutes % 60)
    return f"{hours:02d}:{minutes:02d}"


def floor_to_half_hour(total_minutes: int) -> int:
    return (total_minutes // 30) * 30


def ceil_to_half_hour(total_minutes: int) -> int:
    return ((total_minutes + 29) // 30) * 30


def appointment_duration_minutes(business: dict, appointment: dict) -> int:
    service_lookup = service_map(business)
    service_id = str(appointment.get("servicio_id") or "").strip()
    if service_id and service_id in service_lookup:
        duration = int(service_lookup[service_id].get("duration_minutes") or 0)
        if duration > 0:
            return duration

    service_name = str(appointment.get("servicio") or "").strip()
    if service_name:
        for service in business.get("services", []):
            if service.get("name") == service_name:
                duration = int(service.get("duration_minutes") or 0)
                if duration > 0:
                    return duration

    return 45


def format_visual_day_title(date_iso: str) -> str:
    parsed = date.fromisoformat(date_iso)
    return f"{WEEKDAY_LABELS[parsed.weekday()]} {parsed.strftime('%d/%m')}"


def build_visual_planner(
    appointments: list[dict],
    *,
    business: dict,
    active_filter: str,
    focus_date: str | None,
    month_token: str,
    current_path: str,
) -> dict:
    base_day = date.fromisoformat(focus_date or business_today(business))
    visible_days = [base_day + timedelta(days=offset) for offset in range(3)]
    visible_day_keys = {day.isoformat() for day in visible_days}
    appointments_by_date: dict[str, list[dict]] = {day.isoformat(): [] for day in visible_days}

    for appointment in appointments:
        appointment_date = str(appointment.get("fecha") or "")
        if appointment_date in visible_day_keys:
            appointments_by_date[appointment_date].append(appointment)

    start_candidates: list[int] = []
    end_candidates: list[int] = []
    for day_value in visible_days:
        day_iso = day_value.isoformat()
        schedule_range = parse_schedule_range(business_schedule_for_date(day_iso, business))
        if schedule_range:
            start_candidates.append(schedule_range[0])
            end_candidates.append(schedule_range[1])
        for appointment in appointments_by_date[day_iso]:
            start_min = time_to_minutes(str(appointment.get("hora") or "09:00"))
            duration = appointment_duration_minutes(business, appointment)
            start_candidates.append(start_min)
            end_candidates.append(start_min + duration)

    planner_start = floor_to_half_hour(min(start_candidates or [9 * 60]))
    planner_end = ceil_to_half_hour(max(end_candidates or [19 * 60]))
    if planner_end - planner_start < 8 * 60:
        planner_end = planner_start + (8 * 60)

    visual_slots: list[dict[str, str | bool]] = []
    for minute in range(planner_start, planner_end, 30):
        label = minutes_to_time(minute) if minute % 60 == 0 else ""
        visual_slots.append(
            {
                "time": minutes_to_time(minute),
                "label": label,
                "major": minute % 60 == 0,
            }
        )

    planner_days: list[dict] = []
    for day_value in visible_days:
        day_iso = day_value.isoformat()
        schedule_label = business_schedule_for_date(day_iso, business)
        day_items: list[dict] = []
        for appointment in appointments_by_date[day_iso]:
            start_minutes = time_to_minutes(str(appointment.get("hora") or "09:00"))
            duration = appointment_duration_minutes(business, appointment)
            span = max(1, (duration + 29) // 30)
            start_row = max(1, ((start_minutes - planner_start) // 30) + 1)
            end_time = minutes_to_time(start_minutes + duration)
            day_items.append(
                {
                    **appointment,
                    "visual_start_row": start_row,
                    "visual_span": span,
                    "time_range": f"{appointment.get('hora')} - {end_time}",
                    "edit_href": f"/citas/{appointment['id']}/editar?return_to={current_path}",
                }
            )

        planner_days.append(
            {
                "iso": day_iso,
                "title": format_visual_day_title(day_iso),
                "subtitle": MONTH_LABELS[day_value.month - 1],
                "schedule_label": schedule_label,
                "is_today": day_iso == business_today(business),
                "is_focus": day_iso == focus_date if focus_date else day_iso == business_today(business),
                "count": len(day_items),
                "appointments": sorted(day_items, key=lambda item: (item["hora"], item["id"])),
                "is_closed": schedule_label == "cerrado",
                "new_href": f"/citas/nueva?return_to={current_path}&fecha={day_iso}",
            }
        )

    return {
        "slots": visual_slots,
        "slot_count": len(visual_slots),
        "days": planner_days,
    }


def login_form_context(
    request: Request,
    *,
    business: dict,
    next_path: str,
    error: str | None = None,
    logged_out: bool = False,
) -> dict[str, Any]:
    return {
        "request": request,
        "business": business,
        "next_path": next_path,
        "error": error,
        "logged_out": logged_out,
        "active_page": "login",
    }
