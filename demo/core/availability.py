from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type, timedelta
from pathlib import Path
from typing import Any

from .repositories import (
    get_service_config,
    get_service_config_by_name,
    has_active_appointment_at,
    list_active_appointments_on_date,
)


@dataclass(frozen=True)
class AvailabilityDecision:
    available: bool
    reason: str | None = None
    suggestions: tuple[str, ...] = field(default_factory=tuple)


def _to_minutes(raw_time: str) -> int:
    hours, minutes = raw_time.split(":", 1)
    return (int(hours) * 60) + int(minutes)


def _intervals_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and end_a > start_b


def _service_definition(
    service_name: str | None,
    business: dict[str, Any],
    db_path: Path,
    *,
    service_id: str | None = None,
    connection: Any | None = None,
) -> dict[str, Any] | None:
    if service_id:
        service = get_service_config(db_path, service_id, connection=connection)
        if service:
            return service
    for service in business.get("services", []):
        if service.get("name") == service_name:
            return service
    return get_service_config_by_name(db_path, service_name, connection=connection)


def _default_duration_minutes(business: dict[str, Any]) -> int:
    operational_rules = business.get("operational_rules", {})
    try:
        duration = int(operational_rules.get("default_slot_minutes") or 30)
    except (TypeError, ValueError):
        duration = 30
    return max(5, duration)


def _category_capacity(service_category: str | None, business: dict[str, Any]) -> int:
    if not service_category:
        return 1

    operational_rules = business.get("operational_rules", {})
    configured_capacity = operational_rules.get("category_capacity", {}).get(service_category)
    try:
        configured_capacity_value = int(configured_capacity) if configured_capacity is not None else 0
    except (TypeError, ValueError):
        configured_capacity_value = 0

    active_staff = [
        member
        for member in business.get("staff", [])
        if member.get("active", True) and service_category in member.get("service_categories", [])
    ]
    active_staff_count = len(active_staff)
    if configured_capacity_value > 0 and active_staff_count > 0:
        return min(configured_capacity_value, active_staff_count)
    if active_staff_count > 0:
        return active_staff_count
    if configured_capacity_value > 0:
        return 0
    return 1


def _category_name(service_category: str | None, business: dict[str, Any]) -> str:
    if not service_category:
        return "ese servicio"
    for category in business.get("service_categories", []):
        if category.get("id") == service_category:
            return str(category.get("name") or "ese servicio")
    return service_category.replace("_", " ")


def _daily_hours(date: str, business: dict[str, Any]) -> tuple[int, int] | None:
    from datetime import date as _date

    hours = business.get("hours", {})
    parsed = _date.fromisoformat(date)
    if parsed.weekday() <= 4:
        raw_schedule = str(hours.get("monday_friday") or "")
    elif parsed.weekday() == 5:
        raw_schedule = str(hours.get("saturday") or "")
    else:
        raw_schedule = str(hours.get("sunday") or "")

    if not raw_schedule or raw_schedule == "cerrado":
        return None

    open_time, _, close_time = raw_schedule.partition("-")
    if not open_time or not close_time:
        return None
    return _to_minutes(open_time.strip()), _to_minutes(close_time.strip())


def _format_minutes(total_minutes: int) -> str:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def _format_slot_label(slot_date: str, time_value: str, requested_date: str) -> str:
    if slot_date == requested_date:
        return time_value
    return f"{slot_date} {time_value}"


def _part_of_day_label(preferred_part_of_day: str | None) -> str | None:
    if not preferred_part_of_day:
        return None
    if preferred_part_of_day == "mañana":
        return "por la mañana"
    if preferred_part_of_day == "tarde":
        return "por la tarde"
    if preferred_part_of_day == "noche":
        return "por la noche"
    if preferred_part_of_day == "mediodía":
        return "al mediodía"
    return None


def _join_with_or(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} o {items[1]}"
    return f"{', '.join(items[:-1])} o {items[-1]}"


def _suggestion_offer_text(suggestions: tuple[str, ...], requested_date: str) -> str:
    if not suggestions:
        return ""

    parsed: list[tuple[str | None, str]] = []
    for item in suggestions:
        parts = item.split(" ", 1)
        if len(parts) == 2 and len(parts[0]) == 10 and parts[0][4] == "-" and parts[0][7] == "-":
            parsed.append((parts[0], parts[1]))
        else:
            parsed.append((requested_date, item))

    unique_dates = {slot_date for slot_date, _ in parsed if slot_date}
    if len(unique_dates) == 1:
        slot_date = next(iter(unique_dates))
        times = [time_value for _, time_value in parsed]
        if slot_date == requested_date:
            return f"a las {_join_with_or(times)}"
        return f"el {slot_date} a las {_join_with_or(times)}"

    return _join_with_or(list(suggestions))


def _preferred_period_message(
    *,
    preferred_part_of_day: str | None,
    suggestions: tuple[str, ...],
    requested_date: str,
) -> str | None:
    label = _part_of_day_label(preferred_part_of_day)
    if not label:
        return None
    base = f"No tengo hueco ese día {label}."
    if suggestions:
        return f"{base} Te puedo atender {_suggestion_offer_text(suggestions, requested_date)}."
    return base


