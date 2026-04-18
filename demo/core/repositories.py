from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .db import connection_scope
from .models import ACTIVE_APPOINTMENT_STATES, APPOINTMENT_STATES


def now_iso(timezone: str = "Atlantic/Canary") -> str:
    return datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")


def normalize_phone(phone: str) -> str:
    normalized = re.sub(r"\D", "", phone)
    if normalized.startswith("00"):
        normalized = normalized[2:]
    if normalized.startswith("34") and len(normalized) == 11:
        normalized = normalized[2:]
    return normalized


def is_valid_phone(phone: str) -> bool:
    normalized = normalize_phone(phone)
    return 9 <= len(normalized) <= 15


def find_customer_by_phone(
    db_path: Path,
    phone: str,
    *,
    exclude_customer_id: int | None = None,
    connection: Any | None = None,
) -> dict[str, Any] | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return None

    extra_clause = ""
    params: tuple[Any, ...] = (normalized,)
    if exclude_customer_id is not None:
        extra_clause = "AND id != ?"
        params = (normalized, exclude_customer_id)

    if connection is None:
        with connection_scope(db_path) as connection:
            row = connection.execute(
                f"SELECT * FROM clientes WHERE telefono = ? {extra_clause}",
                params,
            ).fetchone()
    else:
        row = connection.execute(
            f"SELECT * FROM clientes WHERE telefono = ? {extra_clause}",
            params,
        ).fetchone()
    return dict(row) if row else None


