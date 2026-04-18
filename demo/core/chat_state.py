from __future__ import annotations

from time import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationState:
    last_seen_at: float = field(default_factory=time)
    turn_counter: int = 0
    channel_type: str | None = None
    incoming_phone: str | None = None
    collecting_appointment: bool = False
    appointment: dict[str, str] = field(default_factory=dict)
    known_customer: dict[str, Any] | None = None
    channel_customer_greeted: bool = False
    customer_identity_uncertain: bool = False
    customer_name_override: str | None = None
    expected_field: str | None = None
    last_intent: str | None = None
    pending_clarification: dict[str, Any] | None = None
    pending_clarification_turns: int = 0
    pending_offer: dict[str, Any] | None = None
    pending_offer_turns: int = 0
    recent_completion: dict[str, str] | None = None
    recent_completion_turns: int = 0


def clear_pending_clarification(state: ConversationState) -> None:
    state.pending_clarification = None
    state.pending_clarification_turns = 0


def clear_pending_offer(state: ConversationState) -> None:
    state.pending_offer = None
    state.pending_offer_turns = 0


def clear_recent_completion(state: ConversationState) -> None:
    state.recent_completion = None
    state.recent_completion_turns = 0


def set_recent_completion(state: ConversationState, *, date: str, time: str, service: str) -> None:
    state.recent_completion = {
        "date": date,
        "time": time,
        "service": service,
    }
    state.recent_completion_turns = 2


def decay_recent_completion(state: ConversationState) -> None:
    if not state.recent_completion:
        return
    state.recent_completion_turns -= 1
    if state.recent_completion_turns <= 0:
        clear_recent_completion(state)


def pick_variant(state: ConversationState, key: str, variants: tuple[str, ...]) -> str:
    if not variants:
        return ""
    index = (state.turn_counter + len(key)) % len(variants)
    return variants[index]


def set_pending_booking_offer(state: ConversationState, service_name: str | None) -> None:
    if not service_name:
        clear_pending_offer(state)
        return
    state.pending_offer = {
        "kind": "booking_offer",
        "service": service_name,
        "prefill": {},
    }
    state.pending_offer_turns = 2


def set_pending_generic_booking_offer(
    state: ConversationState,
    *,
    prefill: dict[str, str] | None = None,
) -> None:
    state.pending_offer = {
        "kind": "booking_offer",
        "service": None,
        "prefill": prefill or {},
    }
    state.pending_offer_turns = 2


def set_pending_service_clarification(
    state: ConversationState,
    *,
    result: Any,
    intent: str,
) -> None:
    service_ids = [str(service.get("id", "")) for service in result.matches if service.get("id")]
    if not service_ids:
        clear_pending_clarification(state)
        return

    state.pending_clarification = {
        "kind": "service",
        "intent": intent,
        "service_ids": service_ids,
    }
    state.pending_clarification_turns = 2
