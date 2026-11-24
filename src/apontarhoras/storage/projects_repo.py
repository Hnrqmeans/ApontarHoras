"""Tabela `projects`."""

import sqlite3
from datetime import datetime

from apontarhoras.domain.project import Project
from apontarhoras.storage.db import from_db_time, to_db_time

_COLUMNS = "id, code, name, description, active, created_at"


def _to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        description=row["description"],
        active=bool(row["active"]),
        created_at=from_db_time(row["created_at"]),
    )


def get(conn: sqlite3.Connection, project_id: int) -> Project | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _to_project(row) if row else None


def list_all(conn: sqlite3.Connection, *, only_active: bool) -> list[Project]:
    where = "WHERE active = 1" if only_active else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM projects {where} ORDER BY active DESC, code COLLATE NOCASE"
    ).fetchall()
    return [_to_project(row) for row in rows]


def code_taken(conn: sqlite3.Connection, code: str, *, exclude_id: int | None = None) -> bool:
    row = conn.execute("SELECT 1 FROM projects WHERE code = ? AND id IS NOT ?", (code, exclude_id)).fetchone()
    return row is not None


def insert(conn: sqlite3.Connection, *, code: str, name: str, description: str, now: datetime) -> int:
    cursor = conn.execute(
        "INSERT INTO projects (code, name, description, created_at) VALUES (?, ?, ?, ?)",
        (code, name, description, to_db_time(now)),
    )
    return cursor.lastrowid


def update(
    conn: sqlite3.Connection, project_id: int, *, code: str, name: str, description: str, active: bool
) -> None:
    conn.execute(
        "UPDATE projects SET code = ?, name = ?, description = ?, active = ? WHERE id = ?",
        (code, name, description, int(active), project_id),
    )


def delete(conn: sqlite3.Connection, project_id: int) -> None:
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