def create_customer(
    db_path: Path,
    *,
    name: str,
    phone: str,
    email: str | None = None,
    notes: str | None = None,
    timezone: str = "Atlantic/Canary",
    connection: Any | None = None,
) -> dict[str, Any]:
    normalized = normalize_phone(phone)
    if not normalized:
        raise ValueError("Teléfono no válido")
    created_at = now_iso(timezone)
    if connection is None:
        with connection_scope(db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO clientes (nombre, telefono, email, notas, fecha_alta)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name.strip(), normalized, email, notes, created_at),
            )
            row = connection.execute(
                "SELECT * FROM clientes WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
    else:
        cursor = connection.execute(
            """
            INSERT INTO clientes (nombre, telefono, email, notas, fecha_alta)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), normalized, email, notes, created_at),
        )
        row = connection.execute(
            "SELECT * FROM clientes WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


def get_or_create_customer(
    db_path: Path,
    *,
    name: str,
    phone: str,
    timezone: str = "Atlantic/Canary",
    connection: Any | None = None,
) -> tuple[dict[str, Any], bool]:
    if not is_valid_phone(phone):
        raise ValueError("Teléfono no válido")

    existing = find_customer_by_phone(db_path, phone, connection=connection)
    if existing:
        return existing, False

    return create_customer(
        db_path,
        name=name,
        phone=phone,
        timezone=timezone,
        connection=connection,
    ), True


def list_customers(db_path: Path) -> list[dict[str, Any]]:
    with connection_scope(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, nombre, telefono, fecha_alta, ultima_visita
            FROM clientes
            ORDER BY datetime(fecha_alta) DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_customer(
    db_path: Path,
    customer_id: int,
    *,
    connection: Any | None = None,
) -> dict[str, Any] | None:
    if connection is None:
        with connection_scope(db_path) as connection:
            row = connection.execute(
                "SELECT * FROM clientes WHERE id = ?",
                (customer_id,),
            ).fetchone()
    else:
        row = connection.execute(
            "SELECT * FROM clientes WHERE id = ?",
            (customer_id,),
        ).fetchone()
    return dict(row) if row else None


def update_customer(
    db_path: Path,
    *,
    customer_id: int,
    name: str,
    phone: str,
    email: str | None = None,
    notes: str | None = None,
) -> dict[str, Any] | None:
    normalized = normalize_phone(phone)
    if not normalized:
        raise ValueError("Teléfono no válido")

    with connection_scope(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE clientes
            SET nombre = ?,
                telefono = ?,
                email = ?,
                notas = ?
            WHERE id = ?
            """,
            (
                name.strip(),
                normalized,
                email.strip() if email else None,
                notes.strip() if notes else None,
                customer_id,
            ),
        )
        if cursor.rowcount <= 0:
            return None
        row = connection.execute(
            "SELECT * FROM clientes WHERE id = ?",
            (customer_id,),
        ).fetchone()
    return dict(row) if row else None


def slugify_identifier(value: str) -> str:
    slug = normalize_phone(value) if value.isdigit() else re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "item"


def _load_json_value(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return fallback


def _service_from_row(row: dict[str, Any]) -> dict[str, Any]:
    duration_minutes = int(row.get("duracion_minutos") or 0)
    return {
        "id": row["id"],
        "name": row["nombre"],
        "category": row["categoria_id"],
        "category_name": row.get("categoria_nombre", ""),
        "aliases": _load_json_value(row.get("aliases_json"), []),
        "rules": _load_json_value(row.get("rules_json"), {}),
        "price": row["precio"],
        "duration_minutes": duration_minutes,
        "duration": f"{duration_minutes} min",
        "active": bool(row.get("activo", 1)),
    }


def _staff_from_row(row: dict[str, Any], category_ids: list[str], category_names: list[str]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["nombre"],
        "role": row.get("rol") or "",
        "service_categories": category_ids,
        "category_names": category_names,
        "active": bool(row.get("activo", 1)),
    }


def _unique_identifier(connection: Any, table: str, base_id: str) -> str:
    candidate = base_id or "item"
    suffix = 2
    while connection.execute(f"SELECT 1 FROM {table} WHERE id = ?", (candidate,)).fetchone():
        candidate = f"{base_id}_{suffix}"
        suffix += 1
    return candidate


def seed_operational_data(db_path: Path, config: dict[str, Any], *, timezone: str = "Atlantic/Canary") -> None:
    created_at = now_iso(timezone)
    categories = config.get("service_categories", [])
    services = config.get("services", [])
    staff = config.get("staff", [])

    with connection_scope(db_path) as connection:
        has_categories = connection.execute("SELECT 1 FROM service_categories LIMIT 1").fetchone() is not None
        has_services = connection.execute("SELECT 1 FROM servicios_config LIMIT 1").fetchone() is not None
        has_staff = connection.execute("SELECT 1 FROM personal LIMIT 1").fetchone() is not None

        if not has_categories:
            for category in categories:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO service_categories (id, nombre, capacidad, activo)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        category.get("id"),
                        category.get("name"),
                        int(category.get("default_capacity") or 1),
                        1,
                    ),
                )

        if not has_services:
            for service in services:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO servicios_config
                    (id, nombre, categoria_id, duracion_minutos, precio, aliases_json, rules_json, activo, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        service.get("id"),
                        service.get("name"),
                        service.get("category"),
                        int(service.get("duration_minutes") or 30),
                        service.get("price", "precio a consultar"),
                        json.dumps(service.get("aliases", []), ensure_ascii=False),
                        json.dumps(service.get("rules", {}), ensure_ascii=False),
                        1 if service.get("active", True) else 0,
                        created_at,
                        created_at,
                    ),
                )

        if not has_staff:
            for member in staff:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO personal (id, nombre, rol, activo, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        member.get("id"),
                        member.get("name"),
                        member.get("role"),
                        1 if member.get("active", True) else 0,
                        created_at,
                        created_at,
                    ),
                )
                for category_id in member.get("service_categories", []):
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO personal_categorias (personal_id, categoria_id)
                        VALUES (?, ?)
                        """,
                        (member.get("id"), category_id),
                    )


def list_service_categories(db_path: Path, *, active_only: bool = False) -> list[dict[str, Any]]:
    query = """
        SELECT id, nombre, capacidad, activo
        FROM service_categories
    """
    params: tuple[Any, ...] = ()
    if active_only:
        query += " WHERE activo = 1"
    query += " ORDER BY nombre ASC"

    with connection_scope(db_path) as connection:
        rows = connection.execute(query, params).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["nombre"],
            "capacity": int(row["capacidad"] or 0),
            "active": bool(row["activo"]),
        }
        for row in rows
    ]


def update_category_capacities(db_path: Path, capacities: dict[str, int]) -> None:
    with connection_scope(db_path) as connection:
        for category_id, capacity in capacities.items():
            connection.execute(
                "UPDATE service_categories SET capacidad = ? WHERE id = ?",
                (max(0, int(capacity)), category_id),
            )


def list_services_config(db_path: Path, *, active_only: bool = False) -> list[dict[str, Any]]:
    query = """
        SELECT
            servicios_config.*,
            service_categories.nombre AS categoria_nombre
        FROM servicios_config
        JOIN service_categories ON service_categories.id = servicios_config.categoria_id
    """
    if active_only:
        query += " WHERE servicios_config.activo = 1"
    query += " ORDER BY servicios_config.activo DESC, service_categories.nombre ASC, servicios_config.nombre ASC"

    with connection_scope(db_path) as connection:
        rows = connection.execute(query).fetchall()
    return [_service_from_row(dict(row)) for row in rows]


def get_service_config(
    db_path: Path,
    service_id: str,
    *,
    connection: Any | None = None,
) -> dict[str, Any] | None:
    if connection is None:
        with connection_scope(db_path) as connection:
            row = connection.execute(
                """
                SELECT
                    servicios_config.*,
                    service_categories.nombre AS categoria_nombre
                FROM servicios_config
                JOIN service_categories ON service_categories.id = servicios_config.categoria_id
                WHERE servicios_config.id = ?
                """,
                (service_id,),
            ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT
                servicios_config.*,
                service_categories.nombre AS categoria_nombre
            FROM servicios_config
            JOIN service_categories ON service_categories.id = servicios_config.categoria_id
            WHERE servicios_config.id = ?
            """,
            (service_id,),
        ).fetchone()
    return _service_from_row(dict(row)) if row else None