def _slot_matches_part_of_day(total_minutes: int, preferred_part_of_day: str | None) -> bool:
    if not preferred_part_of_day:
        return True
    if preferred_part_of_day == "mañana":
        return total_minutes < 14 * 60
    if preferred_part_of_day == "mediodía":
        return 12 * 60 <= total_minutes < 16 * 60
    if preferred_part_of_day == "tarde":
        return 15 * 60 <= total_minutes < 21 * 60
    if preferred_part_of_day == "noche":
        return total_minutes >= 20 * 60
    return True


def _available_slot_minutes_for_date(
    db_path: Path,
    *,
    business: dict[str, Any],
    date: str,
    requested_start: int,
    requested_duration: int,
    service: str,
    service_id: str | None,
    exclude_appointment_id: int | None,
    exclude_requested_start: bool,
    preferred_part_of_day: str | None,
) -> list[int]:
    day_hours = _daily_hours(date, business)
    if not day_hours:
        return []

    open_minutes, close_minutes = day_hours
    last_start = close_minutes - requested_duration
    if last_start < open_minutes:
        return []

    candidate_minutes: list[int] = []
    current = open_minutes
    while current <= last_start:
        if not exclude_requested_start or current != requested_start:
            candidate_minutes.append(current)
        current += 15

    available_slots: list[int] = []
    for candidate in candidate_minutes:
        decision = check_basic_availability(
            db_path,
            business=business,
            date=date,
            time=_format_minutes(candidate),
            service=service,
            service_id=service_id,
            exclude_appointment_id=exclude_appointment_id,
            suggest_alternatives=False,
        )
        if decision.available:
            available_slots.append(candidate)

    available_slots.sort(
        key=lambda candidate: (
            abs(candidate - requested_start),
            0 if candidate >= requested_start else 1,
            candidate,
        )
    )
    return available_slots


def _alternative_suggestions(
    db_path: Path,
    *,
    business: dict[str, Any],
    date: str,
    requested_start: int,
    requested_duration: int,
    service: str,
    service_id: str | None,
    exclude_appointment_id: int | None,
    preferred_part_of_day: str | None,
) -> tuple[str, ...]:
    requested_day = date_type.fromisoformat(date)
    preferred_suggestions: list[str] = []
    fallback_suggestions: list[str] = []

    def add_suggestions(slot_date: str, candidate_slots: list[int]) -> None:
        for candidate in candidate_slots:
            label = _format_slot_label(slot_date, _format_minutes(candidate), date)
            target = (
                preferred_suggestions
                if _slot_matches_part_of_day(candidate, preferred_part_of_day)
                else fallback_suggestions
            )
            if label not in target:
                target.append(label)

    same_day_slots = _available_slot_minutes_for_date(
        db_path,
        business=business,
        date=date,
        requested_start=requested_start,
        requested_duration=requested_duration,
        service=service,
        service_id=service_id,
        exclude_appointment_id=exclude_appointment_id,
        exclude_requested_start=True,
        preferred_part_of_day=preferred_part_of_day,
    )
    add_suggestions(date, same_day_slots)
    if len(preferred_suggestions) >= 3:
        return tuple(preferred_suggestions[:3])

    for day_offset in range(1, 8):
        candidate_date = (requested_day + timedelta(days=day_offset)).isoformat()
        candidate_slots = _available_slot_minutes_for_date(
            db_path,
            business=business,
            date=candidate_date,
            requested_start=requested_start,
            requested_duration=requested_duration,
            service=service,
            service_id=service_id,
            exclude_appointment_id=exclude_appointment_id,
            exclude_requested_start=False,
            preferred_part_of_day=preferred_part_of_day,
        )
        add_suggestions(candidate_date, candidate_slots[:3])
        if len(preferred_suggestions) >= 3:
            return tuple(preferred_suggestions[:3])

    combined = preferred_suggestions + [label for label in fallback_suggestions if label not in preferred_suggestions]
    return tuple(combined[:3])


