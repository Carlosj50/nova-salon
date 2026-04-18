from __future__ import annotations

from pathlib import Path
from typing import Any

from .chat_booking import continue_appointment_flow, resolve_pending_offer
from .chat_channels import (
    apply_channel_context,
    apply_identity_hint_from_message,
    decorate_whatsapp_reply,
    reset_appointment_collection,
)
from .chat_state import (
    ConversationState,
    clear_pending_clarification,
    clear_pending_offer,
    clear_recent_completion,
    decay_recent_completion,
    pick_variant,
    set_pending_booking_offer,
    set_pending_generic_booking_offer,
    set_pending_service_clarification,
)
from .chat_text import (
    answer_hours,
    answer_location,
    booking_prefill_from_hours,
    detect_intent,
    looks_like_loose_customer_fragment,
    normalize,
)
from .service_catalog import analyze_service_request, list_prices, list_services, service_summary


def resolve_pending_service_clarification(
    message: str,
    business: dict[str, Any],
    state: ConversationState,
) -> dict[str, Any] | None:
    pending = state.pending_clarification
    if not pending or pending.get("kind") != "service":
        return None

    result = analyze_service_request(
        message,
        business,
        allow_modifier_only=True,
        allowed_service_ids=set(pending.get("service_ids", [])),
    )

    if result.status == "matched" and result.matched_service:
        service = result.matched_service
        clear_pending_clarification(state)
        intent = pending.get("intent", "services")
        if intent == "prices":
            set_pending_booking_offer(state, service.get("name"))
            booking_offer = pick_variant(
                state,
                "price_offer",
                (
                    "Si quieres, te dejo ya la cita pedida.",
                    "Si te viene bien, te dejo ya la cita pedida.",
                    "Si te encaja, te dejo ya la cita pedida.",
                ),
            )
            return {
                "reply": (
                    f"Te orientaría en {service_summary(service)} "
                    "El precio final puede cambiar un poco según valoración. "
                    f"{booking_offer}"
                ),
                "intent": "prices",
                "appointment_created": False,
            }
        set_pending_booking_offer(state, service.get("name"))
        service_offer = pick_variant(
            state,
            "service_offer",
            (
                "Sí, lo hacemos.",
                "Sí, ese servicio lo trabajamos.",
                "Sí, lo tenemos.",
            ),
        )
        booking_offer = pick_variant(
            state,
            "service_booking_offer",
            (
                "Si quieres, te dejo ya la cita pedida.",
                "Si te viene bien, te dejo ya la cita pedida.",
                "Si te encaja, te la dejo ya pedida.",
            ),
        )
        return {
            "reply": (
                f"{service_offer} {service_summary(service)} "
                f"{booking_offer}"
            ),
            "intent": "services",
            "appointment_created": False,
        }

    if result.needs_clarification and result.clarification:
        set_pending_service_clarification(state, result=result, intent=pending.get("intent", "services"))
        return {
            "reply": f"{result.clarification} Así te digo justo la opción correcta.",
            "intent": pending.get("intent", "services"),
            "appointment_created": False,
        }

    state.pending_clarification_turns -= 1
    if state.pending_clarification_turns <= 0:
        clear_pending_clarification(state)
    return None


