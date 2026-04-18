from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


BASE_GROUPS = {
    "corte": (
        "corte",
        "cortar",
        "cortarme",
        "corte de pelo",
        "cortar pelo",
        "cortarme el pelo",
        "corte cabello",
    ),
    "peinado": ("peinado", "peinar", "peinarme", "brushing"),
    "color": ("color", "coloracion", "tinte", "tenir", "teñir", "color de pelo"),
    "mechas": ("mechas", "reflejos", "balayage"),
    "decoloracion": ("decoloracion", "decolorar", "decolorarme"),
    "unas": ("unas", "uñas"),
    "manicura": ("manicura", "esmaltado"),
    "pedicura": ("pedicura",),
    "barba": (
        "barba",
        "arreglo de barba",
        "afeitado",
        "afeitar",
        "afeitarme",
        "barberia",
        "barbería",
    ),
}

MODIFIER_GROUPS = {
    "hombre": ("hombre", "caballero", "senor", "señor", "varon", "masculino", "chico"),
    "mujer": ("mujer", "senora", "señora", "femenino", "chica"),
    "infantil": ("nino", "niño", "nina", "niña", "infantil", "hijo", "hija"),
}

MUTUALLY_EXCLUSIVE_MODIFIERS = (
    frozenset(("hombre", "mujer", "infantil")),
)

GENERIC_GROUPS = {"corte", "unas"}
SPECIFIC_GROUPS = {"barba", "decoloracion", "manicura", "mechas", "pedicura", "peinado"}
MIN_CLEAR_SCORE = 35
CLEAR_MARGIN = 18


@dataclass
class ServiceMatchResult:
    status: str
    matches: list[dict[str, Any]] = field(default_factory=list)
    clarification: str | None = None
    requested_groups: set[str] = field(default_factory=set)
    requested_modifiers: set[str] = field(default_factory=set)
    has_signal: bool = False

    @property
    def matched_service(self) -> dict[str, Any] | None:
        if self.status == "matched" and self.matches:
            return self.matches[0]
        return None

    @property
    def needs_clarification(self) -> bool:
        return self.status in {"ambiguous", "multiple"}


@dataclass
class _ServiceCandidate:
    service: dict[str, Any]
    index: int
    score: int
    service_groups: set[str]
    service_modifiers: set[str]
    conflicts: set[str]


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def compact(text: str) -> str:
    clean = normalize(text).replace("_", " ")
    clean = re.sub(r"[^\w\s:+/-]", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()


def phrase_in_text(phrase: str, text: str) -> bool:
    phrase = compact(phrase)
    if not phrase:
        return False
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def phrase_position(phrase: str, text: str) -> int | None:
    phrase = compact(phrase)
    if not phrase:
        return None
    match = re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text)
    if not match:
        return None
    return match.start()


def extract_groups(text: str, groups: dict[str, tuple[str, ...]]) -> set[str]:
    clean = compact(text)
    found: set[str] = set()
    for group, terms in groups.items():
        if any(phrase_in_text(term, clean) for term in terms):
            found.add(group)
    return found


def service_terms(service: dict[str, Any]) -> list[str]:
    terms = [service.get("name", ""), str(service.get("id", "")).replace("_", " ")]
    terms.extend(service.get("aliases", []))
    return [term for term in terms if term]


def service_text(service: dict[str, Any]) -> str:
    return " ".join(service_terms(service))


def modifier_conflicts(requested: set[str], service_modifiers: set[str]) -> set[str]:
    conflicts: set[str] = set()
    for exclusive_group in MUTUALLY_EXCLUSIVE_MODIFIERS:
        requested_in_group = requested & exclusive_group
        service_in_group = service_modifiers & exclusive_group
        if requested_in_group and service_in_group and requested_in_group.isdisjoint(service_in_group):
            conflicts.update(service_in_group)
    return conflicts


