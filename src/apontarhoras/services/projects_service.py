"""Cadastro de projetos de P&D (o responsável cadastra; todos veem os ativos)."""

import sqlite3
from datetime import datetime

from apontarhoras.domain.audit import changes
from apontarhoras.domain.errors import NotFound, ValidationError
from apontarhoras.domain.project import (
    Project,
    normalize_code,
    normalize_text,
    validate_code,
    validate_description,
    validate_name,
)
from apontarhoras.domain.user import User
from apontarhoras.services import audit
from apontarhoras.services.common import require_admin, require_user, utcnow
from apontarhoras.storage import projects_repo, time_entries_repo
from apontarhoras.storage.db import transaction


def _snapshot(project: Project) -> dict:
    return {
        "código": project.code,
        "nome": project.name,
        "descrição": project.description,
        "ativo": project.active,
        "lei do bem": project.rd_eligible,
    }


def _get(conn: sqlite3.Connection, project_id: int) -> Project:
    project = projects_repo.get(conn, project_id)
    if project is None:
        raise NotFound("Projeto não encontrado.")
    return project


def _clean(code: str, name: str, description: str) -> tuple[str, str, str]:
    code, name, description = normalize_code(code), normalize_text(name), description.strip()
    validate_code(code)
    validate_name(name)
    validate_description(description)
    return code, name, description


def list_projects(conn: sqlite3.Connection, actor: User | None, *, include_inactive: bool = False) -> list[Project]:
    """Colaborador vê só os ativos (onde pode apontar); o responsável pode ver todos."""
    user = require_user(actor)
    only_active = not (include_inactive and user.is_admin)
    return projects_repo.list_all(conn, only_active=only_active)


def get_project(conn: sqlite3.Connection, actor: User | None, project_id: int) -> Project:
    require_admin(actor)
    return _get(conn, project_id)


def create_project(
    conn: sqlite3.Connection,
    actor: User | None,
    *,
    code: str,
    name: str,
    description: str = "",
    rd_eligible: bool = True,
    now: datetime | None = None,
) -> Project:
    admin = require_admin(actor)
    code, name, description = _clean(code, name, description)
    with transaction(conn):
        if projects_repo.code_taken(conn, code):
            raise ValidationError(f"Já existe um projeto com o código '{code}'.")
        project_id = projects_repo.insert(
            conn, code=code, name=name, description=description, rd_eligible=rd_eligible, now=now or utcnow()
        )
        project = projects_repo.get(conn, project_id)
        audit.record(conn, admin, "create", "project", project_id, _snapshot(project), now=now)
    return project


def update_project(
    conn: sqlite3.Connection,
    actor: User | None,
    project_id: int,
    *,
    code: str,
    name: str,
    description: str,
    active: bool,
    rd_eligible: bool = True,
    now: datetime | None = None,
) -> Project:
    admin = require_admin(actor)
    code, name, description = _clean(code, name, description)
    with transaction(conn):
        before = _get(conn, project_id)
        if projects_repo.code_taken(conn, code, exclude_id=project_id):
            raise ValidationError(f"Já existe um projeto com o código '{code}'.")
        projects_repo.update(
            conn, project_id, code=code, name=name, description=description, active=active, rd_eligible=rd_eligible
        )
        after = projects_repo.get(conn, project_id)
        diff = changes(_snapshot(before), _snapshot(after))
        if diff:
            audit.record(conn, admin, "update", "project", project_id, diff, now=now)
    return after


def delete_project(
    conn: sqlite3.Connection, actor: User | None, project_id: int, *, now: datetime | None = None
) -> None:
    admin = require_admin(actor)
    with transaction(conn):
        project = _get(conn, project_id)
        if time_entries_repo.count_by(conn, "project_id", project_id):
            raise ValidationError("Este projeto tem horas apontadas: desative-o em vez de excluir.")
        projects_repo.delete(conn, project_id)
        audit.record(conn, admin, "delete", "project", project_id, _snapshot(project), now=now)
