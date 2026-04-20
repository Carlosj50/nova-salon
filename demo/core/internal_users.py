from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import hash_admin_password
from .db import connection_scope
from .repositories import now_iso


VALID_USER_ROLES = ("admin", "staff")


def _user_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "password_hash": str(row["password_hash"]),
        "role": str(row["role"]),
        "active": bool(row["active"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def list_internal_users(db_path: Path) -> list[dict[str, Any]]:
    with connection_scope(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, username, password_hash, role, active, created_at, updated_at
            FROM internal_users
            ORDER BY active DESC, role ASC, username COLLATE NOCASE ASC
            """
        ).fetchall()
    return [_user_from_row(dict(row)) for row in rows]


def get_internal_user(db_path: Path, user_id: int) -> dict[str, Any] | None:
    with connection_scope(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, username, password_hash, role, active, created_at, updated_at
            FROM internal_users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return _user_from_row(dict(row))


def get_internal_user_by_username(db_path: Path, username: str) -> dict[str, Any] | None:
    clean_username = str(username or "").strip()
    if not clean_username:
        return None
    with connection_scope(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, username, password_hash, role, active, created_at, updated_at
            FROM internal_users
            WHERE lower(username) = lower(?)
            """,
            (clean_username,),
        ).fetchone()
    if not row:
        return None
    return _user_from_row(dict(row))


def create_internal_user(
    db_path: Path,
    *,
    username: str,
    password: str,
    role: str,
    active: bool = True,
    timezone: str = "Atlantic/Canary",
) -> dict[str, Any]:
    clean_username = str(username or "").strip()
    clean_role = str(role or "").strip().lower()
    if clean_role not in VALID_USER_ROLES:
        raise ValueError("invalid_role")
    password_hash = hash_admin_password(password)
    timestamp = now_iso(timezone)
    with connection_scope(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO internal_users (username, password_hash, role, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (clean_username, password_hash, clean_role, 1 if active else 0, timestamp, timestamp),
        )
        user_id = int(cursor.lastrowid)
    return get_internal_user(db_path, user_id)  # type: ignore[return-value]


def update_internal_user(
    db_path: Path,
    *,
    user_id: int,
    username: str,
    role: str,
    active: bool,
    password: str | None = None,
    timezone: str = "Atlantic/Canary",
) -> dict[str, Any] | None:
    clean_username = str(username or "").strip()
    clean_role = str(role or "").strip().lower()
    if clean_role not in VALID_USER_ROLES:
        raise ValueError("invalid_role")
    with connection_scope(db_path) as connection:
        if password:
            connection.execute(
                """
                UPDATE internal_users
                SET username = ?, role = ?, active = ?, password_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    clean_username,
                    clean_role,
                    1 if active else 0,
                    hash_admin_password(password),
                    now_iso(timezone),
                    user_id,
                ),
            )
        else:
            connection.execute(
                """
                UPDATE internal_users
                SET username = ?, role = ?, active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    clean_username,
                    clean_role,
                    1 if active else 0,
                    now_iso(timezone),
                    user_id,
                ),
            )
    return get_internal_user(db_path, user_id)