def get_service_config_by_name(
    db_path: Path,
    service_name: str | None,
    *,
    connection: Any | None = None,
) -> dict[str, Any] | None:
    if not service_name:
        return None
    if connection is None:
        with connection_scope(db_path) as connection:
            row = connection.execute(
                """
                SELECT
                    servicios_config.*,
                    service_categories.nombre AS categoria_nombre
                FROM servicios_config
                JOIN service_categories ON service_categories.id = servicios_config.categoria_id
                WHERE servicios_config.nombre = ?
                LIMIT 1
                """,
                (service_name,),
            ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT
                servicios_config.*,
                service_categories.nombre AS categoria_nombre
            FROM servicios_config
            JOIN service_categories ON service_categories.id = servicios_config.categoria_id
            WHERE servicios_config.nombre = ?
            LIMIT 1
            """,
            (service_name,),
        ).fetchone()
    return _service_from_row(dict(row)) if row else None


def backfill_appointment_service_ids(db_path: Path) -> None:
    with connection_scope(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, servicio
            FROM citas
            WHERE servicio_id IS NULL OR servicio_id = ''
            """
        ).fetchall()
        if not rows:
            return

        service_rows = connection.execute(
            """
            SELECT id, nombre
            FROM servicios_config
            """
        ).fetchall()
        service_ids_by_name = {
            str(row["nombre"]).strip(): str(row["id"]).strip()
            for row in service_rows
            if row["nombre"] and row["id"]
        }

        for row in rows:
            service_id = service_ids_by_name.get(str(row["servicio"] or "").strip())
            if not service_id:
                continue
            connection.execute(
                "UPDATE citas SET servicio_id = ? WHERE id = ?",
                (service_id, row["id"]),
            )


def create_service_config(
    db_path: Path,
    *,
    name: str,
    category_id: str,
    duration_minutes: int,
    price: str,
    active: bool = True,
    aliases: list[str] | None = None,
    rules: dict[str, Any] | None = None,
    timezone: str = "Atlantic/Canary",
) -> dict[str, Any]:
    created_at = now_iso(timezone)
    base_id = slugify_identifier(name)
    with connection_scope(db_path) as connection:
        service_id = _unique_identifier(connection, "servicios_config", base_id)
        connection.execute(
            """
            INSERT INTO servicios_config
            (id, nombre, categoria_id, duracion_minutos, precio, aliases_json, rules_json, activo, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                service_id,
                name.strip(),
                category_id,
                int(duration_minutes),
                price.strip(),
                json.dumps(aliases or [name.strip()], ensure_ascii=False),
                json.dumps(rules or {}, ensure_ascii=False),
                1 if active else 0,
                created_at,
                created_at,
            ),
        )
    return get_service_config(db_path, service_id)  # type: ignore[return-value]


def update_service_config(
    db_path: Path,
    *,
    service_id: str,
    name: str,
    category_id: str,
    duration_minutes: int,
    price: str,
    active: bool,
) -> dict[str, Any] | None:
    current = get_service_config(db_path, service_id)
    if not current:
        return None

    aliases = current.get("aliases") or [name.strip()]
    if current.get("name") != name.strip() and aliases == [current.get("name")]:
        aliases = [name.strip()]

    with connection_scope(db_path) as connection:
        connection.execute(
            """
            UPDATE servicios_config
            SET nombre = ?,
                categoria_id = ?,
                duracion_minutos = ?,
                precio = ?,
                aliases_json = ?,
                activo = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                name.strip(),
                category_id,
                int(duration_minutes),
                price.strip(),
                json.dumps(aliases, ensure_ascii=False),
                1 if active else 0,
                now_iso(),
                service_id,
            ),
        )
    return get_service_config(db_path, service_id)