def term_score(term: str) -> int:
    groups = extract_groups(term, BASE_GROUPS)
    modifiers = extract_groups(term, MODIFIER_GROUPS)

    if modifiers:
        return 70
    if len(groups) > 1:
        return 62
    if groups & SPECIFIC_GROUPS:
        return 58
    if groups:
        return 24
    return 10


def build_candidate(
    message_text: str,
    service: dict[str, Any],
    index: int,
    requested_groups: set[str],
    requested_modifiers: set[str],
    allow_modifier_only: bool,
) -> _ServiceCandidate | None:
    terms = service_terms(service)
    exact_terms = [term for term in terms if phrase_in_text(term, message_text)]
    profile_text = service_text(service)
    service_groups = extract_groups(profile_text, BASE_GROUPS)
    category = str(service.get("category", "")).strip().lower()
    if category in BASE_GROUPS:
        service_groups.add(category)
    service_modifiers = extract_groups(profile_text, MODIFIER_GROUPS)

    group_matches = requested_groups & service_groups
    modifier_matches = requested_modifiers & service_modifiers
    modifier_only_match = allow_modifier_only and not requested_groups and modifier_matches

    if not exact_terms and not group_matches and not modifier_only_match:
        return None

    conflicts = modifier_conflicts(requested_modifiers, service_modifiers)
    missing_groups = requested_groups - service_groups

    score = sum(term_score(term) for term in exact_terms)
    score += 35 * len(group_matches)
    score += 55 * len(modifier_matches)
    score -= 25 * len(missing_groups)
    score -= 120 * len(conflicts)

    return _ServiceCandidate(
        service=service,
        index=index,
        score=score,
        service_groups=service_groups,
        service_modifiers=service_modifiers,
        conflicts=conflicts,
    )


