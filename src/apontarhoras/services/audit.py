"""Gravação e consulta da auditoria."""

import sqlite3
from datetime import datetime
from typing import Any

from apontarhoras.domain.audit import AuditEntry
from apontarhoras.domain.user import User
from apontarhoras.services.common import require_admin, utcnow
from apontarhoras.storage import audit_repo


def record(
    conn: sqlite3.Connection,
    actor: User | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    details: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
    actor_name: str | None = None,
) -> None:
    """Chamar dentro da transação da operação. Nunca colocar senha/hash em `details`."""
    audit_repo.insert(
        conn,
        at=now or utcnow(),
        actor_id=actor.id if actor else None,
        actor_name=actor_name or (f"{actor.name} ({actor.login})" if actor else "—"),
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details or {},
    )


def list_recent(conn: sqlite3.Connection, actor: User | None, limit: int = 200) -> list[AuditEntry]:
    require_admin(actor)
    return audit_repo.list_recent(conn, limit)
