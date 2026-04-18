from __future__ import annotations

from pathlib import Path
from typing import Any

from .appointment_service import AppointmentServiceError, create_customer_appointment
from .chat_channels import reset_appointment_collection, should_preserve_channel_contact
from .chat_state import (
    ConversationState,
    clear_pending_clarification,
    clear_pending_offer,
    pick_variant,
    set_pending_service_clarification,
    set_recent_completion,
)
from .chat_text import (
    contains_affirmative,
    contains_negative,
    extract_identity_name,
    extract_name,
    extract_phone,
    is_affirmative,
    is_negative,
)
from .datetime_parser import parse_datetime
from .repositories import find_customer_by_phone
from .service_catalog import analyze_service_request


def update_service_from_message(
    appointment: dict[str, str],
    message: str,
    business: dict[str, Any],
    expected_field: str | None,
) -> None:
    result = analyze_service_request(
        message,
        business,
        allow_modifier_only=expected_field == "service",
    )

    if result.status == "matched" and result.matched_service:
        appointment["service"] = result.matched_service["name"]
        appointment["service_id"] = str(result.matched_service.get("id") or "").strip()
        appointment.pop("service_error", None)
        return

    if result.needs_clarification and result.clarification:
        appointment.pop("service", None)
        appointment.pop("service_id", None)
        appointment["service_error"] = result.clarification
        return

    if expected_field == "service" and message.strip() and not extract_identity_name(message):
        appointment.pop("service", None)
        appointment.pop("service_id", None)
        appointment["service_error"] = (
            "No veo ese servicio en la configuración actual. "
            "Dime uno de los servicios disponibles y te ayudo."
        )


def update_appointment_from_message(
    appointment: dict[str, str],
    message: str,
    business: dict[str, Any],
    expected_field: str | None,
) -> None:
    explicit_identity_name = extract_identity_name(message)

    phone = extract_phone(message)
    if phone:
        appointment["phone"] = phone

    parsed = parse_datetime(
        message,
        timezone=business.get("timezone", "Atlantic/Canary"),
        expected_field=expected_field,
        has_date_context=bool(appointment.get("date")),
    )
    if parsed.date_error:
        appointment["date_error"] = parsed.date_error
    else:
        appointment.pop("date_error", None)
        if parsed.date_value:
            appointment["date"] = parsed.date_value

    if parsed.time_error:
        appointment["time_error"] = parsed.time_error
    else:
        appointment.pop("time_error", None)
        if parsed.time_value:
            appointment["time"] = parsed.time_value
        if parsed.part_of_day:
            appointment["part_of_day"] = parsed.part_of_day

    if expected_field == "date" and message.strip() and not appointment.get("date") and not parsed.date_error:
        appointment["date_error"] = "No puedo resolver esa fecha. Dime un día concreto, por ejemplo 'mañana', 'este viernes' o '18/04'."

    if (
        expected_field == "time"
        and message.strip()
        and not appointment.get("time")
        and not phone
        and not parsed.part_of_day
    ):
        appointment["time_error"] = "Para dejarlo bien apuntado en la agenda necesito una hora concreta, por ejemplo 10:00 o 17:30."

    update_service_from_message(appointment, message, business, expected_field)

    if explicit_identity_name:
        appointment["name"] = explicit_identity_name

    should_try_loose_name = (
        expected_field in {"slot", "date", "time", "phone"}
        and not phone
        and not parsed.date_value
        and not parsed.time_value
        and not parsed.part_of_day
    )
    name = extract_name(message, expected_field == "name" or should_try_loose_name)
    if name:
        appointment["name"] = name


def missing_fields(state: ConversationState) -> list[str]:
    appointment = state.appointment
    if not appointment.get("date") and not appointment.get("time"):
        return ["slot"]

    fields: list[str] = []
    if not appointment.get("date"):
        fields.append("date")
    if not appointment.get("time"):
        fields.append("time")
    if not appointment.get("service"):
        fields.append("service")
    if not appointment.get("phone"):
        fields.append("phone")
    if not state.known_customer and not appointment.get("name"):
        fields.append("name")
    return fields


def next_missing_field(state: ConversationState) -> str | None:
    fields = missing_fields(state)
    return fields[0] if fields else None


def question_for(field: str) -> str:
    questions = {
        "slot": "¿Qué día y hora te vendría bien? Por ejemplo: mañana a las 17:00 o este viernes a las 12:30.",
        "date": "¿Qué día quieres la cita?",
        "time": "¿Qué hora te viene bien para dejarlo en la agenda? Por ejemplo: 10:00 o 17:30.",
        "phone": "Déjame un teléfono de contacto y lo dejamos apuntado.",
        "name": "Ese teléfono todavía no lo tengo en la agenda. ¿A nombre de quién lo dejamos?",
        "service": "¿Qué servicio te apunto?",
    }
    return questions[field]


