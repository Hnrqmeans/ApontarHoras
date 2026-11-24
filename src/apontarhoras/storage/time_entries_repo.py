"""Tabela `time_entries` (apontamentos), lida já com os nomes de usuário, projeto e tarefa."""

import sqlite3
from datetime import date, datetime

from apontarhoras.domain.time_entry import TimeEntry
from apontarhoras.storage.db import from_db_time, to_db_time

_SELECT = """
SELECT t.id, t.user_id, u.name AS user_name, t.work_date, t.project_id, p.code AS project_code,
       p.name AS project_name, t.task_id, k.name AS task_name, t.start_minute, t.end_minute, t.break_minutes,
       t.minutes, t.rd_eligible, t.description, t.created_at, t.updated_at
FROM time_entries t
JOIN users u ON u.id = t.user_id
JOIN projects p ON p.id = t.project_id
JOIN tasks k ON k.id = t.task_id
"""

_ORDER = " ORDER BY t.work_date, t.start_minute, t.id"


def _to_entry(row: sqlite3.Row) -> TimeEntry:
    return TimeEntry(
        id=row["id"],
        user_id=row["user_id"],
        user_name=row["user_name"],
        work_date=date.fromisoformat(row["work_date"]),
        project_id=row["project_id"],
        project_code=row["project_code"],
        project_name=row["project_name"],
        task_id=row["task_id"],
        task_name=row["task_name"],
        start_minute=row["start_minute"],
        end_minute=row["end_minute"],
        break_minutes=row["break_minutes"],
        minutes=row["minutes"],
        rd_eligible=bool(row["rd_eligible"]),
        description=row["description"],
        created_at=from_db_time(row["created_at"]),
        updated_at=from_db_time(row["updated_at"]),
    )


def get(conn: sqlite3.Connection, entry_id: int) -> TimeEntry | None:
    row = conn.execute(f"{_SELECT} WHERE t.id = ?", (entry_id,)).fetchone()
    return _to_entry(row) if row else None


def list_for_user(conn: sqlite3.Connection, user_id: int, first_day: date, last_day: date) -> list[TimeEntry]:
    rows = conn.execute(
        f"{_SELECT} WHERE t.user_id = ? AND t.work_date BETWEEN ? AND ?{_ORDER}",
        (user_id, first_day.isoformat(), last_day.isoformat()),
    ).fetchall()
    return [_to_entry(row) for row in rows]


def list_same_day(
    conn: sqlite3.Connection, user_id: int, work_date: date, *, exclude_id: int | None = None
) -> list[TimeEntry]:
    rows = conn.execute(
        f"{_SELECT} WHERE t.user_id = ? AND t.work_date = ? AND t.id IS NOT ?{_ORDER}",
        (user_id, work_date.isoformat(), exclude_id),
    ).fetchall()
    return [_to_entry(row) for row in rows]


def count_by(conn: sqlite3.Connection, column: str, value: int) -> int:
    """Quantos apontamentos usam o usuário/projeto/tarefa (bloqueia exclusão)."""
    if column not in ("user_id", "project_id", "task_id"):
        raise ValueError(column)
    return conn.execute(f"SELECT COUNT(*) FROM time_entries WHERE {column} = ?", (value,)).fetchone()[0]


def insert(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    work_date: date,
    project_id: int,
    task_id: int,
    start_minute: int,
    end_minute: int,
    break_minutes: int,
    minutes: int,
    rd_eligible: bool,
    description: str,
    now: datetime,
) -> int:
    cursor = conn.execute(
        "INSERT INTO time_entries (user_id, work_date, project_id, task_id, start_minute, end_minute, break_minutes, "
        "minutes, rd_eligible, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, work_date.isoformat(), project_id, task_id, start_minute, end_minute, break_minutes, minutes,
         int(rd_eligible), description, to_db_time(now), to_db_time(now)),
    )
    return cursor.lastrowid


def update(
    conn: sqlite3.Connection,
    entry_id: int,
    *,
    work_date: date,
    project_id: int,
    task_id: int,
    start_minute: int,
    end_minute: int,
    break_minutes: int,
    minutes: int,
    rd_eligible: bool,
    description: str,
    now: datetime,
) -> None:
    conn.execute(
        "UPDATE time_entries SET work_date = ?, project_id = ?, task_id = ?, start_minute = ?, end_minute = ?, "
        "break_minutes = ?, minutes = ?, rd_eligible = ?, description = ?, updated_at = ? WHERE id = ?",
        (work_date.isoformat(), project_id, task_id, start_minute, end_minute, break_minutes, minutes,
         int(rd_eligible), description, to_db_time(now), entry_id),
    )


def delete(conn: sqlite3.Connection, entry_id: int) -> None:
    conn.execute("DELETE FROM time_entries WHERE id = ?", (entry_id,))
