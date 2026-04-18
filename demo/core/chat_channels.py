from __future__ import annotations

from pathlib import Path

from .chat_state import ConversationState, pick_variant
from .chat_text import extract_identity_name, first_name, normalize
from .repositories import find_customer_by_phone, normalize_phone


def should_preserve_channel_contact(state: ConversationState) -> bool:
    return state.channel_type == "whatsapp" and bool(state.incoming_phone)


def reset_appointment_collection(state: ConversationState) -> None:
    state.collecting_appointment = True
    state.appointment = {}
    state.expected_field = None

    if should_preserve_channel_contact(state):
        state.appointment["phone"] = str(state.incoming_phone or "")
        if state.customer_identity_uncertain and state.customer_name_override:
            state.appointment["name"] = state.customer_name_override
            state.appointment.pop("customer_id", None)
        elif state.known_customer:
            state.appointment["name"] = str(state.known_customer.get("nombre") or "")
            state.appointment["customer_id"] = str(state.known_customer.get("id") or "")


def apply_channel_context(
    state: ConversationState,
    *,
    channel_type: str | None,
    incoming_phone: str | None,
    db_path: Path,
) -> bool:
    if channel_type:
        state.channel_type = channel_type

    if state.channel_type != "whatsapp":
        return False

    normalized_phone = normalize_phone(incoming_phone or "")
    if not normalized_phone:
        return False

    if state.incoming_phone and state.incoming_phone != normalized_phone:
        state.channel_customer_greeted = False
        state.customer_identity_uncertain = False
        state.customer_name_override = None
        state.known_customer = None

    state.incoming_phone = normalized_phone
    state.appointment.setdefault("phone", normalized_phone)

    customer = find_customer_by_phone(db_path, normalized_phone)
    if not customer:
        if not state.customer_identity_uncertain:
            state.known_customer = None
            state.appointment.pop("customer_id", None)
        return False

    just_recognized = not state.channel_customer_greeted
    state.known_customer = customer
    if not state.customer_identity_uncertain:
        state.appointment["name"] = str(customer.get("nombre") or "")
        state.appointment["customer_id"] = str(customer.get("id") or "")
    return just_recognized


def apply_identity_hint_from_message(state: ConversationState, message: str) -> bool:
    if not should_preserve_channel_contact(state):
        return False

    explicit_name = extract_identity_name(message)
    if not explicit_name:
        return False

    known_name = str((state.known_customer or {}).get("nombre") or "")
    if known_name and normalize(explicit_name) == normalize(known_name):
        return False

    state.customer_identity_uncertain = True
    state.customer_name_override = explicit_name
    state.channel_customer_greeted = True
    state.appointment["phone"] = str(state.incoming_phone or "")
    state.appointment["name"] = explicit_name
    state.appointment.pop("customer_id", None)
    return True


def decorate_whatsapp_reply(
    state: ConversationState,
    *,
    intent: str,
    reply: str,
) -> str:
    if state.channel_type != "whatsapp":
        return reply

    if state.customer_identity_uncertain:
        return reply

    if not state.known_customer or state.channel_customer_greeted:
        return reply

    customer_name = first_name((state.known_customer or {}).get("nombre"))
    if not customer_name:
        return reply

    reply_normalized = normalize(reply)
    name_normalized = normalize(customer_name)
    if f"hola {name_normalized}" in reply_normalized or name_normalized in reply_normalized:
        state.channel_customer_greeted = True
        return reply

    if intent == "greeting":
        state.channel_customer_greeted = True
        return pick_variant(
            state,
            "whatsapp_known_greeting",
            (
                f"Hola {customer_name}, te tengo registrada. ¿En qué te ayudo?",
                f"Hola {customer_name}, dime qué necesitas y te ayudo.",
                f"Hola {customer_name}, puedo ayudarte con tu próxima cita o con cualquier duda.",
            ),
        )

    state.channel_customer_greeted = True
    prefix = pick_variant(
        state,
        "whatsapp_known_prefix",
        (
            f"Hola {customer_name}. ",
            f"Hola {customer_name}, ",
        ),
    )
    return f"{prefix}{reply}"