def question_for_state(field: str, state: ConversationState) -> str:
    appointment = state.appointment
    remaining_fields = missing_fields(state)
    if len(remaining_fields) == 1:
        compact_questions = {
            "time": "Perfecto. Solo me falta la hora.",
            "phone": "Perfecto. Solo me falta un teléfono de contacto.",
            "name": "Perfecto. Solo me falta el nombre.",
            "service": "Perfecto. Solo me falta saber qué servicio quieres.",
            "date": "Perfecto. Solo me falta el día.",
            "slot": "Perfecto. Solo me falta el día y la hora.",
        }
        if field in compact_questions:
            return compact_questions[field]
    if field == "time" and appointment.get("date") and appointment.get("part_of_day"):
        return (
            f"Perfecto, te lo preparo para {appointment['date']} "
            f"por la {appointment['part_of_day']}. Para dejarlo bien en la agenda, dime una hora aproximada."
        )
    if field == "time" and appointment.get("date"):
        return f"Perfecto, te lo preparo para {appointment['date']}. ¿A qué hora lo dejamos?"
    return question_for(field)


def captured_fields_prefix(
    *,
    state: ConversationState,
    added_fields: list[str],
    found_existing_customer: bool,
) -> str:
    if found_existing_customer and state.known_customer and not state.customer_identity_uncertain:
        return f"Perfecto, ya te tengo en la agenda como {state.known_customer['nombre']}. "

    visible_labels = {
        "date": "el día",
        "time": "la hora",
        "phone": "el teléfono",
        "name": "el nombre",
        "service": "el servicio",
    }
    labels = [visible_labels[field] for field in added_fields if field in visible_labels]
    if not labels:
        return ""
    if len(labels) == 1:
        return f"Perfecto, ya tengo {labels[0]}. "
    if len(labels) == 2:
        return f"Perfecto, ya tengo {labels[0]} y {labels[1]}. "
    return f"Perfecto, ya tengo {', '.join(labels[:-1])} y {labels[-1]}. "


def sync_customer_from_phone(state: ConversationState, db_path: Path) -> bool:
    phone = state.appointment.get("phone")
    if not phone or state.known_customer:
        return False

    customer = find_customer_by_phone(db_path, phone)
    if not customer:
        return False

    state.known_customer = customer
    state.appointment["name"] = customer["nombre"]
    state.appointment["customer_id"] = str(customer["id"])
    return True


def finish_appointment(
    state: ConversationState,
    business: dict[str, Any],
    db_path: Path,
) -> dict[str, Any]:
    appointment = state.appointment
    try:
        result = create_customer_appointment(
            db_path,
            business=business,
            customer_name=appointment["name"],
            customer_phone=appointment["phone"],
            date=appointment["date"],
            time=appointment["time"],
            part_of_day=appointment.get("part_of_day"),
            service_id=appointment.get("service_id"),
            service=appointment["service"],
        )
    except AppointmentServiceError as exc:
        if exc.field == "date":
            appointment.pop("date", None)
            state.expected_field = "date"
        elif exc.field == "service":
            appointment.pop("service", None)
            appointment.pop("service_id", None)
            state.expected_field = "service"
        elif exc.field == "phone":
            appointment.pop("phone", None)
            state.expected_field = "phone"
        else:
            appointment.pop("time", None)
            state.expected_field = "time"
        return {
            "reply": exc.message,
            "intent": "appointment_capture",
            "appointment_created": False,
        }
    customer = result["customer"]
    customer_created = bool(result["customer_created"])
    db_appointment = result["appointment"]

    known_customer = state.known_customer
    identity_uncertain = state.customer_identity_uncertain

    state.collecting_appointment = False
    state.appointment = {}
    state.known_customer = known_customer if should_preserve_channel_contact(state) else None
    state.expected_field = None
    clear_pending_clarification(state)
    clear_pending_offer(state)
    set_recent_completion(
        state,
        date=str(db_appointment["fecha"]),
        time=str(db_appointment["hora"]),
        service=str(db_appointment["servicio"]),
    )

    if customer_created:
        reply = (
            f"Ya he dejado creada la ficha de {customer['nombre']} y la cita pedida "
            f"para {db_appointment['fecha']} a las {db_appointment['hora']} por {db_appointment['servicio']}. "
            "Ahora mismo queda pendiente de confirmación."
        )
    elif identity_uncertain:
        reply = (
            f"Perfecto. Ya te he dejado pedida la cita para {db_appointment['fecha']} "
            f"a las {db_appointment['hora']} por {db_appointment['servicio']}. "
            "Ahora mismo queda pendiente de confirmación."
        )
    else:
        reply = (
            f"Perfecto, {customer['nombre']}. Ya te he dejado pedida la cita "
            f"para {db_appointment['fecha']} a las {db_appointment['hora']} por {db_appointment['servicio']}. "
            "Ahora mismo queda pendiente de confirmación."
        )

    return {
        "reply": reply,
        "intent": "appointment_created",
        "appointment_created": True,
        "customer_created": customer_created,
        "appointment": db_appointment,
    }


