from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


WEEKDAYS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}

MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

PARTS_OF_DAY = {
    "por la manana": "mañana",
    "por la mañana": "mañana",
    "esta manana": "mañana",
    "esta mañana": "mañana",
    "por la tarde": "tarde",
    "esta tarde": "tarde",
    "por la noche": "noche",
    "mediodia": "mediodía",
    "mediodía": "mediodía",
}


@dataclass(frozen=True)
class DateTimeParseResult:
    date_value: str | None = None
    time_value: str | None = None
    part_of_day: str | None = None
    date_error: str | None = None
    time_error: str | None = None


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def today_for_timezone(timezone: str) -> date:
    return datetime.now(ZoneInfo(timezone)).date()


def format_date(value: date) -> str:
    return value.isoformat()


def reject_past(value: date, today: date) -> str | None:
    if value < today:
        return "Esa fecha ya ha pasado. Dime una fecha futura para registrar la solicitud."
    return None


def next_weekday(today: date, weekday: int, *, include_today: bool = True) -> date:
    days_ahead = (weekday - today.weekday()) % 7
    if days_ahead == 0 and not include_today:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def this_weekday(today: date, weekday: int) -> date | None:
    days_ahead = weekday - today.weekday()
    if days_ahead < 0:
        return None
    return today + timedelta(days=days_ahead)


def following_weekday(today: date, weekday: int) -> date:
    this_or_next = next_weekday(today, weekday, include_today=False)
    if this_or_next <= today + timedelta(days=6 - today.weekday()):
        return this_or_next + timedelta(days=7)
    return this_or_next


def parse_explicit_date(text: str, today: date) -> tuple[str | None, str | None]:
    iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        year, month, day = (int(part) for part in iso_match.groups())
        try:
            value = date(year, month, day)
        except ValueError:
            return None, "No reconozco esa fecha. Escríbela como 2026-04-18 o 18/04."
        return format_date(value), reject_past(value, today)

    numeric_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", text)
    if numeric_match:
        day = int(numeric_match.group(1))
        month = int(numeric_match.group(2))
        raw_year = numeric_match.group(3)
        year = int(raw_year) if raw_year else today.year
        if raw_year and year < 100:
            year += 2000
        try:
            value = date(year, month, day)
        except ValueError:
            return None, "No reconozco esa fecha. Escríbela como 18/04 o 2026-04-18."
        if not raw_year and value < today:
            value = date(today.year + 1, month, day)
        return format_date(value), reject_past(value, today)

    month_names = "|".join(MONTHS)
    text_month_match = re.search(
        rf"\b(\d{{1,2}})\s*(?:de\s*)?({month_names})(?:\s*(?:de\s*)?(\d{{2,4}}))?\b",
        text,
    )
    if text_month_match:
        day = int(text_month_match.group(1))
        month = MONTHS[text_month_match.group(2)]
        raw_year = text_month_match.group(3)
        year = int(raw_year) if raw_year else today.year
        if raw_year and year < 100:
            year += 2000
        try:
            value = date(year, month, day)
        except ValueError:
            return None, "No reconozco esa fecha. Por ejemplo: 18 de abril."
        if not raw_year and value < today:
            value = date(today.year + 1, month, day)
        return format_date(value), reject_past(value, today)

    return None, None


def parse_date(message: str, timezone: str) -> tuple[str | None, str | None]:
    today = today_for_timezone(timezone)
    text = normalize(message)

    if re.search(r"\b(?:la\s+)?(?:proxima|siguiente)\s+semana\b", text) or "semana que viene" in text:
        weekday_mentioned = any(day in text for day in WEEKDAYS)
        if not weekday_mentioned:
            return None, "Necesito un día concreto de la próxima semana para registrar la cita."

    explicit_date, explicit_error = parse_explicit_date(text, today)
    if explicit_date or explicit_error:
        return explicit_date, explicit_error

    if "pasado manana" in text:
        return format_date(today + timedelta(days=2)), None
    if "manana" in text:
        return format_date(today + timedelta(days=1)), None
    if re.search(r"\bhoy\b", text):
        return format_date(today), None

    weekday_names = "|".join(WEEKDAYS)
    weekday_match = re.search(rf"\b(?:(este|esta|proximo|proxima|siguiente)\s+)?({weekday_names})\b", text)
    if not weekday_match:
        return None, None

    prefix = weekday_match.group(1)
    weekday = WEEKDAYS[weekday_match.group(2)]

    if prefix in {"este", "esta"}:
        value = this_weekday(today, weekday)
        if value is None:
            return None, "Ese día ya pasó esta semana. Dime una fecha concreta o usa 'próximo'."
        return format_date(value), None

    if prefix in {"proximo", "proxima", "siguiente"}:
        return format_date(following_weekday(today, weekday)), None

    return format_date(next_weekday(today, weekday)), None


def normalize_hour(hour: int, minutes: int = 0) -> str | None:
    if 0 <= hour <= 23 and 0 <= minutes <= 59:
        return f"{hour:02d}:{minutes:02d}"
    return None


def parse_time(message: str, *, allow_bare_hour: bool = False) -> tuple[str | None, str | None, str | None]:
    text = normalize(message)
    part_of_day = None

    for phrase, label in PARTS_OF_DAY.items():
        if phrase in text:
            part_of_day = label
            break

    phrase_match = re.search(
        r"\b(?:a las|las|sobre las|sobre|a)\s+([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:h|horas)?\b",
        text,
    )
    if phrase_match:
        hour = int(phrase_match.group(1))
        minutes = int(phrase_match.group(2) or 0)
        return normalize_hour(hour, minutes), part_of_day, None

    colon_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if colon_match:
        return normalize_hour(int(colon_match.group(1)), int(colon_match.group(2))), part_of_day, None

    h_match = re.search(r"\b([01]?\d|2[0-3])\s*h\b", text)
    if h_match:
        return normalize_hour(int(h_match.group(1))), part_of_day, None

    if allow_bare_hour:
        bare_match = re.fullmatch(r"\s*([01]?\d|2[0-3])\s*", text)
        if bare_match:
            return normalize_hour(int(bare_match.group(1))), part_of_day, None

    return None, part_of_day, None


def parse_datetime(
    message: str,
    *,
    timezone: str,
    expected_field: str | None = None,
    has_date_context: bool = False,
) -> DateTimeParseResult:
    date_value, date_error = parse_date(message, timezone)
    allow_bare_hour = expected_field == "time" or bool(date_value) or has_date_context
    time_value, part_of_day, time_error = parse_time(message, allow_bare_hour=allow_bare_hour)

    return DateTimeParseResult(
        date_value=date_value,
        time_value=time_value,
        part_of_day=part_of_day,
        date_error=date_error,
        time_error=time_error,
    )
