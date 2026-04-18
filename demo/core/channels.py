from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .db import connection_scope
from .repositories import now_iso


CHANNEL_MODES = ("demo", "preparado", "conectado")
CHANNEL_TYPES = ("whatsapp",)


def normalize_whatsapp_phone(phone: str | None) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def make_whatsapp_url(phone: str | None) -> str | None:
    normalized = normalize_whatsapp_phone(phone)
    if not normalized:
        return None
    return f"https://wa.me/{normalized}"


def decode_config(config_json: str | None) -> dict[str, Any]:
    if not config_json:
        return {}
    try:
        value = json.loads(config_json)
    except json.JSONDecodeError:
        return {"raw": config_json}
    return value if isinstance(value, dict) else {"value": value}


def encode_config(raw_config: str | None) -> str | None:
    if not raw_config or not raw_config.strip():
        return None
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError:
        return json.dumps({"notes": raw_config.strip()}, ensure_ascii=False)
    return json.dumps(parsed, ensure_ascii=False)


def decorate_channel(channel: dict[str, Any] | None) -> dict[str, Any] | None:
    if not channel:
        return None
    decorated = dict(channel)
    decorated["activo"] = bool(decorated.get("activo"))
    decorated["config"] = decode_config(decorated.get("config_json"))
    if decorated.get("tipo_canal") == "whatsapp":
        decorated["whatsapp_url"] = make_whatsapp_url(decorated.get("telefono"))
        decorated["telefono_normalizado"] = normalize_whatsapp_phone(decorated.get("telefono"))
    return decorated


def list_channels(db_path: Path) -> list[dict[str, Any]]:
    with connection_scope(db_path) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM canales
            ORDER BY tipo_canal ASC
            """
        ).fetchall()
    return [decorate_channel(dict(row)) for row in rows]


def get_channel(db_path: Path, channel_type: str) -> dict[str, Any] | None:
    with connection_scope(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM canales WHERE tipo_canal = ?",
            (channel_type,),
        ).fetchone()
    return decorate_channel(dict(row)) if row else None


def default_channel(channel_type: str) -> dict[str, Any]:
    return decorate_channel(
        {
            "id": None,
            "tipo_canal": channel_type,
            "activo": False,
            "modo": "demo",
            "telefono": "",
            "nombre_visible": "",
            "config_json": "",
            "created_at": "",
            "updated_at": "",
        }
    )


def upsert_channel(
    db_path: Path,
    *,
    channel_type: str,
    active: bool,
    mode: str,
    phone: str | None,
    display_name: str | None,
    config_json: str | None,
    timezone: str = "Atlantic/Canary",
) -> dict[str, Any]:
    if channel_type not in CHANNEL_TYPES:
        raise ValueError("Tipo de canal no soportado")
    if mode not in CHANNEL_MODES:
        raise ValueError("Modo de canal no válido")

    timestamp = now_iso(timezone)
    normalized_config = encode_config(config_json)

    with connection_scope(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM canales WHERE tipo_canal = ?",
            (channel_type,),
        ).fetchone()
        if existing:
            connection.execute(
                """
                UPDATE canales
                SET activo = ?,
                    modo = ?,
                    telefono = ?,
                    nombre_visible = ?,
                    config_json = ?,
                    updated_at = ?
                WHERE tipo_canal = ?
                """,
                (
                    1 if active else 0,
                    mode,
                    phone.strip() if phone else None,
                    display_name.strip() if display_name else None,
                    normalized_config,
                    timestamp,
                    channel_type,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO canales (
                    tipo_canal, activo, modo, telefono, nombre_visible,
                    config_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    channel_type,
                    1 if active else 0,
                    mode,
                    phone.strip() if phone else None,
                    display_name.strip() if display_name else None,
                    normalized_config,
                    timestamp,
                    timestamp,
                ),
            )

    return get_channel(db_path, channel_type) or default_channel(channel_type)
