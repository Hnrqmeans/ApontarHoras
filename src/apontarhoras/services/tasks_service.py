"""Cadastro de tarefas (o responsável cadastra e define quais contam para a Lei do Bem; todos veem as ativas)."""

import sqlite3
from datetime import datetime

from apontarhoras.domain.audit import changes
from apontarhoras.domain.errors import NotFound, ValidationError
from apontarhoras.domain.project import normalize_text
from apontarhoras.domain.task import Task, validate_name
from apontarhoras.domain.user import User
from apontarhoras.services import audit
from apontarhoras.services.common import require_admin, require_user, utcnow
from apontarhoras.storage import tasks_repo, time_entries_repo
from apontarhoras.storage.db import transaction


def _snapshot(task: Task) -> dict:
    return {"nome": task.name, "lei do bem": task.rd_eligible, "ativa": task.active}


def _get(conn: sqlite3.Connection, task_id: int) -> Task:
    task = tasks_repo.get(conn, task_id)
    if task is None:
        raise NotFound("Tarefa não encontrada.")
    return task


def _clean(name: str) -> str:
    name = normalize_text(name)
    validate_name(name)
    return name


def list_tasks(conn: sqlite3.Connection, actor: User | None, *, include_inactive: bool = False) -> list[Task]:
    """Colaborador vê só as ativas (onde pode apontar); o responsável pode ver todas."""
    user = require_user(actor)
    return tasks_repo.list_all(conn, only_active=not (include_inactive and user.is_admin))


def get_task(conn: sqlite3.Connection, actor: User | None, task_id: int) -> Task:
    require_admin(actor)
    return _get(conn, task_id)


def create_task(
    conn: sqlite3.Connection, actor: User | None, *, name: str, rd_eligible: bool, now: datetime | None = None
) -> Task:
    admin = require_admin(actor)
    name = _clean(name)
    with transaction(conn):
        if tasks_repo.name_taken(conn, name):
            raise ValidationError(f"Já existe a tarefa '{name}'.")
        task_id = tasks_repo.insert(conn, name=name, rd_eligible=rd_eligible, now=now or utcnow())
        task = tasks_repo.get(conn, task_id)
        audit.record(conn, admin, "create", "task", task_id, _snapshot(task), now=now)
    return task


def update_task(
    conn: sqlite3.Connection,
    actor: User | None,
    task_id: int,
    *,
    name: str,
    rd_eligible: bool,
    active: bool,
    now: datetime | None = None,
) -> Task:
    """Mudar "Lei do Bem" vale só para os próximos apontamentos (os antigos guardam o valor da época)."""
    admin = require_admin(actor)
    name = _clean(name)
    with transaction(conn):
        before = _get(conn, task_id)
        if tasks_repo.name_taken(conn, name, exclude_id=task_id):
            raise ValidationError(f"Já existe a tarefa '{name}'.")
        tasks_repo.update(conn, task_id, name=name, rd_eligible=rd_eligible, active=active)
        after = tasks_repo.get(conn, task_id)
        diff = changes(_snapshot(before), _snapshot(after))
        if diff:
            audit.record(conn, admin, "update", "task", task_id, diff, now=now)
    return after


def delete_task(conn: sqlite3.Connection, actor: User | None, task_id: int, *, now: datetime | None = None) -> None:
    admin = require_admin(actor)
    with transaction(conn):
        task = _get(conn, task_id)
        if time_entries_repo.count_by(conn, "task_id", task_id):
            raise ValidationError("Esta tarefa tem horas apontadas: desative-a em vez de excluir.")
        tasks_repo.delete(conn, task_id)
        audit.record(conn, admin, "delete", "task", task_id, _snapshot(task), now=now)
