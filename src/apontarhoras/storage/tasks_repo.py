"""Tabela `tasks`."""

import sqlite3
from datetime import datetime

from apontarhoras.domain.task import Task
from apontarhoras.storage.db import from_db_time, to_db_time

_COLUMNS = "id, name, rd_eligible, active, created_at"


def _to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        name=row["name"],
        rd_eligible=bool(row["rd_eligible"]),
        active=bool(row["active"]),
        created_at=from_db_time(row["created_at"]),
    )


def get(conn: sqlite3.Connection, task_id: int) -> Task | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _to_task(row) if row else None


def list_all(conn: sqlite3.Connection, *, only_active: bool) -> list[Task]:
    where = "WHERE active = 1" if only_active else ""
    rows = conn.execute(f"SELECT {_COLUMNS} FROM tasks {where} ORDER BY active DESC, name COLLATE NOCASE").fetchall()
    return [_to_task(row) for row in rows]


def name_taken(conn: sqlite3.Connection, name: str, *, exclude_id: int | None = None) -> bool:
    row = conn.execute("SELECT 1 FROM tasks WHERE name = ? AND id IS NOT ?", (name, exclude_id)).fetchone()
    return row is not None


def insert(conn: sqlite3.Connection, *, name: str, rd_eligible: bool, now: datetime) -> int:
    cursor = conn.execute(
        "INSERT INTO tasks (name, rd_eligible, created_at) VALUES (?, ?, ?)",
        (name, int(rd_eligible), to_db_time(now)),
    )
    return cursor.lastrowid


def update(conn: sqlite3.Connection, task_id: int, *, name: str, rd_eligible: bool, active: bool) -> None:
    conn.execute(
        "UPDATE tasks SET name = ?, rd_eligible = ?, active = ? WHERE id = ?",
        (name, int(rd_eligible), int(active), task_id),
    )


def delete(conn: sqlite3.Connection, task_id: int) -> None:
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