def handle_message(
    message: str,
    business: dict[str, Any],
    state: ConversationState,
    db_path: Path,
    *,
    channel_type: str | None = None,
    incoming_phone: str | None = None,
) -> dict[str, Any]:
    state.turn_counter += 1
    decay_recent_completion(state)
    clean_message = message.strip()
    if not clean_message:
        return {
            "reply": "Escribe una pregunta o dime qué cita quieres reservar.",
            "intent": "empty",
            "appointment_created": False,
        }

    apply_channel_context(
        state,
        channel_type=channel_type,
        incoming_phone=incoming_phone,
        db_path=db_path,
    )

    identity_hint_applied = apply_identity_hint_from_message(state, clean_message)

    if state.collecting_appointment:
        result = continue_appointment_flow(clean_message, business, state, db_path)
        result["reply"] = decorate_whatsapp_reply(
            state,
            intent=result["intent"],
            reply=result["reply"],
        )
        return result

    pending_offer_resolution = resolve_pending_offer(clean_message, business, state, db_path)
    if pending_offer_resolution:
        state.last_intent = pending_offer_resolution["intent"]
        pending_offer_resolution["reply"] = decorate_whatsapp_reply(
            state,
            intent=pending_offer_resolution["intent"],
            reply=pending_offer_resolution["reply"],
        )
        return pending_offer_resolution

    pending_resolution = resolve_pending_service_clarification(clean_message, business, state)
    if pending_resolution:
        state.last_intent = pending_resolution["intent"]
        pending_resolution["reply"] = decorate_whatsapp_reply(
            state,
            intent=pending_resolution["intent"],
            reply=pending_resolution["reply"],
        )
        return pending_resolution

    intent = detect_intent(clean_message, business)
    state.last_intent = intent

    if identity_hint_applied and intent in {"fallback", "greeting"}:
        reply = "Perfecto, lo tengo en cuenta. Dime qué necesitas y te ayudo."
        return {
            "reply": reply,
            "intent": "identity_update",
            "appointment_created": False,
        }

    if (
        state.recent_completion
        and intent == "fallback"
        and looks_like_loose_customer_fragment(clean_message)
    ):
        recent = state.recent_completion
        return {
            "reply": decorate_whatsapp_reply(
                state,
                intent="recent_completion",
                reply=(
                f"La cita ya quedó apuntada para {recent['date']} a las {recent['time']}. "
                "Si quieres cambiar algo o pedir otra, dímelo."
                ),
            ),
            "intent": "recent_completion",
            "appointment_created": False,
        }

    if intent == "booking":
        clear_recent_completion(state)
        clear_pending_clarification(state)
        clear_pending_offer(state)
        reset_appointment_collection(state)
        result = continue_appointment_flow(clean_message, business, state, db_path)
        result["reply"] = decorate_whatsapp_reply(
            state,
            intent=result["intent"],
            reply=result["reply"],
        )
        return result

    if intent == "hours":
        clear_recent_completion(state)
        clear_pending_clarification(state)
        clear_pending_offer(state)
        prefill = booking_prefill_from_hours(clean_message, business)
        set_pending_generic_booking_offer(state, prefill=prefill)
        location_keywords = ("donde", "direccion", "ubicacion", "ubicados", "contacto", "telefono", "whatsapp", "llamar")
        location_requested = any(keyword in normalize(clean_message) for keyword in location_keywords)
        if location_requested:
            reply = f"{answer_location(business)} {answer_hours(clean_message, business)}"
        else:
            reply = answer_hours(clean_message, business)
    elif intent == "services":
        clear_recent_completion(state)
        service_result = analyze_service_request(clean_message, business)
        if service_result.status == "matched":
            clear_pending_clarification(state)
            set_pending_booking_offer(state, service_result.matched_service.get("name") if service_result.matched_service else None)
            services_text = "; ".join(service_summary(service) for service in service_result.matches)
            service_offer = pick_variant(
                state,
                "services_intent_offer",
                (
                    "Sí, lo hacemos.",
                    "Sí, ese servicio lo trabajamos.",
                    "Sí, lo tenemos.",
                ),
            )
            booking_offer = pick_variant(
                state,
                "services_intent_booking",
                (
                    "Si quieres, te dejo ya la cita pedida.",
                    "Si te viene bien, te dejo ya la cita pedida.",
                    "Si te encaja, te la dejo ya pedida.",
                ),
            )
            reply = f"{service_offer} {services_text} {booking_offer}"
        elif service_result.needs_clarification and service_result.clarification:
            clear_pending_offer(state)
            set_pending_service_clarification(state, result=service_result, intent="services")
            reply = f"{service_result.clarification} Así te digo la opción correcta."
        else:
            clear_pending_clarification(state)
            clear_pending_offer(state)
            reply = (
                f"Ahora mismo trabajamos servicios como {list_services(business)}. "
                "Si me dices cuál te interesa, te oriento mejor."
            )
    elif intent == "prices":
        clear_recent_completion(state)
        service_result = analyze_service_request(clean_message, business)
        if service_result.status == "matched":
            clear_pending_clarification(state)
            set_pending_booking_offer(state, service_result.matched_service.get("name") if service_result.matched_service else None)
            prices_text = "; ".join(service_summary(service) for service in service_result.matches)
            booking_offer = pick_variant(
                state,
                "prices_intent_booking",
                (
                    "Si quieres, te dejo ya la cita pedida.",
                    "Si te viene bien, te dejo ya la cita pedida.",
                    "Si te encaja, te la dejo ya pedida.",
                ),
            )
            reply = (
                f"Te orientaría en {prices_text} "
                "El precio final puede cambiar un poco según valoración. "
                f"{booking_offer}"
            )
        elif service_result.needs_clarification and service_result.clarification:
            clear_pending_offer(state)
            set_pending_service_clarification(state, result=service_result, intent="prices")
            reply = f"Para darte un precio orientativo bien ajustado: {service_result.clarification}"
        else:
            clear_pending_clarification(state)
            clear_pending_offer(state)
            reply = f"Para que te hagas una idea, algunos precios son: {list_prices(business)}."
    elif intent == "location":
        clear_recent_completion(state)
        clear_pending_clarification(state)
        clear_pending_offer(state)
        set_pending_generic_booking_offer(state)
        reply = answer_location(business)
    elif intent == "greeting":
        clear_recent_completion(state)
        clear_pending_clarification(state)
        clear_pending_offer(state)
        reply = business.get("messages", {}).get(
            "welcome",
            "Hola. Puedo ayudarte con horarios, servicios, precios o dejarte una cita pedida.",
        )
    elif intent == "thanks":
        clear_recent_completion(state)
        clear_pending_clarification(state)
        clear_pending_offer(state)
        reply = pick_variant(
            state,
            "thanks_reply",
            (
                "De nada. Si necesitas algo más, aquí estoy.",
                "De nada. Si te viene bien, seguimos.",
                "Perfecto. Si necesitas otra cosa, dime.",
            ),
        )
    elif intent == "help":
        clear_recent_completion(state)
        clear_pending_clarification(state)
        clear_pending_offer(state)
        reply = pick_variant(
            state,
            "help_reply",
            (
                "Puedo ayudarte con horarios, servicios, precios, ubicación y dejarte una cita pedida. "
                "Por ejemplo: 'mañana a las 17 mechas', 'precio del tinte' o '¿abren el sábado?'.",
                "Te puedo ayudar con horarios, servicios, precios, ubicación o reservar una cita. "
                "Por ejemplo: 'quiero cita mañana por la tarde' o 'precio del corte mujer'.",
            ),
        )
    else:
        clear_pending_clarification(state)
        clear_pending_offer(state)
        default_fallback = pick_variant(
            state,
            "fallback_reply",
            (
                "Puedo ayudarte con horarios, servicios, precios, ubicación o dejarte una cita pedida.",
                "Si te viene bien, dime qué necesitas y te ayudo con horarios, servicios, precios o una cita.",
            ),
        )
        reply = business.get("messages", {}).get("fallback", default_fallback)

    reply = decorate_whatsapp_reply(state, intent=intent, reply=reply)
    return {"reply": reply, "intent": intent, "appointment_created": False}