def set_service_active(db_path: Path, service_id: str, active: bool) -> bool:
    with connection_scope(db_path) as connection:
        cursor = connection.execute(
            "UPDATE servicios_config SET activo = ?, updated_at = ? WHERE id = ?",
            (1 if active else 0, now_iso(), service_id),
        )
    return cursor.rowcount > 0


def list_staff_members(db_path: Path, *, active_only: bool = False) -> list[dict[str, Any]]:
    query = """
        SELECT id, nombre, rol, activo
        FROM personal
    """
    if active_only:
        query += " WHERE activo = 1"
    query += " ORDER BY activo DESC, nombre ASC"

    with connection_scope(db_path) as connection:
        rows = connection.execute(query).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            category_rows = connection.execute(
                """
                SELECT service_categories.id, service_categories.nombre
                FROM personal_categorias
                JOIN service_categories ON service_categories.id = personal_categorias.categoria_id
                WHERE personal_categorias.personal_id = ?
                ORDER BY service_categories.nombre ASC
                """,
                (row["id"],),
            ).fetchall()
            items.append(
                _staff_from_row(
                    dict(row),
                    [item["id"] for item in category_rows],
                    [item["nombre"] for item in category_rows],
                )
            )
    return items


def get_staff_member(db_path: Path, staff_id: str) -> dict[str, Any] | None:
    with connection_scope(db_path) as connection:
        row = connection.execute(
            "SELECT id, nombre, rol, activo FROM personal WHERE id = ?",
            (staff_id,),
        ).fetchone()
        if not row:
            return None
        category_rows = connection.execute(
            """
            SELECT service_categories.id, service_categories.nombre
            FROM personal_categorias
            JOIN service_categories ON service_categories.id = personal_categorias.categoria_id
            WHERE personal_categorias.personal_id = ?
            ORDER BY service_categories.nombre ASC
            """,
            (staff_id,),
        ).fetchall()
    return _staff_from_row(
        dict(row),
        [item["id"] for item in category_rows],
        [item["nombre"] for item in category_rows],
    )


