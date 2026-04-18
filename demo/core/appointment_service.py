from __future__ import annotations

from datetime import date as date_type, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .availability import check_basic_availability
from .db import connection_scope
from .models import APPOINTMENT_STATES
from .repositories import (
    create_appointment,
    get_appointment,
    get_customer,
    get_or_create_customer,
    get_service_config,
    get_service_config_by_name,
    is_valid_phone,
    update_appointment,
)


class AppointmentServiceError(Exception):
    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


def _today_iso(business: dict[str, Any]) -> str:
    timezone = business.get("timezone", "Atlantic/Canary")
    return datetime.now(ZoneInfo(timezone)).date().isoformat()


def _validate_date(raw_date: str, *, business: dict[str, Any]) -> str:
    try:
        appointment_date = date_type.fromisoformat(raw_date.strip())
    except ValueError as exc:
        raise AppointmentServiceError("Indica una fecha válida para la cita.", field="date") from exc

    if appointment_date < date_type.fromisoformat(_today_iso(business)):
        raise AppointmentServiceError("No puedo guardar una cita en una fecha pasada.", field="date")
    return appointment_date.isoformat()


def _validate_time(raw_time: str) -> str:
    clean = raw_time.strip()
    try:
        datetime.strptime(clean, "%H:%M")
    except ValueError as exc:
        raise AppointmentServiceError("Indica una hora válida con formato HH:MM.", field="time") from exc
    return clean


def _validate_status(raw_status: str) -> str:
    status = raw_status.strip()
    if status not in APPOINTMENT_STATES:
        raise AppointmentServiceError("Elige un estado válido para la cita.", field="status")
    return status


def _resolve_service(
    db_path: Path,
    *,
    service_id: str | None,
    service_name: str | None,
    connection: Any,
) -> dict[str, Any]:
    service = None
    normalized_id = str(service_id or "").strip()
    if normalized_id:
        service = get_service_config(db_path, normalized_id, connection=connection)
    if not service and service_name:
        service = get_service_config_by_name(db_path, service_name, connection=connection)
    if not service:
        raise AppointmentServiceError("Elige un servicio para guardar la cita.", field="service")
    return service


def _resolve_customer_for_create(
    db_path: Path,
    *,
    customer_id: int | None,
    customer_name: str | None,
    customer_phone: str | None,
    business: dict[str, Any],
    connection: Any,
) -> tuple[dict[str, Any], bool]:
    if customer_id is not None:
        customer = get_customer(db_path, customer_id, connection=connection)
        if not customer:
            raise AppointmentServiceError(
                "No encuentro ese cliente. Elige uno de la lista o crea uno nuevo rápido.",
                field="customer_id",
            )
        return customer, False

    name = str(customer_name or "").strip()
    phone = str(customer_phone or "").strip()
    if not name or not phone:
        raise AppointmentServiceError(
            "Si no eliges un cliente existente, necesito al menos nombre y teléfono.",
            field="customer",
        )
    if not is_valid_phone(phone):
        raise AppointmentServiceError(
            "Indica un teléfono válido. Puedes escribirlo con espacios o +34 y lo normalizo al guardar.",
            field="phone",
        )

    return get_or_create_customer(
        db_path,
        name=name,
        phone=phone,
        timezone=business.get("timezone", "Atlantic/Canary"),
        connection=connection,
    )


def create_customer_appointment(
    db_path: Path,
    *,
    business: dict[str, Any],
    customer_id: int | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    date: str,
    time: str,
    service_id: str | None = None,
    service: str | None = None,
    status: str = "pendiente",
    notes: str | None = None,
    part_of_day: str | None = None,
) -> dict[str, Any]:
    with connection_scope(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        service_record = _resolve_service(
            db_path,
            service_id=service_id,
            service_name=service,
            connection=connection,
        )
        normalized_date = _validate_date(date, business=business)
        normalized_time = _validate_time(time)
        normalized_status = _validate_status(status)
        availability = check_basic_availability(
            db_path,
            business=business,
            date=normalized_date,
            time=normalized_time,
            service_id=str(service_record.get("id") or ""),
            service=str(service_record.get("name") or ""),
            preferred_part_of_day=part_of_day,
            connection=connection,
        )
        if not availability.available:
            raise AppointmentServiceError(
                availability.reason or "No puedo confirmar ese hueco ahora mismo.",
                field="time",
            )

        customer, customer_created = _resolve_customer_for_create(
            db_path,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            business=business,
            connection=connection,
        )
        appointment = create_appointment(
            db_path,
            customer_id=int(customer["id"]),
            date=normalized_date,
            time=normalized_time,
            part_of_day=part_of_day,
            service_id=str(service_record.get("id") or "") or None,
            service=str(service_record.get("name") or ""),
            status=normalized_status,
            notes=notes.strip() if notes else None,
            timezone=business.get("timezone", "Atlantic/Canary"),
            connection=connection,
        )
    return {
        "appointment": appointment,
        "customer": customer,
        "customer_created": customer_created,
    }


def update_customer_appointment(
    db_path: Path,
    *,
    business: dict[str, Any],
    appointment_id: int,
    date: str,
    time: str,
    service_id: str | None = None,
    service: str | None = None,
    status: str,
    notes: str | None = None,
    part_of_day: str | None = None,
) -> dict[str, Any]:
    with connection_scope(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = get_appointment(db_path, appointment_id, connection=connection)
        if not current:
            raise AppointmentServiceError("Cita no encontrada.", field="appointment")

        service_record = _resolve_service(
            db_path,
            service_id=service_id,
            service_name=service,
            connection=connection,
        )
        normalized_date = _validate_date(date, business=business)
        normalized_time = _validate_time(time)
        normalized_status = _validate_status(status)
        availability = check_basic_availability(
            db_path,
            business=business,
            date=normalized_date,
            time=normalized_time,
            service_id=str(service_record.get("id") or ""),
            service=str(service_record.get("name") or ""),
            exclude_appointment_id=appointment_id,
            preferred_part_of_day=part_of_day,
            connection=connection,
        )
        if not availability.available:
            raise AppointmentServiceError(
                availability.reason or "Ese hueco ya está ocupado.",
                field="time",
            )

        appointment = update_appointment(
            db_path,
            appointment_id=appointment_id,
            date=normalized_date,
            time=normalized_time,
            service_id=str(service_record.get("id") or "") or None,
            service=str(service_record.get("name") or ""),
            status=normalized_status,
            part_of_day=part_of_day,
            notes=notes.strip() if notes else None,
            connection=connection,
        )
        if not appointment:
            raise AppointmentServiceError("No he podido guardar los cambios de la cita.", field="appointment")
    return {
        "appointment": appointment,
        "customer_id": int(current["cliente_id"]),
    }
