"""Tabela `audit_log` (só inserção e leitura: auditoria não se edita), com a corrente de selos (domain/audit_chain)."""

import json
import sqlite3
from datetime import datetime
from typing import Any

from apontarhoras.domain.audit import AuditEntry
from apontarhoras.domain.audit_chain import GENESIS_HASH, ChainCheck, canonical_content, chain_hash
from apontarhoras.storage.db import from_db_time, to_db_time, transaction


def _row_hash(prev_hash: str, row: sqlite3.Row) -> str:
    content = canonical_content(
        at=row["at"],
        actor_id=row["actor_id"],
        actor_name=row["actor_name"],
        action=row["action"],
        entity=row["entity"],
        entity_id=row["entity_id"],
        details=json.loads(row["details"]),
    )
    return chain_hash(prev_hash, content)


def _last_hash(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    return row["hash"] if row and row["hash"] else GENESIS_HASH


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
    """Lê o selo do último registro e grava o novo já selado, na mesma transação (quem chega depois espera)."""
    at_text = to_db_time(at)
    details_text = json.dumps(details, ensure_ascii=False)
    content = canonical_content(
        at=at_text,
        actor_id=actor_id,
        actor_name=actor_name,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=json.loads(details_text),  # exatamente o que fica gravado (ex.: tupla vira lista)
    )
    with transaction(conn):
        prev_hash = _last_hash(conn)
        conn.execute(
            "INSERT INTO audit_log (at, actor_id, actor_name, action, entity, entity_id, details, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (at_text, actor_id, actor_name, action, entity, entity_id, details_text, prev_hash,
             chain_hash(prev_hash, content)),
        )


def seal_pending(conn: sqlite3.Connection) -> int:
    """Sela, em ordem de id, os registros ainda sem selo (gravados antes da migração 003). Devolve quantos selou."""
    with transaction(conn):
        rows = conn.execute("SELECT * FROM audit_log WHERE hash IS NULL ORDER BY id").fetchall()
        for row in rows:
            before = conn.execute(
                "SELECT hash FROM audit_log WHERE id < ? ORDER BY id DESC LIMIT 1", (row["id"],)
            ).fetchone()
            prev_hash = before["hash"] if before and before["hash"] else GENESIS_HASH
            conn.execute(
                "UPDATE audit_log SET prev_hash = ?, hash = ? WHERE id = ?",
                (prev_hash, _row_hash(prev_hash, row), row["id"]),
            )
    return len(rows)


def verify_chain(conn: sqlite3.Connection) -> ChainCheck:
    """Confere os registros em ordem de id: cada selo bate com o conteúdo e aponta para o selo do anterior."""
    expected_prev = GENESIS_HASH
    total = 0
    last_id = None
    for row in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        total += 1
        try:
            intact = row["prev_hash"] == expected_prev and row["hash"] == _row_hash(expected_prev, row)
        except (ValueError, TypeError):  # detalhes que não são mais JSON válido
            intact = False
        if not intact:
            return ChainCheck(total=total, broken_id=row["id"], last_id=last_id,
                              last_hash=expected_prev if last_id else None)
        expected_prev = row["hash"]
        last_id = row["id"]
    return ChainCheck(total=total, last_id=last_id, last_hash=expected_prev if last_id else None)


def get_hash(conn: sqlite3.Connection, audit_id: int) -> str | None:
    row = conn.execute("SELECT hash FROM audit_log WHERE id = ?", (audit_id,)).fetchone()
    return row["hash"] if row else None


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
