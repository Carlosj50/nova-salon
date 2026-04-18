from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from pathlib import Path
from typing import Iterator


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def connection_scope(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = get_connection(db_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(db_path: Path) -> None:
    with connection_scope(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                telefono TEXT NOT NULL UNIQUE,
                email TEXT,
                notas TEXT,
                fecha_alta TEXT NOT NULL,
                ultima_visita TEXT
            );

            CREATE TABLE IF NOT EXISTS citas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                franja TEXT,
                servicio_id TEXT,
                servicio TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente', 'confirmada', 'completada', 'cancelada')),
                notas TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (cliente_id) REFERENCES clientes(id),
                FOREIGN KEY (servicio_id) REFERENCES servicios_config(id)
            );

            CREATE INDEX IF NOT EXISTS idx_clientes_telefono
                ON clientes(telefono);

            CREATE INDEX IF NOT EXISTS idx_citas_fecha_hora
                ON citas(fecha, hora);

            CREATE INDEX IF NOT EXISTS idx_citas_cliente
                ON citas(cliente_id);

            CREATE TABLE IF NOT EXISTS canales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_canal TEXT NOT NULL UNIQUE,
                activo INTEGER NOT NULL DEFAULT 0,
                modo TEXT NOT NULL DEFAULT 'demo'
                    CHECK (modo IN ('demo', 'preparado', 'conectado')),
                telefono TEXT,
                nombre_visible TEXT,
                config_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS service_categories (
                id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                capacidad INTEGER NOT NULL DEFAULT 1,
                activo INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS servicios_config (
                id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                categoria_id TEXT NOT NULL,
                duracion_minutos INTEGER NOT NULL,
                precio TEXT NOT NULL,
                aliases_json TEXT,
                rules_json TEXT,
                activo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (categoria_id) REFERENCES service_categories(id)
            );

            CREATE INDEX IF NOT EXISTS idx_servicios_categoria
                ON servicios_config(categoria_id);

            CREATE INDEX IF NOT EXISTS idx_servicios_activo
                ON servicios_config(activo);

            CREATE TABLE IF NOT EXISTS personal (
                id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                rol TEXT,
                activo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS personal_categorias (
                personal_id TEXT NOT NULL,
                categoria_id TEXT NOT NULL,
                PRIMARY KEY (personal_id, categoria_id),
                FOREIGN KEY (personal_id) REFERENCES personal(id) ON DELETE CASCADE,
                FOREIGN KEY (categoria_id) REFERENCES service_categories(id)
            );

            CREATE TABLE IF NOT EXISTS business_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(citas)").fetchall()
        }
        if "franja" not in columns:
            connection.execute("ALTER TABLE citas ADD COLUMN franja TEXT")
        if "servicio_id" not in columns:
            connection.execute("ALTER TABLE citas ADD COLUMN servicio_id TEXT")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_citas_servicio_id ON citas(servicio_id)"
        )
