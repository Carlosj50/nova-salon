from __future__ import annotations

import re
import unicodedata
from typing import Any

from .datetime_parser import parse_date, parse_datetime
from .repositories import normalize_phone
from .service_catalog import analyze_service_request


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def first_name(value: str | None) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    return clean.split()[0]


def is_affirmative(message: str) -> bool:
    text = normalize(message).strip()
    return bool(
        text
        and re.fullmatch(
            r"(si|sí|claro|vale|ok|okay|perfecto|de acuerdo|me interesa|quiero|adelante|por favor|si claro|si quiero)",
            text,
        )
    )


def contains_affirmative(message: str) -> bool:
    text = normalize(message).strip()
    if not text:
        return False
    starters = (
        "si",
        "sí",
        "claro",
        "vale",
        "ok",
        "okay",
        "perfecto",
        "de acuerdo",
        "me interesa",
        "quiero",
        "adelante",
        "por favor",
    )
    return any(
        text == starter
        or text.startswith(f"{starter} ")
        or text.startswith(f"{starter},")
        or text.startswith(f"{starter}.")
        for starter in starters
    )


def is_negative(message: str) -> bool:
    text = normalize(message).strip()
    return bool(
        text
        and re.fullmatch(
            r"(no|no gracias|ahora no|de momento no|prefiero que no|no hace falta)",
            text,
        )
    )


def contains_negative(message: str) -> bool:
    text = normalize(message).strip()
    if not text:
        return False
    starters = (
        "no",
        "no gracias",
        "ahora no",
        "de momento no",
        "prefiero que no",
        "no hace falta",
    )
    return any(
        text == starter
        or text.startswith(f"{starter} ")
        or text.startswith(f"{starter},")
        or text.startswith(f"{starter}.")
        for starter in starters
    )


def is_greeting(message: str) -> bool:
    text = normalize(message).strip()
    return bool(
        text
        and re.fullmatch(
            r"(hola|buenas|buenos dias|buenas tardes|buenas noches|hola buenas|hey|holi)",
            text,
        )
    )


def is_thanks(message: str) -> bool:
    text = normalize(message).strip()
    return bool(
        text
        and re.fullmatch(
            r"(gracias|muchas gracias|genial gracias|perfecto gracias|ok gracias|vale gracias)",
            text,
        )
    )


def looks_like_loose_customer_fragment(message: str) -> bool:
    clean = message.strip()
    if not clean or len(clean) > 40:
        return False
    if any(char.isdigit() for char in clean):
        return extract_phone(clean) is not None
    return re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]{2,40}", clean) is not None


def extract_identity_name(message: str) -> str | None:
    clean = message.strip()
    patterns = (
        r"^(?:no soy\s+[^,.;]+[,.;]?\s*)?soy\s+(.+)$",
        r"^(?:me llamo|mi nombre es)\s+(.+)$",
    )

    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip(" .,!;:")
        if any(char.isdigit() for char in candidate):
            return None
        if 2 <= len(candidate) <= 60:
            return candidate
    return None


def parse_hours_range(raw_value: str | None) -> tuple[str, str] | None:
    if not raw_value or raw_value == "cerrado":
        return None
    match = re.fullmatch(r"\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s*", raw_value)
    if not match:
        return None
    return match.group(1), match.group(2)


def hours_for_date(date_value: str, business: dict[str, Any]) -> str:
    hours = business.get("hours", {})
    from datetime import date as _date

    parsed = _date.fromisoformat(date_value)
    if parsed.weekday() <= 4:
        return str(hours.get("monday_friday") or hours.get("summary") or "horario pendiente de configurar")
    if parsed.weekday() == 5:
        return str(hours.get("saturday") or "cerrado")
    return str(hours.get("sunday") or "cerrado")


def answer_hours(message: str, business: dict[str, Any]) -> str:
    hours = business.get("hours", {})
    date_value, date_error = parse_date(message, business.get("timezone", "Atlantic/Canary"))
    normalized_message = normalize(message)

    if date_error:
        return f"{date_error} Nuestro horario general es {hours.get('summary', 'horario pendiente de configurar')}."

    if date_value:
        day_schedule = hours_for_date(date_value, business)
        if day_schedule == "cerrado":
            return f"El {date_value} estamos cerrados. Si quieres, dime otro día y te digo qué opciones tienes."

        range_values = parse_hours_range(day_schedule)
        if "tarde" in normalized_message and range_values:
            _, close_time = range_values
            if close_time > "15:00":
                return f"Sí, ese día atendemos por la tarde. El {date_value} abrimos de {range_values[0]} a {range_values[1]}."
            return f"Ese día solo abrimos por la mañana: de {range_values[0]} a {range_values[1]}."

        if "manana" in normalized_message and range_values and range_values[0] < "14:00":
            return f"Sí, ese día abrimos de {range_values[0]} a {range_values[1]}."

        return f"El {date_value} abrimos de {day_schedule}. Si te viene bien, te dejo la cita pedida."

    return (
        f"Nuestro horario es {hours.get('summary', 'horario pendiente de configurar')}. "
        "Si te viene bien, te dejo la cita pedida y el equipo la confirma."
    )


