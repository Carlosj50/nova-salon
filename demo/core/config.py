from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .db import connection_scope
from .repositories import (
    backfill_appointment_service_ids,
    list_service_categories,
    list_services_config,
    list_staff_members,
    seed_operational_data,
)

EDITABLE_BUSINESS_KEYS = ("name", "sector", "phone", "address", "logo_path")
EDITABLE_HOURS_KEYS = ("summary", "monday_friday", "saturday", "sunday")
EDITABLE_MESSAGE_KEYS = ("welcome", "fallback")


def _merge_dict(target: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            nested = dict(target.get(key, {}))
            target[key] = _merge_dict(nested, value)
        else:
            target[key] = value
    return target


def load_business_overrides(db_path: Path) -> dict[str, Any]:
    with connection_scope(db_path) as connection:
        row = connection.execute(
            "SELECT data_json FROM business_config WHERE id = 1"
        ).fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["data_json"])
    except json.JSONDecodeError:
        return {}


def business_settings_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in EDITABLE_BUSINESS_KEYS:
        value = str(data.get(key) or "").strip()
        if value:
            payload[key] = value

    raw_hours = data.get("hours", {})
    if isinstance(raw_hours, dict):
        hours_payload = {
            key: str(raw_hours.get(key) or "").strip()
            for key in EDITABLE_HOURS_KEYS
            if str(raw_hours.get(key) or "").strip()
        }
        if hours_payload:
            payload["hours"] = hours_payload

    raw_messages = data.get("messages", {})
    if isinstance(raw_messages, dict):
        messages_payload = {
            key: str(raw_messages.get(key) or "").strip()
            for key in EDITABLE_MESSAGE_KEYS
            if str(raw_messages.get(key) or "").strip()
        }
        if messages_payload:
            payload["messages"] = messages_payload

    return payload


def upsert_business_overrides(db_path: Path, data: dict[str, Any], *, timezone: str = "Atlantic/Canary") -> None:
    from .repositories import now_iso

    payload = business_settings_payload(data)
    with connection_scope(db_path) as connection:
        connection.execute(
            """
            INSERT INTO business_config (id, data_json, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
            """,
            (json.dumps(payload, ensure_ascii=False), now_iso(timezone)),
        )

def load_business_config(path: Path, db_path: Path | None = None) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    if not db_path:
        return config

    seed_operational_data(db_path, config, timezone=config.get("timezone", "Atlantic/Canary"))
    backfill_appointment_service_ids(db_path)
    categories = list_service_categories(db_path)
    services = list_services_config(db_path, active_only=True)
    staff = list_staff_members(db_path, active_only=True)

    config["service_categories"] = categories
    config["services"] = services
    config["staff"] = staff

    operational_rules = dict(config.get("operational_rules", {}))
    operational_rules["category_capacity"] = {
        category["id"]: category["capacity"]
        for category in categories
        if category.get("active", True)
    }
    config["operational_rules"] = operational_rules

    overrides = load_business_overrides(db_path)
    if overrides:
        config = _merge_dict(dict(config), overrides)
    return config


def load_auth_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    raw_auth = dict(config.get("auth", {}))
    username = os.getenv("APP_ADMIN_USERNAME", raw_auth.get("admin_username", "admin"))
    password = os.getenv("APP_ADMIN_PASSWORD", raw_auth.get("admin_password", "local-dev-change-me"))
    session_secret = os.getenv("APP_SESSION_SECRET", raw_auth.get("session_secret", "local-dev-session-secret-change-me"))
    session_cookie = os.getenv("APP_SESSION_COOKIE", raw_auth.get("session_cookie", "nova_panel_session"))

    return {
        "admin_username": str(username),
        "admin_password": str(password),
        "session_secret": str(session_secret),
        "session_cookie": str(session_cookie),
    }
