"""Relatório, painel, pendências da equipe, conferência do mês e exportação (domain + services). Dados fictícios."""

import io
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from xml.etree import ElementTree

import pytest

from apontarhoras.domain.errors import PermissionDenied, ValidationError
from apontarhoras.domain.report import (
    MAX_PERIOD_DAYS,
    ReportFilters,
    ReportKind,
    bar_step,
    decimal_hours,
    format_seal,
    months_in,
    parse_report_filters,
    share_percent,
)
from apontarhoras.services import audit, projects_service, reports_service, tasks_service, time_entries_service
from apontarhoras.services.time_entries_service import summarize_days

TODAY = date(2026, 11, 24)  # terça
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NOVEMBER = ReportFilters(start=date(2026, 11, 1), end=date(2026, 11, 30))


def _at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 11, day, hour, 0, tzinfo=UTC)


@pytest.fixture
def setup(conn, admin, collaborator):
    project = projects_service.create_project(conn, admin, code="PD-01", name="Sensor novo")
    internal = projects_service.create_project(conn, admin, code="INTERNO", name="Interno", rd_eligible=False)
    tasks = {t.name: t for t in tasks_service.list_tasks(conn, admin)}
    return project, internal, tasks


def _entry(conn, user, project, task, work_date, start, end, *, description="Ensaio", lunch="", now=None):
    return time_entries_service.create_entry(
        conn, user, work_date=work_date, project_id=project.id, task_id=task.id, start=start, end=end,
        lunch=lunch, description=description, today=TODAY, now=now or _at(20),
    )


# ---- domain --------------------------------------------------------------------------------------------------


def test_parse_filters_defaults_and_limits():
    filters = parse_report_filters({}, TODAY)
    assert (filters.start, filters.end) == (date(2026, 11, 1), date(2026, 11, 30))
    assert filters.kind is ReportKind.ALL and filters.rd_eligible is None
    filters = parse_report_filters({"inicio": "2026-01-01", "fim": "2026-12-31", "colaborador": "3",
                                    "projeto": "", "tarefa": "7", "tipo": "lei"}, TODAY)
    assert (filters.user_id, filters.project_id, filters.task_id, filters.rd_eligible) == (3, None, 7, True)
    assert filters.filename("xlsx") == "apontamentos_2026-01-01_2026-12-31.xlsx"
    assert parse_report_filters(filters.query(), TODAY) == filters  # ida e volta pelos links
    with pytest.raises(ValidationError, match="posterior"):
        parse_report_filters({"inicio": "2026-11-10", "fim": "2026-11-09"}, TODAY)
    with pytest.raises(ValidationError, match=str(MAX_PERIOD_DAYS)):
        parse_report_filters({"inicio": "2025-01-01", "fim": "2026-01-02"}, TODAY)
    parse_report_filters({"inicio": "2024-01-01", "fim": "2024-12-31"}, TODAY)  # ano bissexto = 366 dias: pode
    for bad in ({"inicio": "ontem"}, {"colaborador": "1 OR 1=1"}, {"tipo": "x"}):
        with pytest.raises(ValidationError):
            parse_report_filters(bad, TODAY)


def test_report_math_helpers():
    assert share_percent(1, 3) == 33 and share_percent(5, 0) == 0
    assert decimal_hours(510) == Decimal("8.50") and decimal_hours(507) == Decimal("8.45")
    assert decimal_hours(1) == Decimal("0.02")  # arredonda meio para cima
    assert bar_step(0, 100) == 0 and bar_step(100, 100) == 100 and bar_step(50, 100) == 50
    assert bar_step(1, 1000) == 5  # valor positivo nunca some
    assert format_seal("0123456789abcdef" + "0" * 48) == "0123 4567 89ab cdef"
    assert months_in(date(2025, 12, 15), date(2026, 2, 1)) == [(2025, 12), (2026, 1), (2026, 2)]


def test_summarize_days_is_the_month_summary_rule(conn, setup, collaborator):
    project, _, tasks = setup
    _entry(conn, collaborator, project, tasks["Desenvolvimento"], "2026-11-23", "8", "12")
    entries = time_entries_service.month_summary(conn, collaborator, 2026, 11, today=TODAY)
    days = summarize_days(
        [e for d in entries.days for e in d.entries], 2026, 11, TODAY
    )
    assert days == entries.days


# ---- relatório -----------------------------------------------------------------------------------------------