def check_basic_availability(
    db_path: Path,
    *,
    business: dict[str, Any],
    date: str,
    time: str,
    service: str,
    service_id: str | None = None,
    exclude_appointment_id: int | None = None,
    suggest_alternatives: bool = True,
    preferred_part_of_day: str | None = None,
    connection: Any | None = None,
) -> AvailabilityDecision:
    requested_service = _service_definition(
        service,
        business,
        db_path,
        service_id=service_id,
        connection=connection,
    )
    if not requested_service:
        if has_active_appointment_at(
            db_path,
            date=date,
            time=time,
            exclude_appointment_id=exclude_appointment_id,
            connection=connection,
        ):
            return AvailabilityDecision(
                available=False,
                reason=(
                    "No puedo confirmar ese hueco porque ya hay una cita activa "
                    "registrada a esa hora. ¿Qué otra hora o franja prefieres?"
                ),
            )
        return AvailabilityDecision(available=True)

    requested_category = str(requested_service.get("category") or "").strip() or None
    requested_duration = int(requested_service.get("duration_minutes") or _default_duration_minutes(business))
    requested_start = _to_minutes(time)
    requested_end = requested_start + requested_duration
    day_hours = _daily_hours(date, business)

    if not day_hours:
        suggestions = ()
        if suggest_alternatives:
            suggestions = _alternative_suggestions(
                db_path,
                business=business,
                date=date,
                requested_start=requested_start,
                requested_duration=requested_duration,
                service=service,
                service_id=service_id,
                exclude_appointment_id=exclude_appointment_id,
                preferred_part_of_day=preferred_part_of_day,
            )
        preferred_message = _preferred_period_message(
            preferred_part_of_day=preferred_part_of_day,
            suggestions=suggestions,
            requested_date=date,
        )
        if preferred_message:
            return AvailabilityDecision(
                available=False,
                reason=preferred_message,
                suggestions=suggestions,
            )
        suggestion_text = f" Te puedo proponer {', '.join(suggestions)}." if suggestions else ""
        return AvailabilityDecision(
            available=False,
            reason=f"No puedo confirmar esa cita porque el {date} estamos cerrados.{suggestion_text}",
            suggestions=suggestions,
        )

    open_minutes, close_minutes = day_hours
    if requested_start < open_minutes or requested_end > close_minutes:
        suggestions = ()
        if suggest_alternatives:
            suggestions = _alternative_suggestions(
                db_path,
                business=business,
                date=date,
                requested_start=requested_start,
                requested_duration=requested_duration,
                service=service,
                service_id=service_id,
                exclude_appointment_id=exclude_appointment_id,
                preferred_part_of_day=preferred_part_of_day,
            )
        preferred_message = _preferred_period_message(
            preferred_part_of_day=preferred_part_of_day,
            suggestions=suggestions,
            requested_date=date,
        )
        if preferred_message:
            return AvailabilityDecision(
                available=False,
                reason=preferred_message,
                suggestions=suggestions,
            )
        suggestion_text = f" Te puedo proponer {', '.join(suggestions)}." if suggestions else ""
        return AvailabilityDecision(
            available=False,
            reason=(
                f"No puedo confirmar esa hora porque el {date} trabajamos entre "
                f"{_format_minutes(open_minutes)} y {_format_minutes(close_minutes)}.{suggestion_text}"
            ),
            suggestions=suggestions,
        )

    effective_capacity = _category_capacity(requested_category, business)
    if effective_capacity <= 0:
        return AvailabilityDecision(
            available=False,
            reason=(
                "No puedo confirmar ese servicio porque esa categoría no tiene capacidad activa configurada. "
                "Revisa personal o prueba otra opción."
            ),
        )

    overlapping = 0
    for appointment in list_active_appointments_on_date(
        db_path,
        date=date,
        exclude_appointment_id=exclude_appointment_id,
        connection=connection,
    ):
        appointment_service = _service_definition(
            str(appointment.get("servicio") or ""),
            business,
            db_path,
            service_id=str(appointment.get("servicio_id") or "").strip() or None,
            connection=connection,
        )
        appointment_category = str(appointment_service.get("category") or "").strip() if appointment_service else ""
        if requested_category and appointment_category != requested_category:
            continue
        if not requested_category and not appointment_category:
            if str(appointment.get("hora") or "") == time:
                overlapping += 1
            continue

        appointment_duration = int(
            (appointment_service or {}).get("duration_minutes") or _default_duration_minutes(business)
        )
        appointment_start = _to_minutes(str(appointment.get("hora") or "00:00"))
        appointment_end = appointment_start + appointment_duration

        if _intervals_overlap(requested_start, requested_end, appointment_start, appointment_end):
            overlapping += 1

    if overlapping >= effective_capacity:
        category_name = _category_name(requested_category, business)
        suggestions = ()
        if suggest_alternatives:
            suggestions = _alternative_suggestions(
                db_path,
                business=business,
                date=date,
                requested_start=requested_start,
                requested_duration=requested_duration,
                service=service,
                service_id=service_id,
                exclude_appointment_id=exclude_appointment_id,
                preferred_part_of_day=preferred_part_of_day,
            )
        preferred_message = _preferred_period_message(
            preferred_part_of_day=preferred_part_of_day,
            suggestions=suggestions,
            requested_date=date,
        )
        if preferred_message:
            return AvailabilityDecision(
                available=False,
                reason=preferred_message,
                suggestions=suggestions,
            )
        suggestion_text = ""
        if suggestions:
            suggestion_text = f" Te puedo proponer {', '.join(suggestions)}."
        return AvailabilityDecision(
            available=False,
            reason=(
                f"No puedo confirmar esa hora porque {category_name.lower()} ya tiene la capacidad ocupada "
                f"en esa franja. ¿Qué otra hora prefieres?{suggestion_text}"
            ),
            suggestions=suggestions,
        )

    return AvailabilityDecision(available=True)
