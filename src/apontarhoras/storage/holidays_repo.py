"""Tabela `holidays`."""

import sqlite3
from datetime import date, datetime

from apontarhoras.domain.holiday import Holiday
from apontarhoras.storage.db import from_db_time, to_db_time

_COLUMNS = "id, day, description, created_at"


def _to_holiday(row: sqlite3.Row) -> Holiday:
    return Holiday(
        id=row["id"],
        day=date.fromisoformat(row["day"]),
        description=row["description"],
        created_at=from_db_time(row["created_at"]),
    )


def get(conn: sqlite3.Connection, holiday_id: int) -> Holiday | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM holidays WHERE id = ?", (holiday_id,)).fetchone()
    return _to_holiday(row) if row else None


def list_between(conn: sqlite3.Connection, first: date, last: date) -> list[Holiday]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM holidays WHERE day BETWEEN ? AND ? ORDER BY day",
        (first.isoformat(), last.isoformat()),
    ).fetchall()
    return [_to_holiday(row) for row in rows]


def day_taken(conn: sqlite3.Connection, day: date) -> bool:
    return conn.execute("SELECT 1 FROM holidays WHERE day = ?", (day.isoformat(),)).fetchone() is not None


def insert(conn: sqlite3.Connection, *, day: date, description: str, now: datetime) -> int:
    cursor = conn.execute(
        "INSERT INTO holidays (day, description, created_at) VALUES (?, ?, ?)",
        (day.isoformat(), description, to_db_time(now)),
    )
    return cursor.lastrowid


def delete(conn: sqlite3.Connection, holiday_id: int) -> None:
    conn.execute("DELETE FROM holidays WHERE id = ?", (holiday_id,))
