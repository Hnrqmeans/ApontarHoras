"""Tabela `users`."""

import sqlite3
from datetime import datetime

from apontarhoras.domain.user import Role, User
from apontarhoras.storage.db import from_db_time, to_db_time

_COLUMNS = "id, name, login, role, active, must_change_password, failed_attempts, locked_until, created_at"


def _to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        name=row["name"],
        login=row["login"],
        role=Role(row["role"]),
        active=bool(row["active"]),
        must_change_password=bool(row["must_change_password"]),
        failed_attempts=row["failed_attempts"],
        locked_until=from_db_time(row["locked_until"]),
        created_at=from_db_time(row["created_at"]),
    )


def get(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone()
    return _to_user(row) if row else None


def get_by_login(conn: sqlite3.Connection, login: str) -> User | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM users WHERE login = ?", (login,)).fetchone()
    return _to_user(row) if row else None


def get_with_hash(conn: sqlite3.Connection, login: str) -> tuple[User, str] | None:
    row = conn.execute(f"SELECT {_COLUMNS}, password_hash FROM users WHERE login = ?", (login,)).fetchone()
    return (_to_user(row), row["password_hash"]) if row else None


def get_password_hash(conn: sqlite3.Connection, user_id: int) -> str | None:
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["password_hash"] if row else None


def list_all(conn: sqlite3.Connection) -> list[User]:
    rows = conn.execute(f"SELECT {_COLUMNS} FROM users ORDER BY active DESC, name COLLATE NOCASE").fetchall()
    return [_to_user(row) for row in rows]


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def count_active_admins(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = ? AND active = 1", (Role.ADMIN.value,)
    ).fetchone()[0]


def login_taken(conn: sqlite3.Connection, login: str) -> bool:
    return conn.execute("SELECT 1 FROM users WHERE login = ?", (login,)).fetchone() is not None


def insert(
    conn: sqlite3.Connection,
    *,
    name: str,
    login: str,
    password_hash: str,
    role: Role,
    must_change_password: bool,
    now: datetime,
) -> int:
    cursor = conn.execute(
        "INSERT INTO users (name, login, password_hash, role, must_change_password, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, login, password_hash, role.value, int(must_change_password), to_db_time(now)),
    )
    return cursor.lastrowid


def update_profile(conn: sqlite3.Connection, user_id: int, *, name: str, role: Role, active: bool) -> None:
    conn.execute(
        "UPDATE users SET name = ?, role = ?, active = ? WHERE id = ?", (name, role.value, int(active), user_id)
    )


def set_password(conn: sqlite3.Connection, user_id: int, password_hash: str, *, must_change: bool) -> None:
    conn.execute(
        "UPDATE users SET password_hash = ?, must_change_password = ?, failed_attempts = 0, locked_until = NULL "
        "WHERE id = ?",
        (password_hash, int(must_change), user_id),
    )


def set_login_state(
    conn: sqlite3.Connection, user_id: int, *, failed_attempts: int, locked_until: datetime | None
) -> None:
    conn.execute(
        "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
        (failed_attempts, to_db_time(locked_until) if locked_until else None, user_id),
    )


def delete(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