def booking_prefill_from_hours(message: str, business: dict[str, Any]) -> dict[str, str]:
    parsed = parse_datetime(
        message,
        timezone=business.get("timezone", "Atlantic/Canary"),
        has_date_context=False,
    )
    if not parsed.date_value:
        return {}

    prefill = {"date": parsed.date_value}
    if not parsed.part_of_day:
        return prefill

    day_schedule = hours_for_date(parsed.date_value, business)
    if day_schedule == "cerrado":
        return {}

    range_values = parse_hours_range(day_schedule)
    if not range_values:
        return prefill

    open_time, close_time = range_values
    if parsed.part_of_day == "tarde" and close_time <= "15:00":
        return {}
    if parsed.part_of_day == "mañana" and open_time >= "14:00":
        return {}

    prefill["part_of_day"] = parsed.part_of_day
    return prefill


def answer_location(business: dict[str, Any]) -> str:
    return (
        f"Estamos en {business.get('address', 'dirección pendiente de configurar')}. "
        f"Si lo prefieres, también puedes llamarnos o escribirnos al {business.get('phone', 'teléfono pendiente de configurar')}."
    )


def detect_intent(message: str, business: dict[str, Any]) -> str:
    text = normalize(message)
    service_result = analyze_service_request(message, business)
    parsed = parse_datetime(
        message,
        timezone=business.get("timezone", "Atlantic/Canary"),
        has_date_context=False,
    )

    hour_keywords = (
        "horario",
        "hora abren",
        "a que hora",
        "abren",
        "abris",
        "abre",
        "abierto",
        "cerrado",
        "manana por la tarde",
    )
    price_keywords = ("precio", "cuanto", "cuesta", "coste", "vale", "tarifa")
    booking_keywords = (
        "cita",
        "reserv",
        "hueco",
        "turno",
        "agenda",
        "agendar",
        "disponibilidad",
    )
    location_keywords = (
        "donde",
        "direccion",
        "ubicacion",
        "ubicados",
        "contacto",
        "telefono",
        "whatsapp",
        "llamar",
    )
    service_keywords = (
        "servicio",
        "servicios",
        "haceis",
        "tenéis",
        "teneis",
        "ofreceis",
        "ofrecéis",
    )
    help_keywords = (
        "ayuda",
        "que puedes hacer",
        "qué puedes hacer",
        "en que me puedes ayudar",
        "en qué me puedes ayudar",
    )

    explicit_hour_question = any(keyword in text for keyword in hour_keywords)
    explicit_booking = any(keyword in text for keyword in booking_keywords)
    has_datetime_signal = bool(parsed.date_value or parsed.time_value or parsed.part_of_day)

    if explicit_booking and not any(keyword in text for keyword in ("abren", "abris", "abre", "horario", "abierto", "cerrado")):
        return "booking"
    if explicit_hour_question:
        return "hours"
    if has_datetime_signal and service_result.has_signal:
        return "booking"
    if has_datetime_signal and not any(keyword in text for keyword in location_keywords):
        return "booking"
    if any(keyword in text for keyword in price_keywords):
        return "prices"
    if explicit_booking:
        return "booking"
    if any(keyword in text for keyword in location_keywords):
        return "location"
    if any(keyword in text for keyword in help_keywords):
        return "help"
    if any(keyword in text for keyword in service_keywords) or service_result.has_signal:
        return "services"
    if is_greeting(message):
        return "greeting"
    if is_thanks(message):
        return "thanks"

    return "fallback"


def extract_phone(message: str) -> str | None:
    match = re.search(r"(\+?\d[\d\s().-]{7,}\d)", message)
    if not match:
        return None

    phone = normalize_phone(match.group(1))
    if 9 <= len(phone) <= 15:
        return phone
    return None


def extract_name(message: str, expected: bool = False) -> str | None:
    clean = message.strip()
    patterns = (
        r"^(?:me llamo|soy|mi nombre es|nombre:)\s+(.+)$",
        r"^(.+)\s+(?:es mi nombre)$",
    )

    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            clean = match.group(1).strip()
            break

    if not expected and clean == message.strip():
        return None

    if any(char.isdigit() for char in clean):
        return None
    if len(clean) < 2 or len(clean) > 60:
        return None

    return clean