def continue_appointment_flow(
    message: str,
    business: dict[str, Any],
    state: ConversationState,
    db_path: Path,
) -> dict[str, Any]:
    previous_appointment = dict(state.appointment)
    pending = state.pending_clarification
    if state.expected_field == "service" and pending and pending.get("intent") == "appointment_capture":
        pending_result = analyze_service_request(
            message,
            business,
            allow_modifier_only=True,
            allowed_service_ids=set(pending.get("service_ids", [])),
        )
        if pending_result.status == "matched" and pending_result.matched_service:
            state.appointment["service"] = pending_result.matched_service["name"]
            state.appointment["service_id"] = str(pending_result.matched_service.get("id") or "").strip()
            state.appointment.pop("service_error", None)
            clear_pending_clarification(state)
        elif pending_result.needs_clarification and pending_result.clarification:
            set_pending_service_clarification(state, result=pending_result, intent="appointment_capture")
            return {
                "reply": pending_result.clarification,
                "intent": "appointment_capture",
                "appointment_created": False,
                "missing_field": "service",
            }

    update_appointment_from_message(state.appointment, message, business, state.expected_field)
    found_existing_customer = sync_customer_from_phone(state, db_path)
    tracked_fields = ("date", "time", "phone", "name", "service")
    added_fields = [
        field
        for field in tracked_fields
        if state.appointment.get(field) and not previous_appointment.get(field)
    ]

    if state.appointment.get("date_error") and not state.appointment.get("date") and not added_fields:
        state.expected_field = "date"
        return {
            "reply": state.appointment.pop("date_error"),
            "intent": "appointment_capture",
            "appointment_created": False,
            "missing_field": "date",
        }

    if state.appointment.get("time_error") and not state.appointment.get("time") and not added_fields:
        state.expected_field = "time"
        return {
            "reply": state.appointment.pop("time_error"),
            "intent": "appointment_capture",
            "appointment_created": False,
            "missing_field": "time",
        }

    if state.appointment.get("service_error") and not state.appointment.get("service"):
        service_result = analyze_service_request(
            message,
            business,
            allow_modifier_only=state.expected_field == "service",
        )
        if service_result.needs_clarification:
            set_pending_service_clarification(state, result=service_result, intent="appointment_capture")
        state.expected_field = "service"
        return {
            "reply": state.appointment.pop("service_error"),
            "intent": "appointment_capture",
            "appointment_created": False,
            "missing_field": "service",
        }

    missing = next_missing_field(state)
    if missing:
        state.expected_field = missing
        prefix = captured_fields_prefix(
            state=state,
            added_fields=added_fields,
            found_existing_customer=found_existing_customer,
        )
        question = question_for_state(missing, state)
        if prefix and question.startswith("Perfecto. "):
            question = question.removeprefix("Perfecto. ")
        elif prefix and question.startswith("Perfecto, "):
            question = question.removeprefix("Perfecto, ")
        if question:
            question = question[0].upper() + question[1:]
        return {
            "reply": f"{prefix}{question}",
            "intent": "appointment_capture",
            "appointment_created": False,
            "missing_field": missing,
        }

    return finish_appointment(state, business, db_path)


def resolve_pending_offer(
    message: str,
    business: dict[str, Any],
    state: ConversationState,
    db_path: Path,
) -> dict[str, Any] | None:
    pending = state.pending_offer
    if not pending or pending.get("kind") != "booking_offer":
        return None

    if is_negative(message) or contains_negative(message):
        clear_pending_offer(state)
        return {
            "reply": "Perfecto. Si te viene bien, dime otra cosa y te ayudo.",
            "intent": "booking_declined",
            "appointment_created": False,
        }

    parsed = parse_datetime(
        message,
        timezone=business.get("timezone", "Atlantic/Canary"),
        has_date_context=False,
    )
    service_result = analyze_service_request(message, business)
    has_booking_data = bool(
        parsed.date_value
        or parsed.time_value
        or parsed.part_of_day
        or extract_phone(message)
        or extract_identity_name(message)
        or service_result.has_signal
    )

    if is_affirmative(message) or contains_affirmative(message) or has_booking_data:
        clear_pending_clarification(state)
        reset_appointment_collection(state)
        service_name = str(pending.get("service") or "").strip()
        if service_name:
            state.appointment["service"] = service_name
        for key, value in (pending.get("prefill") or {}).items():
            if value:
                state.appointment[key] = value
        clear_pending_offer(state)
        return continue_appointment_flow(message, business, state, db_path)

    state.pending_offer_turns -= 1
    if state.pending_offer_turns <= 0:
        clear_pending_offer(state)
    return None
