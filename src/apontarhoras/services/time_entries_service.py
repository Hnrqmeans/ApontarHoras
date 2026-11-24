"""Apontamento de horas: o colaborador aponta, corrige e exclui os próprios; o responsável pode corrigir qualquer um.

Regras (herdadas da planilha antiga): sem data futura, término > início, almoço perguntado quando o período passa
pelas 12:00–13:00, sem sobreposição no mesmo dia, descrição obrigatória quando a hora conta para a Lei do Bem.
"""

import calendar
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, tzinfo

from apontarhoras.domain.audit import changes
from apontarhoras.domain.duration import format_minutes
from apontarhoras.domain.errors import NotFound, PermissionDenied, ValidationError
from apontarhoras.domain.time_entry import (
    TimeEntry,
    compute_minutes,
    format_clock,
    is_late_entry,
    overlaps,
    parse_clock,
    parse_lunch,
    parse_work_date,
    validate_correction_reason,
    validate_description,
)
from apontarhoras.domain.user import User
from apontarhoras.domain.workday import DayStatus, day_status, expected_minutes
from apontarhoras.services import audit
from apontarhoras.services.common import require_user, utcnow
from apontarhoras.storage import projects_repo, tasks_repo, time_entries_repo
from apontarhoras.storage.db import transaction


def local_today() -> date:
    """Data no fuso do servidor (o mesmo dos colaboradores)."""
    return datetime.now().date()


@dataclass(frozen=True)
class DaySummary:
    day: date
    entries: list[TimeEntry]
    worked: int
    expected: int
    status: DayStatus


@dataclass(frozen=True)
class MonthSummary:
    year: int
    month: int
    days: list[DaySummary] = field(default_factory=list)
    total: int = 0
    rd_total: int = 0  # minutos que contam para a Lei do Bem
    entry_count: int = 0
    missing_days: int = 0
    excess_days: int = 0

    @property
    def other_total(self) -> int:
        return self.total - self.rd_total


# ---- consultas -----------------------------------------------------------------------------------------------


def _get_allowed(conn: sqlite3.Connection, actor: User | None, entry_id: int) -> tuple[User, TimeEntry]:
    user = require_user(actor)
    entry = time_entries_repo.get(conn, entry_id)
    if entry is None:
        raise NotFound("Apontamento não encontrado.")
    if entry.user_id != user.id and not user.is_admin:
        raise PermissionDenied("Você só pode ver e alterar os seus apontamentos.")
    return user, entry


def entered_late(entry: TimeEntry, *, tz: tzinfo | None = None) -> bool:
    """Lançado depois do fim do mês trabalhado (data local de `created_at`; `tz` = fuso do servidor)."""
    return is_late_entry(entry.work_date, entry.created_at.astimezone(tz).date())


def _reason_for(user: User, entry: TimeEntry, reason: str) -> dict:
    """Quem mexe no apontamento de outra pessoa (o responsável) precisa dizer o motivo; o dono, não."""
    if user.id == entry.user_id:
        return {}
    return {"motivo": validate_correction_reason(reason)}


def get_entry(conn: sqlite3.Connection, actor: User | None, entry_id: int) -> TimeEntry:
    return _get_allowed(conn, actor, entry_id)[1]


def month_summary(
    conn: sqlite3.Connection, actor: User | None, year: int, month: int, *, today: date | None = None
) -> MonthSummary:
    """Os apontamentos do próprio usuário no mês, dia a dia, com a conferência contra a jornada.

    Mostra todo dia útil até hoje (dia sem apontamento = pendência) e os fins de semana que tiverem horas.
    """
    user = require_user(actor)
    today = today or local_today()
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    entries = time_entries_repo.list_for_user(conn, user.id, first_day, last_day)
    by_day: dict[date, list[TimeEntry]] = {}
    for entry in entries:
        by_day.setdefault(entry.work_date, []).append(entry)

    days: list[DaySummary] = []
    for number in range(1, last_day.day + 1):
        day = date(year, month, number)
        if day > today:
            break
        day_entries = by_day.get(day, [])
        expected = expected_minutes(day)
        if expected == 0 and not day_entries:
            continue
        worked = sum(entry.minutes for entry in day_entries)
        days.append(DaySummary(day, day_entries, worked, expected, day_status(worked, expected)))

    return MonthSummary(
        year=year,
        month=month,
        days=days,
        total=sum(entry.minutes for entry in entries),
        rd_total=sum(entry.minutes for entry in entries if entry.rd_eligible),
        entry_count=len(entries),
        missing_days=sum(1 for d in days if d.status is DayStatus.MISSING),
        excess_days=sum(1 for d in days if d.status is DayStatus.EXCESS),
    )


# ---- gravação ------------------------------------------------------------------------------------------------


def _snapshot(entry: TimeEntry) -> dict:
    return {
        "colaborador": entry.user_name,
        "data": entry.work_date.isoformat(),
        "projeto": entry.project_code,
        "tarefa": entry.task_name,
        "início": format_clock(entry.start_minute),
        "término": format_clock(entry.end_minute),
        "intervalo": format_minutes(entry.break_minutes),
        "horas": format_minutes(entry.minutes),
        "lei do bem": entry.rd_eligible,
        "descrição": entry.description,
    }


