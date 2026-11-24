"""Apontamento, tarefas e bloqueios de exclusão (services: regras + permissão + auditoria). Dados fictícios."""

from datetime import date

import pytest

from apontarhoras.domain.errors import NotFound, PermissionDenied, ValidationError
from apontarhoras.domain.workday import DayStatus
from apontarhoras.services import audit, projects_service, tasks_service, time_entries_service, users_service
from tests.conftest import TEMP_PASSWORD

TODAY = date(2026, 11, 24)  # terça


@pytest.fixture
def project(conn, admin):
    return projects_service.create_project(conn, admin, code="PD-01", name="Sensor novo")


@pytest.fixture
def internal(conn, admin):
    return projects_service.create_project(conn, admin, code="INTERNO", name="Tarefas internas", rd_eligible=False)


def _task(conn, actor, name):
    return next(t for t in tasks_service.list_tasks(conn, actor) if t.name == name)


def _entry(conn, user, project, task, **overrides):
    values = {"work_date": "2026-11-24", "project_id": project.id, "task_id": task.id, "start": "8",
              "end": "12", "description": "Ajuste do controle", "today": TODAY}
    values.update(overrides)
    return time_entries_service.create_entry(conn, user, **values)


# ---- tarefas -------------------------------------------------------------------------------------------------


def test_default_tasks_from_spreadsheet(conn, collaborator):
    tasks = {t.name: t.rd_eligible for t in tasks_service.list_tasks(conn, collaborator)}
    assert tasks["Desenvolvimento"] is True
    assert tasks["Reuniões Externas"] is True
    assert tasks["Suporte"] is False
    assert len(tasks) == 9


def test_tasks_crud_and_permissions(conn, admin, collaborator):
    task = tasks_service.create_task(conn, admin, name="  Prototipagem  ", rd_eligible=True)
    assert task.name == "Prototipagem"
    with pytest.raises(ValidationError, match="Já existe"):
        tasks_service.create_task(conn, admin, name="prototipagem", rd_eligible=False)
    with pytest.raises(PermissionDenied):
        tasks_service.create_task(conn, collaborator, name="Outra", rd_eligible=True)
    tasks_service.update_task(conn, admin, task.id, name="Prototipagem", rd_eligible=True, active=False)
    assert "Prototipagem" not in [t.name for t in tasks_service.list_tasks(conn, collaborator)]
    assert "Prototipagem" not in [t.name for t in tasks_service.list_tasks(conn, collaborator, include_inactive=True)]
    tasks_service.delete_task(conn, admin, task.id)
    with pytest.raises(NotFound):
        tasks_service.get_task(conn, admin, task.id)


# ---- apontamento ---------------------------------------------------------------------------------------------


def test_create_entry_with_lunch(conn, collaborator, project):
    task = _task(conn, collaborator, "Desenvolvimento")
    entry = _entry(conn, collaborator, project, task, start="7", end="16:30", lunch="descontar")
    assert (entry.start_minute, entry.end_minute, entry.break_minutes, entry.minutes) == (420, 990, 60, 510)
    assert entry.rd_eligible
    assert entry.user_id == collaborator.id


def test_lunch_question_is_mandatory_when_spanning(conn, collaborator, project):
    task = _task(conn, collaborator, "Desenvolvimento")
    with pytest.raises(ValidationError, match="almoço"):
        _entry(conn, collaborator, project, task, start="7", end="16:30")
    entry = _entry(conn, collaborator, project, task, start="7", end="16:30", lunch="sem_intervalo")
    assert entry.minutes == 570


def test_eligibility_comes_from_task_and_project(conn, collaborator, project, internal):
    dev, support = _task(conn, collaborator, "Desenvolvimento"), _task(conn, collaborator, "Suporte")
    assert not _entry(conn, collaborator, project, support, start="8", end="9", description="").rd_eligible
    assert not _entry(conn, collaborator, internal, dev, start="9", end="10", description="").rd_eligible
    with pytest.raises(ValidationError, match="Lei do Bem"):
        _entry(conn, collaborator, project, dev, start="10", end="11", description="  ")


def test_eligibility_is_a_snapshot(conn, admin, collaborator, project):
    support = _task(conn, collaborator, "Suporte")
    entry = _entry(conn, collaborator, project, support, description="")
    tasks_service.update_task(conn, admin, support.id, name="Suporte", rd_eligible=True, active=True)
    # corrigir só o horário não muda o que foi gravado na época
    edited = time_entries_service.update_entry(
        conn, collaborator, entry.id, work_date="2026-11-24", project_id=project.id, task_id=support.id,
        start="8", end="11", description="", today=TODAY,
    )
    assert not edited.rd_eligible
    assert edited.minutes == 180


