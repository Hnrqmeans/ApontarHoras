"""Tabela `audit_log` (só inserção e leitura: auditoria não se edita)."""

import json
import sqlite3
from datetime import datetime
from typing import Any

from apontarhoras.domain.audit import AuditEntry
from apontarhoras.storage.db import from_db_time, to_db_time


def insert(
    conn: sqlite3.Connection,
    *,
    at: datetime,
    actor_id: int | None,
    actor_name: str,
    action: str,
    entity: str,
    entity_id: int | None,
    details: dict[str, Any],
) -> None:
    conn.execute(
        "INSERT INTO audit_log (at, actor_id, actor_name, action, entity, entity_id, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (to_db_time(at), actor_id, actor_name, action, entity, entity_id, json.dumps(details, ensure_ascii=False)),
    )


def list_recent(conn: sqlite3.Connection, limit: int) -> list[AuditEntry]:
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [
        AuditEntry(
            id=row["id"],
            at=from_db_time(row["at"]),
            actor_id=row["actor_id"],
            actor_name=row["actor_name"],
            action=row["action"],
            entity=row["entity"],
            entity_id=row["entity_id"],
            details=json.loads(row["details"]),
        )
        for row in rows
    ]
