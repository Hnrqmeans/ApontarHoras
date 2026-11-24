"""Tabela `sessions` (guarda só o hash do token)."""

import sqlite3
from datetime import datetime

from apontarhoras.storage.db import to_db_time


def insert(conn: sqlite3.Connection, token_hash: str, user_id: int, *, now: datetime, expires: datetime) -> None:
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token_hash, user_id, to_db_time(now), to_db_time(expires)),
    )


def user_id_for(conn: sqlite3.Connection, token_hash: str, now: datetime) -> int | None:
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > ?", (token_hash, to_db_time(now))
    ).fetchone()
    return row["user_id"] if row else None


def delete(conn: sqlite3.Connection, token_hash: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def delete_for_user(conn: sqlite3.Connection, user_id: int, *, keep: str | None = None) -> None:
    conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash IS NOT ?", (user_id, keep))


def delete_expired(conn: sqlite3.Connection, now: datetime) -> None:
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (to_db_time(now),))