def test_report_filters_totals_and_groups(conn, admin, collaborator, setup):
    project, internal, tasks = setup
    _entry(conn, collaborator, project, tasks["Desenvolvimento"], "2026-11-23", "8", "12")
    _entry(conn, collaborator, internal, tasks["Suporte"], "2026-11-23", "13", "15", description="")
    _entry(conn, admin, project, tasks["Testes e Validações"], "2026-11-24", "8", "9")
    _entry(conn, admin, project, tasks["Desenvolvimento"], "2026-10-30", "8", "9")  # fora do período

    report = reports_service.build_report(conn, admin, NOVEMBER)
    assert len(report.entries) == 3
    assert (report.total, report.rd_total, report.other_total, report.rd_percent) == (420, 300, 120, 71)
    assert report.by_project == [("PD-01", 300), ("INTERNO", 120)]
    assert report.project_count == 2
    assert report.by_user[0] == ("Bruno Colaborador", 360)
    assert ("Período", "01/11/2026 a 30/11/2026") in report.filter_labels

    only_rd = reports_service.build_report(conn, admin, ReportFilters(NOVEMBER.start, NOVEMBER.end,
                                                                     kind=ReportKind.OTHER))
    assert [e.project_code for e in only_rd.entries] == ["INTERNO"]
    one_user = reports_service.build_report(conn, admin, ReportFilters(NOVEMBER.start, NOVEMBER.end,
                                                                      user_id=admin.id, project_id=project.id))
    assert [e.user_id for e in one_user.entries] == [admin.id]
    assert ("Colaborador", "Ana Responsável") in one_user.filter_labels
    with pytest.raises(ValidationError, match="não encontrad"):
        reports_service.build_report(conn, admin, ReportFilters(NOVEMBER.start, NOVEMBER.end, project_id=999))


def test_only_admin_reaches_reports(conn, collaborator, setup):
    with pytest.raises(PermissionDenied):
        reports_service.build_report(conn, collaborator, NOVEMBER)
    with pytest.raises(PermissionDenied):
        reports_service.team_pending(conn, collaborator, 2026, 11, today=TODAY)
    with pytest.raises(PermissionDenied):
        reports_service.review_month(conn, collaborator, 2026, 11, today=TODAY)
    with pytest.raises(PermissionDenied):
        reports_service.export_xlsx(conn, collaborator, NOVEMBER)
    with pytest.raises(PermissionDenied):
        reports_service.print_report(conn, collaborator, NOVEMBER)
    with pytest.raises(PermissionDenied):
        reports_service.month_status(conn, collaborator, 2026, 11)
    with pytest.raises(PermissionDenied):
        reports_service.build_report(conn, None, NOVEMBER)


def test_team_pending_uses_workday_rule(conn, admin, collaborator, setup):
    project, _, tasks = setup
    # 23/11 (seg): jornada inteira 8:27; 24/11 (ter): só 1 h → pendência; demais dias úteis vazios → pendência
    _entry(conn, collaborator, project, tasks["Desenvolvimento"], "2026-11-23", "8", "1627", lunch="sem_intervalo")
    _entry(conn, collaborator, project, tasks["Desenvolvimento"], "2026-11-24", "8", "9")
    team = reports_service.team_pending(conn, admin, 2026, 11, today=TODAY)
    bruno = next(m for m in team.members if m.user.id == collaborator.id)
    workdays = 17  # dias úteis de 01 a 24/11/2026
    assert bruno.missing_days == workdays - 1
    assert bruno.excess_days == 0
    assert bruno.worked == 507 + 60
    assert bruno.expected == 14 * 507 + 3 * 462  # seg–qui 8:27, sex 7:42
    assert bruno.balance == bruno.worked - bruno.expected
    assert {m.user.id for m in team.members} == {admin.id, collaborator.id}


# ---- conferência do mês --------------------------------------------------------------------------------------


def test_month_review_flags_later_changes(conn, admin, collaborator, setup):
    project, _, tasks = setup
    dev = tasks["Desenvolvimento"]
    first = _entry(conn, collaborator, project, dev, "2026-11-23", "8", "12", now=_at(23))
    second = _entry(conn, collaborator, project, dev, "2026-11-24", "8", "10", now=_at(24, 9))

    review = reports_service.review_month(conn, admin, 2026, 11, today=TODAY, now=_at(24, 10))
    assert (review.entry_count, review.total_minutes, len(review.seal)) == (2, 360, 64)
    report = reports_service.build_report(conn, admin, NOVEMBER)
    assert report.changed_after_review == frozenset()
    assert not report.months[0].changed

    # correção depois da conferência: marcada, e o mês "mudou"; nada é bloqueado
    time_entries_service.update_entry(
        conn, collaborator, second.id, work_date="2026-11-24", project_id=project.id, task_id=dev.id, start="8",
        end="11", description="Ensaio", today=TODAY, now=_at(24, 11),
    )
    report = reports_service.build_report(conn, admin, NOVEMBER)
    assert report.changed_after_review == frozenset({second.id})
    assert report.months[0].changed
    assert "mudou desde a conferência" in reports_service.review_text(report.months[0])

    # conferir de novo: vale a última
    reports_service.review_month(conn, admin, 2026, 11, today=TODAY, now=_at(24, 12))
    report = reports_service.build_report(conn, admin, NOVEMBER)
    assert not report.months[0].changed and report.changed_after_review == frozenset()

    # exclusão depois da conferência também aparece (contagem/selo diferentes)
    time_entries_service.delete_entry(conn, admin, first.id, reason="Lançado em duplicidade", now=_at(24, 13))
    status = reports_service.month_status(conn, admin, 2026, 11)
    assert status.changed and status.entry_count == 1

    actions = [(a.action, a.entity) for a in audit.list_recent(conn, admin)]
    assert actions.count(("review", "month_review")) == 2