def unique_services(candidates: list[_ServiceCandidate]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    services: list[dict[str, Any]] = []
    for candidate in candidates:
        service_id = str(candidate.service.get("id") or candidate.service.get("name"))
        if service_id in seen:
            continue
        seen.add(service_id)
        services.append(candidate.service)
    return services


def format_service_options(services: list[dict[str, Any]]) -> str:
    names = [service.get("name", "servicio") for service in services]
    if len(names) <= 1:
        return names[0] if names else "ese servicio"
    if len(names) == 2:
        return f"{names[0]} o {names[1]}"
    return f"{', '.join(names[:-1])} o {names[-1]}"


def ordered_groups_in_text(text: str, requested_groups: set[str]) -> list[str]:
    ordered: list[tuple[int, str]] = []
    for group in requested_groups:
        positions = [
            position
            for term in BASE_GROUPS[group]
            if (position := phrase_position(term, text)) is not None
        ]
        if positions:
            ordered.append((min(positions), group))

    ordered.sort()
    return [group for _, group in ordered]


def representative_services_for_groups(
    candidates: list[_ServiceCandidate],
    requested_groups: set[str],
    text: str,
) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    seen: set[str] = set()

    for group in ordered_groups_in_text(text, requested_groups):
        group_candidates = [
            candidate for candidate in candidates if group in candidate.service_groups and candidate.score > 0
        ]
        if not group_candidates:
            continue
        group_candidates.sort(key=lambda candidate: (-candidate.score, candidate.index))
        service = group_candidates[0].service
        service_id = str(service.get("id") or service.get("name"))
        if service_id not in seen:
            seen.add(service_id)
            services.append(service)

    if services:
        return services

    return unique_services(candidates[:4])


def clarification_message(services: list[dict[str, Any]], status: str) -> str:
    options = format_service_options(services)
    if status == "multiple":
        return (
            "Ahora mismo registro una solicitud por servicio. "
            f"¿Quieres que lo dejemos como {options}?"
        )
    return f"Claro. ¿Te refieres a {options}?"


def analyze_service_request(
    message: str,
    business: dict[str, Any],
    *,
    allow_modifier_only: bool = False,
    allowed_service_ids: set[str] | None = None,
) -> ServiceMatchResult:
    text = compact(message)
    requested_groups = extract_groups(text, BASE_GROUPS)
    requested_modifiers = extract_groups(text, MODIFIER_GROUPS)
    has_signal = bool(requested_groups or (allow_modifier_only and requested_modifiers))

    candidates: list[_ServiceCandidate] = []
    for index, service in enumerate(business.get("services", [])):
        service_id = str(service.get("id", ""))
        if allowed_service_ids is not None and service_id not in allowed_service_ids:
            continue
        candidate = build_candidate(
            text,
            service,
            index,
            requested_groups,
            requested_modifiers,
            allow_modifier_only,
        )
        if candidate:
            candidates.append(candidate)

    if not candidates:
        return ServiceMatchResult(
            status="none",
            requested_groups=requested_groups,
            requested_modifiers=requested_modifiers,
            has_signal=has_signal,
        )

    non_conflicting = [candidate for candidate in candidates if not candidate.conflicts]
    if non_conflicting:
        candidates = non_conflicting

    candidates.sort(key=lambda candidate: (-candidate.score, candidate.index))

    if len(requested_groups) > 1:
        covering_candidates = [
            candidate for candidate in candidates if requested_groups <= candidate.service_groups
        ]
        if covering_candidates:
            candidates = covering_candidates
        else:
            services = representative_services_for_groups(candidates, requested_groups, text)
            return ServiceMatchResult(
                status="multiple",
                matches=services,
                clarification=clarification_message(services, "multiple"),
                requested_groups=requested_groups,
                requested_modifiers=requested_modifiers,
                has_signal=True,
            )

    if requested_groups and not requested_modifiers and requested_groups <= GENERIC_GROUPS:
        variant_candidates = [
            candidate for candidate in candidates if requested_groups & candidate.service_groups
        ]
        services = unique_services(variant_candidates)
        if len(services) > 1:
            return ServiceMatchResult(
                status="ambiguous",
                matches=services,
                clarification=clarification_message(services, "ambiguous"),
                requested_groups=requested_groups,
                requested_modifiers=requested_modifiers,
                has_signal=True,
            )

    clear_candidates = [candidate for candidate in candidates if candidate.score >= MIN_CLEAR_SCORE]
    if not clear_candidates:
        if allowed_service_ids is not None:
            services = unique_services(candidates)
            if len(services) == 1 and candidates[0].score > 0:
                return ServiceMatchResult(
                    status="matched",
                    matches=[services[0]],
                    requested_groups=requested_groups,
                    requested_modifiers=requested_modifiers,
                    has_signal=True,
                )
        return ServiceMatchResult(
            status="none",
            requested_groups=requested_groups,
            requested_modifiers=requested_modifiers,
            has_signal=has_signal,
        )

    top = clear_candidates[0]
    close_candidates = [
        candidate for candidate in clear_candidates if top.score - candidate.score <= CLEAR_MARGIN
    ]
    services = unique_services(close_candidates)

    if len(services) > 1:
        return ServiceMatchResult(
            status="ambiguous",
            matches=services,
            clarification=clarification_message(services, "ambiguous"),
            requested_groups=requested_groups,
            requested_modifiers=requested_modifiers,
            has_signal=True,
        )

    return ServiceMatchResult(
        status="matched",
        matches=[top.service],
        requested_groups=requested_groups,
        requested_modifiers=requested_modifiers,
        has_signal=True,
    )


def find_matching_services(message: str, business: dict[str, Any]) -> list[dict[str, Any]]:
    result = analyze_service_request(message, business)
    if result.status == "matched":
        return result.matches
    return []


def service_summary(service: dict[str, Any]) -> str:
    price = service.get("price", "precio a confirmar")
    duration = service.get("duration", "")
    if duration:
        return f"{service['name']}: {price}, {duration} aprox."
    return f"{service['name']}: {price}."


def list_services(business: dict[str, Any]) -> str:
    services = business.get("services", [])
    return ", ".join(service.get("name", "") for service in services if service.get("name"))


def list_prices(business: dict[str, Any], limit: int = 6) -> str:
    services = business.get("services", [])[:limit]
    return "; ".join(service_summary(service) for service in services)
