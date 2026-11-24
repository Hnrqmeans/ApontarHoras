"""Importar projetos colando a lista da planilha atual (só o responsável).

Dois passos: pré-visualizar (nada é gravado) e importar (o texto volta do formulário e é revalidado aqui).
Cada projeto novo passa pelas mesmas regras e auditoria do cadastro manual; tudo numa transação só.
"""

import sqlite3
from datetime import datetime

from apontarhoras.domain.project import Project
from apontarhoras.domain.project_import import ImportPreview, build_preview
from apontarhoras.domain.user import User
from apontarhoras.services import projects_service
from apontarhoras.services.common import require_admin, utcnow
from apontarhoras.storage import projects_repo
from apontarhoras.storage.db import transaction


def _existing_codes(conn: sqlite3.Connection) -> set[str]:
    return {project.code for project in projects_repo.list_all(conn, only_active=False)}


def preview(conn: sqlite3.Connection, actor: User | None, text: str) -> ImportPreview:
    require_admin(actor)
    return build_preview(text, _existing_codes(conn))


def import_projects(
    conn: sqlite3.Connection,
    actor: User | None,
    text: str,
    *,
    rd_eligible: bool = True,
    now: datetime | None = None,
) -> list[Project]:
    """Cria as linhas novas; as que já existem (ou ficaram inválidas) são ignoradas. Devolve os criados."""
    admin = require_admin(actor)
    now = now or utcnow()
    with transaction(conn):
        result = build_preview(text, _existing_codes(conn))
        return [
            projects_service.create_project(
                conn, admin, code=line.code, name=line.name, rd_eligible=rd_eligible, now=now
            )
            for line in result.new_lines
        ]