def test_review_month_validation(conn, admin):
    with pytest.raises(ValidationError, match="futuro"):
        reports_service.review_month(conn, admin, 2026, 12, today=TODAY)
    with pytest.raises(ValidationError):
        reports_service.review_month(conn, admin, 2026, 13, today=TODAY)
    review = reports_service.review_month(conn, admin, 2026, 11, today=TODAY)  # mês vazio também se confere
    assert review.entry_count == 0


def test_seal_ignores_renames_for_month_but_not_for_export(conn, admin, collaborator, setup):
    project, _, tasks = setup
    _entry(conn, collaborator, project, tasks["Desenvolvimento"], "2026-11-23", "8", "12")
    before_status = reports_service.month_status(conn, admin, 2026, 11)
    before_report = reports_service.build_report(conn, admin, NOVEMBER)
    projects_service.update_project(conn, admin, project.id, code="PD-02", name="Sensor novo", description="",
                                    active=True, rd_eligible=True)
    assert reports_service.month_status(conn, admin, 2026, 11).seal == before_status.seal
    assert reports_service.build_report(conn, admin, NOVEMBER).seal != before_report.seal


# ---- exportação ----------------------------------------------------------------------------------------------


def _sheet_values(content: bytes, number: int) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        root = ElementTree.fromstring(archive.read(f"xl/worksheets/sheet{number}.xml"))
    rows = []
    for row in root.findall(".//m:row", NS):
        values = []
        for cell in row.findall("m:c", NS):
            text = cell.find("m:is/m:t", NS)
            values.append(text.text if text is not None else cell.find("m:v", NS).text)
        rows.append(values)
    return rows


def test_export_xlsx_and_print_share_the_seal_and_are_audited(conn, admin, collaborator, setup):
    project, _, tasks = setup
    _entry(conn, collaborator, project, tasks["Desenvolvimento"], "2026-11-23", "8", "1630", lunch="sem_intervalo",
           description="=HYPERLINK(\"http://x\")")
    time_entries_service.create_entry(
        conn, collaborator, work_date="2026-11-23", project_id=project.id, task_id=tasks["Desenvolvimento"].id,
        start="7", end="7:30", description="Calibração <ok> & teste", today=TODAY,
    )
    filename, content, report = reports_service.export_xlsx(conn, admin, NOVEMBER)
    assert filename == "apontamentos_2026-11-01_2026-11-30.xlsx"
    rows = _sheet_values(content, 1)
    assert rows[0] == ["Data", "Colaborador", "Projeto", "Tarefa", "Início", "Término", "Horas", "Lei do Bem",
                       "Descrição"]
    assert rows[1][:8] == [str((date(2026, 11, 23) - date(1899, 12, 30)).days), "Bruno Colaborador", "PD-01",
                           "Desenvolvimento", "07:00", "07:30", "0.50", "Sim"]
    assert rows[1][8] == "Calibração <ok> & teste"
    assert rows[2][6] == "8.50" and rows[2][8] == "'=HYPERLINK(\"http://x\")"  # nunca vira fórmula
    summary = {row[0]: row[1] for row in _sheet_values(content, 2) if len(row) > 1}
    assert summary["Selo completo (SHA-256)"] == report.seal
    assert summary["Selo de conferência"] == format_seal(report.seal)

    printed, emission = reports_service.print_report(conn, admin, NOVEMBER)
    assert printed.seal == report.seal  # mesmo conteúdo → mesmo selo
    assert emission.by == "Ana Responsável (ana)"
    exports = [a for a in audit.list_recent(conn, admin) if a.action == "export"]
    assert len(exports) == 2 and exports[0].entity == "report"
    assert {e.details["formato"] for e in exports} == {"Excel", "Impressão/PDF"}
    assert all(e.details["selo"] == report.seal for e in exports)
