"""Consultas do relatório (apontamentos de todos, com filtros) e tabela `month_reviews` (conferência do mês).

Reaproveita a consulta e a conversão de `time_entries_repo` para os apontamentos saírem iguais em todo o app.
"""

import sqlite3
from datetime import date, datetime

from apontarhoras.domain.report import MonthReview
from apontarhoras.domain.time_entry import TimeEntry
from apontarhoras.storage.db import from_db_time, to_db_time
from apontarhoras.storage.time_entries_repo import _SELECT, _to_entry

_REPORT_ORDER = " ORDER BY t.work_date, u.name COLLATE NOCASE, t.start_minute, t.id"


def list_entries(
    conn: sqlite3.Connection,
    first_day: date,
    last_day: date,
    *,
    user_id: int | None = None,
    project_id: int | None = None,
    task_id: int | None = None,
    rd_eligible: bool | None = None,
) -> list[TimeEntry]:
    """Apontamentos do período; filtro `None` = todos. Ordem: data, colaborador, início."""
    where = ["t.work_date BETWEEN ? AND ?"]
    params: list[object] = [first_day.isoformat(), last_day.isoformat()]
    for column, value in (("t.user_id", user_id), ("t.project_id", project_id), ("t.task_id", task_id)):
        if value is not None:
            where.append(f"{column} = ?")
            params.append(value)
    if rd_eligible is not None:
        where.append("t.rd_eligible = ?")
        params.append(int(rd_eligible))
    rows = conn.execute(f"{_SELECT} WHERE {' AND '.join(where)}{_REPORT_ORDER}", params).fetchall()
    return [_to_entry(row) for row in rows]


# ---- conferência do mês --------------------------------------------------------------------------------------

_REVIEW_COLUMNS = "id, year, month, reviewer_name, reviewed_at, entry_count, total_minutes, seal"


def _to_review(row: sqlite3.Row) -> MonthReview:
    return MonthReview(
        id=row["id"],
        year=row["year"],
        month=row["month"],
        reviewer_name=row["reviewer_name"],
        reviewed_at=from_db_time(row["reviewed_at"]),
        entry_count=row["entry_count"],
        total_minutes=row["total_minutes"],
        seal=row["seal"],
    )


def insert_review(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    reviewer_id: int,
    reviewer_name: str,
    now: datetime,
    entry_count: int,
    total_minutes: int,
    seal: str,
) -> int:
    cursor = conn.execute(
        "INSERT INTO month_reviews (year, month, reviewer_id, reviewer_name, reviewed_at, entry_count, total_minutes, "
        "seal) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (year, month, reviewer_id, reviewer_name, to_db_time(now), entry_count, total_minutes, seal),
    )
    return cursor.lastrowid


def latest_review(conn: sqlite3.Connection, year: int, month: int) -> MonthReview | None:
    """A última conferência do mês (é a que vale)."""
    row = conn.execute(
        f"SELECT {_REVIEW_COLUMNS} FROM month_reviews WHERE year = ? AND month = ? ORDER BY id DESC LIMIT 1",
        (year, month),
    ).fetchone()
    return _to_review(row) if row else None
