from __future__ import annotations

import json
import os
from hashlib import pbkdf2_hmac
from pathlib import Path
from secrets import compare_digest, token_hex
import sqlite3
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
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"


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


def load_auth_overrides(db_path: Path) -> dict[str, Any]:
    try:
        with connection_scope(db_path) as connection:
            row = connection.execute(
                "SELECT data_json FROM auth_config WHERE id = 1"
            ).fetchone()
    except sqlite3.OperationalError:
        return {}
    if not row:
        return {}
    try:
        return json.loads(row["data_json"])
    except json.JSONDecodeError:
        return {}


def hash_admin_password(password: str, *, iterations: int = 240000) -> str:
    salt = token_hex(16)
    derived = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"{PASSWORD_HASH_PREFIX}${iterations}${salt}${derived.hex()}"


def verify_admin_password(submitted_password: str, stored_value: str) -> bool:
    if not stored_value:
        return False
    if stored_value.startswith(f"{PASSWORD_HASH_PREFIX}$"):
        try:
            _prefix, raw_iterations, salt, expected_hash = stored_value.split("$", 3)
            iterations = int(raw_iterations)
        except ValueError:
            return False
        candidate = pbkdf2_hmac(
            "sha256",
            submitted_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return compare_digest(candidate, expected_hash)
    return compare_digest(submitted_password, stored_value)


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


def upsert_auth_overrides(db_path: Path, data: dict[str, Any], *, timezone: str = "Atlantic/Canary") -> None:
    from .repositories import now_iso

    existing = load_auth_overrides(db_path)
    payload = dict(existing)
    if "admin_username" in data:
        username = str(data.get("admin_username") or "").strip()
        if username:
            payload["admin_username"] = username
    if "admin_password_hash" in data:
        password_hash = str(data.get("admin_password_hash") or "").strip()
        if password_hash:
            payload["admin_password_hash"] = password_hash
    with connection_scope(db_path) as connection:
        connection.execute(
            """
            INSERT INTO auth_config (id, data_json, updated_at)
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


def load_auth_config(path: Path, db_path: Path | None = None) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    raw_auth = dict(config.get("auth", {}))
    environment_overrides_admin = any(
        name in os.environ for name in ("APP_ADMIN_USERNAME", "APP_ADMIN_PASSWORD")
    )
    auth_overrides = load_auth_overrides(db_path) if db_path and not environment_overrides_admin else {}

    default_username = auth_overrides.get("admin_username", raw_auth.get("admin_username", "admin"))
    default_password = auth_overrides.get("admin_password_hash", raw_auth.get("admin_password", "local-dev-change-me"))

    username = os.getenv("APP_ADMIN_USERNAME", default_username)
    password = os.getenv("APP_ADMIN_PASSWORD", default_password)
    session_secret = os.getenv("APP_SESSION_SECRET", raw_auth.get("session_secret", "local-dev-session-secret-change-me"))
    session_cookie = os.getenv("APP_SESSION_COOKIE", raw_auth.get("session_cookie", "nova_panel_session"))
    if environment_overrides_admin:
        admin_source = "environment"
    elif auth_overrides:
        admin_source = "panel"
    else:
        admin_source = "config"

    return {
        "admin_username": str(username),
        "admin_password": str(password),
        "session_secret": str(session_secret),
        "session_cookie": str(session_cookie),
        "admin_source": admin_source,
        "managed_by_env": environment_overrides_admin,
    }