def test_no_overlap_no_future_no_inactive(conn, admin, collaborator, project):
    task = _task(conn, collaborator, "Desenvolvimento")
    _entry(conn, collaborator, project, task, start="8", end="12")
    with pytest.raises(ValidationError, match="Já existe um apontamento"):
        _entry(conn, collaborator, project, task, start="11", end="13")
    _entry(conn, collaborator, project, task, start="12", end="12:30")  # encostado pode
    with pytest.raises(ValidationError, match="futura"):
        _entry(conn, collaborator, project, task, work_date="2026-11-25")
    # outra pessoa no mesmo horário pode
    _entry(conn, admin, project, task, start="8", end="12")
    projects_service.update_project(conn, admin, project.id, code="PD-01", name="Sensor novo", description="",
                                    active=False)
    with pytest.raises(ValidationError, match="projeto ativo"):
        _entry(conn, collaborator, project, task, work_date="2026-11-23")
    with pytest.raises(ValidationError, match="Selecione o projeto"):
        _entry(conn, collaborator, project, task, project_id="")


def test_only_owner_or_admin_touches_entry(conn, admin, collaborator, project):
    other = users_service.create_user(conn, admin, name="Carla Colaboradora", login="carla", role="colaborador",
                                      temporary_password=TEMP_PASSWORD)
    task = _task(conn, collaborator, "Desenvolvimento")
    entry = _entry(conn, collaborator, project, task)
    with pytest.raises(PermissionDenied):
        time_entries_service.get_entry(conn, other, entry.id)
    with pytest.raises(PermissionDenied):
        time_entries_service.delete_entry(conn, other, entry.id)
    with pytest.raises(PermissionDenied):
        time_entries_service.update_entry(conn, other, entry.id, work_date="2026-11-24", project_id=project.id,
                                          task_id=task.id, start="8", end="9", description="x", today=TODAY)
    with pytest.raises(PermissionDenied):
        time_entries_service.create_entry(conn, None, work_date="2026-11-24", project_id=project.id,
                                          task_id=task.id, start="8", end="9", description="x", today=TODAY)
    # o responsável corrige o apontamento de outra pessoa; continua sendo da pessoa
    edited = time_entries_service.update_entry(conn, admin, entry.id, work_date="2026-11-24", project_id=project.id,
                                               task_id=task.id, start="8", end="9", description="x", today=TODAY)
    assert edited.user_id == collaborator.id
    time_entries_service.delete_entry(conn, collaborator, entry.id)
    with pytest.raises(NotFound):
        time_entries_service.get_entry(conn, collaborator, entry.id)


def test_entries_are_audited(conn, admin, collaborator, project):
    task = _task(conn, collaborator, "Desenvolvimento")
    entry = _entry(conn, collaborator, project, task)
    time_entries_service.update_entry(conn, collaborator, entry.id, work_date="2026-11-24", project_id=project.id,
                                      task_id=task.id, start="8", end="11", description="Ajuste do controle",
                                      today=TODAY)
    time_entries_service.delete_entry(conn, collaborator, entry.id)
    log = [(a.action, a.entity) for a in audit.list_recent(conn, admin)[:3]]
    assert log == [("delete", "time_entry"), ("update", "time_entry"), ("create", "time_entry")]
    update = audit.list_recent(conn, admin)[1]
    assert update.details["término"] == ["12:00", "11:00"]
    assert update.details["colaborador"] == "Bruno Colaborador"


def test_month_summary_with_gaps(conn, collaborator, project):
    dev, support = _task(conn, collaborator, "Desenvolvimento"), _task(conn, collaborator, "Suporte")
    _entry(conn, collaborator, project, dev, work_date="2026-11-23", start="7", end="16:27", lunch="descontar")
    _entry(conn, collaborator, project, support, work_date="2026-11-24", start="8", end="10", description="")
    _entry(conn, collaborator, project, dev, work_date="2026-11-22", start="9", end="10")  # domingo
    summary = time_entries_service.month_summary(conn, collaborator, 2026, 11, today=TODAY)
    days = {d.day: d for d in summary.days}
    assert days[date(2026, 11, 23)].status is DayStatus.OK  # 8h27
    assert days[date(2026, 11, 24)].status is DayStatus.MISSING
    assert days[date(2026, 11, 22)].status is DayStatus.NOT_WORKDAY
    assert date(2026, 11, 21) not in days  # sábado sem horas não aparece
    assert date(2026, 11, 25) not in days  # futuro não aparece
    assert days[date(2026, 11, 2)].worked == 0
    assert summary.total == 507 + 120 + 60
    assert summary.rd_total == 507 + 60
    assert summary.other_total == 120
    assert summary.entry_count == 3
    assert summary.missing_days == 16  # 17 dias úteis até 24/11, menos o dia 23 (OK); o 24 está incompleto


def test_cannot_delete_records_with_hours(conn, admin, collaborator, project):
    task = _task(conn, collaborator, "Desenvolvimento")
    _entry(conn, collaborator, project, task)
    with pytest.raises(ValidationError, match="desative"):
        projects_service.delete_project(conn, admin, project.id)
    with pytest.raises(ValidationError, match="desative"):
        tasks_service.delete_task(conn, admin, task.id)
    with pytest.raises(ValidationError, match="desative"):
        users_service.delete_user(conn, admin, collaborator.id)