def create_staff_member(
    db_path: Path,
    *,
    name: str,
    role: str | None = None,
    category_ids: list[str] | None = None,
    active: bool = True,
    timezone: str = "Atlantic/Canary",
) -> dict[str, Any]:
    created_at = now_iso(timezone)
    base_id = slugify_identifier(name)
    with connection_scope(db_path) as connection:
        staff_id = _unique_identifier(connection, "personal", base_id)
        connection.execute(
            """
            INSERT INTO personal (id, nombre, rol, activo, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (staff_id, name.strip(), role.strip() if role else None, 1 if active else 0, created_at, created_at),
        )
        for category_id in category_ids or []:
            connection.execute(
                "INSERT OR IGNORE INTO personal_categorias (personal_id, categoria_id) VALUES (?, ?)",
                (staff_id, category_id),
            )
    return get_staff_member(db_path, staff_id)  # type: ignore[return-value]


def update_staff_member(
    db_path: Path,
    *,
    staff_id: str,
    name: str,
    role: str | None = None,
    category_ids: list[str] | None = None,
    active: bool = True,
) -> dict[str, Any] | None:
    with connection_scope(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE personal
            SET nombre = ?,
                rol = ?,
                activo = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (name.strip(), role.strip() if role else None, 1 if active else 0, now_iso(), staff_id),
        )
        if cursor.rowcount <= 0:
            return None
        connection.execute("DELETE FROM personal_categorias WHERE personal_id = ?", (staff_id,))
        for category_id in category_ids or []:
            connection.execute(
                "INSERT OR IGNORE INTO personal_categorias (personal_id, categoria_id) VALUES (?, ?)",
                (staff_id, category_id),
            )
    return get_staff_member(db_path, staff_id)


def set_staff_active(db_path: Path, staff_id: str, active: bool) -> bool:
    with connection_scope(db_path) as connection:
        cursor = connection.execute(
            "UPDATE personal SET activo = ?, updated_at = ? WHERE id = ?",
            (1 if active else 0, now_iso(), staff_id),
        )
    return cursor.rowcount > 0


def list_appointments(db_path: Path) -> list[dict[str, Any]]:
    with connection_scope(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                citas.id,
                citas.fecha,
                citas.hora,
                citas.franja,
                citas.servicio_id,
                citas.servicio,
                citas.estado,
                citas.notas,
                citas.created_at,
                clientes.id AS cliente_id,
                clientes.nombre AS cliente_nombre,
                clientes.telefono AS cliente_telefono
            FROM citas
            JOIN clientes ON clientes.id = citas.cliente_id
            ORDER BY date(citas.fecha) ASC, time(citas.hora) ASC, citas.id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def list_customer_appointments(db_path: Path, customer_id: int) -> list[dict[str, Any]]:
    with connection_scope(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, fecha, hora, franja, servicio_id, servicio, estado, notas, created_at
            FROM citas
            WHERE cliente_id = ?
            ORDER BY date(fecha) DESC, time(hora) DESC, id DESC
            """,
            (customer_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_appointment(
    db_path: Path,
    appointment_id: int,
    *,
    connection: Any | None = None,
) -> dict[str, Any] | None:
    if connection is None:
        with connection_scope(db_path) as connection:
            row = connection.execute(
                """
                SELECT
                    citas.*,
                    clientes.id AS cliente_id,
                    clientes.nombre AS cliente_nombre,
                    clientes.telefono AS cliente_telefono
                FROM citas
                JOIN clientes ON clientes.id = citas.cliente_id
                WHERE citas.id = ?
                """,
                (appointment_id,),
            ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT
                citas.*,
                clientes.id AS cliente_id,
                clientes.nombre AS cliente_nombre,
                clientes.telefono AS cliente_telefono
            FROM citas
            JOIN clientes ON clientes.id = citas.cliente_id
            WHERE citas.id = ?
            """,
            (appointment_id,),
        ).fetchone()
    return dict(row) if row else None


def refresh_customer_last_visit(connection: Any, customer_id: int) -> None:
    last_completed = connection.execute(
        """
        SELECT fecha
        FROM citas
        WHERE cliente_id = ?
          AND estado = 'completada'
        ORDER BY date(fecha) DESC, time(hora) DESC, id DESC
        LIMIT 1
        """,
        (customer_id,),
    ).fetchone()
    connection.execute(
        "UPDATE clientes SET ultima_visita = ? WHERE id = ?",
        (last_completed[0] if last_completed else None, customer_id),
    )


def has_active_appointment_at(
    db_path: Path,
    *,
    date: str,
    time: str,
    exclude_appointment_id: int | None = None,
    connection: Any | None = None,
) -> bool:
    placeholders = ", ".join("?" for _ in ACTIVE_APPOINTMENT_STATES)
    extra_clause = ""
    params: tuple[Any, ...] = (date, time, *ACTIVE_APPOINTMENT_STATES)
    if exclude_appointment_id is not None:
        extra_clause = "AND id != ?"
        params = (date, time, *ACTIVE_APPOINTMENT_STATES, exclude_appointment_id)

    if connection is None:
        with connection_scope(db_path) as connection:
            row = connection.execute(
                f"""
                SELECT id
                FROM citas
                WHERE fecha = ?
                  AND hora = ?
                  AND estado IN ({placeholders})
                  {extra_clause}
                LIMIT 1
                """,
                params,
            ).fetchone()
    else:
        row = connection.execute(
            f"""
            SELECT id
            FROM citas
            WHERE fecha = ?
              AND hora = ?
              AND estado IN ({placeholders})
              {extra_clause}
            LIMIT 1
            """,
            params,
        ).fetchone()
    return row is not None


def list_active_appointments_on_date(
    db_path: Path,
    *,
    date: str,
    exclude_appointment_id: int | None = None,
    connection: Any | None = None,
) -> list[dict[str, Any]]:
    placeholders = ", ".join("?" for _ in ACTIVE_APPOINTMENT_STATES)
    extra_clause = ""
    params: tuple[Any, ...] = (date, *ACTIVE_APPOINTMENT_STATES)
    if exclude_appointment_id is not None:
        extra_clause = "AND id != ?"
        params = (date, *ACTIVE_APPOINTMENT_STATES, exclude_appointment_id)

    if connection is None:
        with connection_scope(db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT id, fecha, hora, servicio_id, servicio, estado
                FROM citas
                WHERE fecha = ?
                  AND estado IN ({placeholders})
                  {extra_clause}
                ORDER BY time(hora) ASC, id DESC
                """,
                params,
            ).fetchall()
    else:
        rows = connection.execute(
            f"""
            SELECT id, fecha, hora, servicio_id, servicio, estado
            FROM citas
            WHERE fecha = ?
              AND estado IN ({placeholders})
              {extra_clause}
            ORDER BY time(hora) ASC, id DESC
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def create_appointment(
    db_path: Path,
    *,
    customer_id: int,
    date: str,
    time: str,
    part_of_day: str | None = None,
    service_id: str | None = None,
    service: str,
    status: str = "pendiente",
    notes: str | None = None,
    timezone: str = "Atlantic/Canary",
    connection: Any | None = None,
) -> dict[str, Any]:
    if status not in APPOINTMENT_STATES:
        raise ValueError("Estado de cita no válido")

    created_at = now_iso(timezone)
    if connection is None:
        with connection_scope(db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO citas (cliente_id, fecha, hora, franja, servicio_id, servicio, estado, notas, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    customer_id,
                    date.strip(),
                    time.strip(),
                    part_of_day,
                    service_id.strip() if service_id else None,
                    service.strip(),
                    status,
                    notes,
                    created_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM citas WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
    else:
        cursor = connection.execute(
            """
            INSERT INTO citas (cliente_id, fecha, hora, franja, servicio_id, servicio, estado, notas, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                date.strip(),
                time.strip(),
                part_of_day,
                service_id.strip() if service_id else None,
                service.strip(),
                status,
                notes,
                created_at,
            ),
        )
        row = connection.execute(
            "SELECT * FROM citas WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


def update_appointment_status(db_path: Path, appointment_id: int, status: str) -> bool:
    if status not in APPOINTMENT_STATES:
        return False

    with connection_scope(db_path) as connection:
        appointment = connection.execute(
            "SELECT cliente_id FROM citas WHERE id = ?",
            (appointment_id,),
        ).fetchone()
        if not appointment:
            return False

        cursor = connection.execute(
            "UPDATE citas SET estado = ? WHERE id = ?",
            (status, appointment_id),
        )
        refresh_customer_last_visit(connection, appointment["cliente_id"])

    return cursor.rowcount > 0


def update_appointment(
    db_path: Path,
    *,
    appointment_id: int,
    date: str,
    time: str,
    service_id: str | None,
    service: str,
    status: str,
    part_of_day: str | None = None,
    notes: str | None = None,
    connection: Any | None = None,
) -> dict[str, Any] | None:
    if status not in APPOINTMENT_STATES:
        raise ValueError("Estado de cita no válido")

    if connection is None:
        with connection_scope(db_path) as connection:
            appointment = connection.execute(
                "SELECT cliente_id FROM citas WHERE id = ?",
                (appointment_id,),
            ).fetchone()
            if not appointment:
                return None

            connection.execute(
                """
                UPDATE citas
                SET fecha = ?,
                    hora = ?,
                    servicio_id = ?,
                    servicio = ?,
                    estado = ?,
                    notas = ?,
                    franja = ?
                WHERE id = ?
                """,
                (
                    date.strip(),
                    time.strip(),
                    service_id.strip() if service_id else None,
                    service.strip(),
                    status,
                    notes,
                    part_of_day,
                    appointment_id,
                ),
            )
            refresh_customer_last_visit(connection, appointment["cliente_id"])
            row = connection.execute(
                "SELECT * FROM citas WHERE id = ?",
                (appointment_id,),
            ).fetchone()
    else:
        appointment = connection.execute(
            "SELECT cliente_id FROM citas WHERE id = ?",
            (appointment_id,),
        ).fetchone()
        if not appointment:
            return None

        connection.execute(
            """
            UPDATE citas
            SET fecha = ?,
                hora = ?,
                servicio_id = ?,
                servicio = ?,
                estado = ?,
                notas = ?,
                franja = ?
            WHERE id = ?
            """,
            (
                date.strip(),
                time.strip(),
                service_id.strip() if service_id else None,
                service.strip(),
                status,
                notes,
                part_of_day,
                appointment_id,
            ),
        )
        refresh_customer_last_visit(connection, appointment["cliente_id"])
        row = connection.execute(
            "SELECT * FROM citas WHERE id = ?",
            (appointment_id,),
        ).fetchone()
    return dict(row) if row else None