def _parse_id(value: str | int, message: str) -> int:
    text = str(value).strip()
    if not text.isdigit():
        raise ValidationError(message)
    return int(text)


def _validate(
    conn: sqlite3.Connection,
    owner_id: int,
    *,
    work_date: str,
    project_id: str | int,
    task_id: str | int,
    start: str,
    end: str,
    lunch: str,
    description: str,
    today: date,
    current: TimeEntry | None,
) -> dict:
    """Confere tudo e devolve os campos prontos para o banco. Chamar dentro da transação."""
    day = parse_work_date(work_date, today)

    project = projects_repo.get(conn, _parse_id(project_id, "Selecione o projeto."))
    keeps_project = current is not None and project is not None and project.id == current.project_id
    if project is None or not (project.active or keeps_project):
        raise ValidationError("Selecione um projeto ativo.")

    task = tasks_repo.get(conn, _parse_id(task_id, "Selecione a tarefa."))
    keeps_task = current is not None and task is not None and task.id == current.task_id
    if task is None or not (task.active or keeps_task):
        raise ValidationError("Selecione uma tarefa ativa.")

    # Retrato da época: na correção, se projeto e tarefa não mudaram, mantém o que foi gravado.
    if keeps_project and keeps_task:
        rd_eligible = current.rd_eligible
    else:
        rd_eligible = project.rd_eligible and task.rd_eligible

    description = description.replace("\r", "").strip()
    validate_description(description, rd_eligible=rd_eligible)

    start_minute = parse_clock(start)
    end_minute = parse_clock(end)
    break_minutes, minutes = compute_minutes(start_minute, end_minute, parse_lunch(lunch))

    exclude_id = current.id if current else None
    for other in time_entries_repo.list_same_day(conn, owner_id, day, exclude_id=exclude_id):
        if overlaps(start_minute, end_minute, other.start_minute, other.end_minute):
            raise ValidationError(
                f"Já existe um apontamento neste dia entre {format_clock(other.start_minute)} e "
                f"{format_clock(other.end_minute)} ({other.project_code})."
            )

    return {
        "work_date": day,
        "project_id": project.id,
        "task_id": task.id,
        "start_minute": start_minute,
        "end_minute": end_minute,
        "break_minutes": break_minutes,
        "minutes": minutes,
        "rd_eligible": rd_eligible,
        "description": description,
    }


def create_entry(
    conn: sqlite3.Connection,
    actor: User | None,
    *,
    work_date: str,
    project_id: str | int,
    task_id: str | int,
    start: str,
    end: str,
    lunch: str = "",
    description: str = "",
    today: date | None = None,
    now: datetime | None = None,
) -> TimeEntry:
    """Sempre em nome do próprio usuário logado (não existe apontar por outra pessoa)."""
    user = require_user(actor)
    with transaction(conn):
        values = _validate(
            conn, user.id, work_date=work_date, project_id=project_id, task_id=task_id, start=start, end=end,
            lunch=lunch, description=description, today=today or local_today(), current=None,
        )
        entry_id = time_entries_repo.insert(conn, user_id=user.id, now=now or utcnow(), **values)
        entry = time_entries_repo.get(conn, entry_id)
        audit.record(conn, user, "create", "time_entry", entry_id, _snapshot(entry), now=now)
    return entry


def update_entry(
    conn: sqlite3.Connection,
    actor: User | None,
    entry_id: int,
    *,
    work_date: str,
    project_id: str | int,
    task_id: str | int,
    start: str,
    end: str,
    lunch: str = "",
    description: str = "",
    reason: str = "",
    today: date | None = None,
    now: datetime | None = None,
) -> TimeEntry:
    """`reason` é obrigatório (3–500 caracteres) quando quem corrige não é o dono do apontamento."""
    with transaction(conn):
        user, before = _get_allowed(conn, actor, entry_id)
        motive = _reason_for(user, before, reason)
        values = _validate(
            conn, before.user_id, work_date=work_date, project_id=project_id, task_id=task_id, start=start,
            end=end, lunch=lunch, description=description, today=today or local_today(), current=before,
        )
        time_entries_repo.update(conn, entry_id, now=now or utcnow(), **values)
        after = time_entries_repo.get(conn, entry_id)
        diff = changes(_snapshot(before), _snapshot(after))
        if diff:
            audit.record(conn, user, "update", "time_entry", entry_id,
                         {"colaborador": after.user_name, **diff, **motive}, now=now)
    return after


def delete_entry(
    conn: sqlite3.Connection, actor: User | None, entry_id: int, *, reason: str = "", now: datetime | None = None
) -> None:
    """`reason` é obrigatório (3–500 caracteres) quando quem exclui não é o dono do apontamento."""
    with transaction(conn):
        user, entry = _get_allowed(conn, actor, entry_id)
        motive = _reason_for(user, entry, reason)
        time_entries_repo.delete(conn, entry_id)
        audit.record(conn, user, "delete", "time_entry", entry_id, {**_snapshot(entry), **motive}, now=now)
