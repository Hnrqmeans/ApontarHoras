"""Relatório, painel, pendências da equipe, conferência do mês e exportação (Excel e impressão). Só o responsável.

D9: o mês não trava. A conferência registra quantos apontamentos, quantas horas e o selo (SHA-256) do mês naquele
momento; o que for criado/alterado depois aparece como "alterado após a conferência". Nada é bloqueado.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from apontarhoras.domain.duration import format_minutes
from apontarhoras.domain.errors import ValidationError
from apontarhoras.domain.report import (
    MonthReview,
    MonthReviewStatus,
    ReportFilters,
    changed_after_review,
    decimal_hours,
    export_seal,
    format_seal,
    group_minutes,
    month_bounds,
    month_seal,
    months_in,
    share_percent,
)
from apontarhoras.domain.time_entry import TimeEntry, format_clock
from apontarhoras.domain.user import User
from apontarhoras.domain.workday import DayStatus
from apontarhoras.integrations.xlsx import Sheet, build_xlsx
from apontarhoras.services import audit
from apontarhoras.services.common import require_admin, utcnow
from apontarhoras.services.time_entries_service import local_today, summarize_days
from apontarhoras.storage import projects_repo, reports_repo, tasks_repo, users_repo
from apontarhoras.storage.db import transaction

REPORT_TITLE = "RELATÓRIO DE APONTAMENTOS P&D"
SEAL_EXPLANATION = (
    "Selo de conferência: código (SHA-256) calculado sobre os filtros e todas as linhas deste relatório; "
    "se qualquer dado mudar, o selo muda — o mesmo selo aparece no Excel e na impressão dos mesmos dados."
)
COLUMNS = ("Data", "Colaborador", "Projeto", "Tarefa", "Início", "Término", "Horas", "Lei do Bem", "Descrição")


@dataclass(frozen=True)
class Report:
    filters: ReportFilters
    filter_labels: list[tuple[str, str]]
    entries: list[TimeEntry]
    by_project: list[tuple[str, int]]
    by_task: list[tuple[str, int]]
    by_user: list[tuple[str, int]]
    months: list[MonthReviewStatus]
    changed_after_review: frozenset[int]  # ids dos apontamentos criados/alterados depois da conferência do mês
    seal: str

    @property
    def total(self) -> int:
        return sum(entry.minutes for entry in self.entries)

    @property
    def rd_total(self) -> int:
        return sum(entry.minutes for entry in self.entries if entry.rd_eligible)

    @property
    def other_total(self) -> int:
        return self.total - self.rd_total

    @property
    def rd_percent(self) -> int:
        return share_percent(self.rd_total, self.total)

    @property
    def project_count(self) -> int:
        return len(self.by_project)


@dataclass(frozen=True)
class Emission:
    """Quem emitiu e quando (rodapé da impressão e aba "Resumo" do Excel)."""

    at: datetime
    by: str


@dataclass(frozen=True)
class MemberPending:
    user: User
    missing_days: int
    excess_days: int
    worked: int
    expected: int

    @property
    def balance(self) -> int:
        return self.worked - self.expected


@dataclass(frozen=True)
class TeamPending:
    year: int
    month: int
    members: list[MemberPending]
    status: MonthReviewStatus


# ---- consultas -----------------------------------------------------------------------------------------------


def _filter_labels(conn: sqlite3.Connection, filters: ReportFilters) -> list[tuple[str, str]]:
    user_label = project_label = task_label = None
    if filters.user_id is not None:
        user = users_repo.get(conn, filters.user_id)
        if user is None:
            raise ValidationError("Colaborador não encontrado.")
        user_label = user.name
    if filters.project_id is not None:
        project = projects_repo.get(conn, filters.project_id)
        if project is None:
            raise ValidationError("Projeto não encontrado.")
        project_label = f"{project.code} — {project.name}"
    if filters.task_id is not None:
        task = tasks_repo.get(conn, filters.task_id)
        if task is None:
            raise ValidationError("Tarefa não encontrada.")
        task_label = task.name
    period = f"{filters.start.strftime('%d/%m/%Y')} a {filters.end.strftime('%d/%m/%Y')}"
    return [
        ("Período", period),
        ("Colaborador", user_label or "Todos"),
        ("Projeto", project_label or "Todos"),
        ("Tarefa", task_label or "Todas"),
        ("Tipo", filters.kind.label),
    ]


def _month_status(conn: sqlite3.Connection, year: int, month: int) -> MonthReviewStatus:
    first_day, last_day = month_bounds(year, month)
    entries = reports_repo.list_entries(conn, first_day, last_day)
    return MonthReviewStatus(
        year=year,
        month=month,
        review=reports_repo.latest_review(conn, year, month),
        entry_count=len(entries),
        total_minutes=sum(entry.minutes for entry in entries),
        seal=month_seal(entries),
    )


def _build(conn: sqlite3.Connection, filters: ReportFilters) -> Report:
    labels = _filter_labels(conn, filters)
    entries = reports_repo.list_entries(
        conn, filters.start, filters.end, user_id=filters.user_id, project_id=filters.project_id,
        task_id=filters.task_id, rd_eligible=filters.rd_eligible,
    )
    months = [_month_status(conn, year, month) for year, month in months_in(filters.start, filters.end)]
    reviews = {(status.year, status.month): status.review for status in months}
    changed = frozenset(
        entry.id for entry in entries
        if changed_after_review(entry, reviews.get((entry.work_date.year, entry.work_date.month)))
    )
    return Report(
        filters=filters,
        filter_labels=labels,
        entries=entries,
        by_project=group_minutes(entries, lambda entry: entry.project_code),
        by_task=group_minutes(entries, lambda entry: entry.task_name),
        by_user=group_minutes(entries, lambda entry: entry.user_name),
        months=months,
        changed_after_review=changed,
        seal=export_seal(labels, entries),
    )


def build_report(conn: sqlite3.Connection, actor: User | None, filters: ReportFilters) -> Report:
    require_admin(actor)
    return _build(conn, filters)


def team_pending(
    conn: sqlite3.Connection, actor: User | None, year: int, month: int, *, today: date | None = None
) -> TeamPending:
    """Por colaborador ativo: dias com pendência, dias a verificar e horas apontadas × esperadas até hoje."""
    require_admin(actor)
    today = today or local_today()
    first_day, last_day = month_bounds(year, month)
    by_user: dict[int, list[TimeEntry]] = {}
    for entry in reports_repo.list_entries(conn, first_day, last_day):
        by_user.setdefault(entry.user_id, []).append(entry)
    members = []
    for user in users_repo.list_all(conn):
        if not user.active:
            continue
        days = summarize_days(by_user.get(user.id, []), year, month, today)
        members.append(MemberPending(
            user=user,
            missing_days=sum(1 for day in days if day.status is DayStatus.MISSING),
            excess_days=sum(1 for day in days if day.status is DayStatus.EXCESS),
            worked=sum(day.worked for day in days),
            expected=sum(day.expected for day in days),
        ))
    return TeamPending(year, month, members, _month_status(conn, year, month))


def month_status(conn: sqlite3.Connection, actor: User | None, year: int, month: int) -> MonthReviewStatus:
    require_admin(actor)
    return _month_status(conn, year, month)


# ---- conferência do mês --------------------------------------------------------------------------------------


def review_month(
    conn: sqlite3.Connection,
    actor: User | None,
    year: int,
    month: int,
    *,
    today: date | None = None,
    now: datetime | None = None,
) -> MonthReview:
    """Marca o mês como conferido (não trava nada). Pode repetir: vale a última conferência."""
    user = require_admin(actor)
    today = today or local_today()
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        raise ValidationError("Mês inválido.")
    if (year, month) > (today.year, today.month):
        raise ValidationError("Não é possível conferir um mês futuro.")
    now = now or utcnow()
    with transaction(conn):
        status = _month_status(conn, year, month)
        review_id = reports_repo.insert_review(
            conn, year=year, month=month, reviewer_id=user.id, reviewer_name=f"{user.name} ({user.login})", now=now,
            entry_count=status.entry_count, total_minutes=status.total_minutes, seal=status.seal,
        )
        audit.record(conn, user, "review", "month_review", review_id, {
            "mês": f"{month:02d}/{year}",
            "apontamentos": status.entry_count,
            "horas": format_minutes(status.total_minutes),
            "selo": status.seal,
        }, now=now)
        review = reports_repo.latest_review(conn, year, month)
    return review


# ---- exportação ----------------------------------------------------------------------------------------------


def _audit_export(conn: sqlite3.Connection, user: User, report: Report, fmt: str, now: datetime) -> None:
    details = {"formato": fmt, **dict(report.filter_labels), "apontamentos": len(report.entries),
               "horas": format_minutes(report.total), "selo": report.seal}
    with transaction(conn):
        audit.record(conn, user, "export", "report", None, details, now=now)


def _emission(user: User, now: datetime) -> Emission:
    return Emission(at=now, by=f"{user.name} ({user.login})")


def print_report(
    conn: sqlite3.Connection, actor: User | None, filters: ReportFilters, *, now: datetime | None = None
) -> tuple[Report, Emission]:
    """Relatório para imprimir/salvar como PDF. A emissão fica na auditoria."""
    user = require_admin(actor)
    now = now or utcnow()
    report = _build(conn, filters)
    _audit_export(conn, user, report, "Impressão/PDF", now)
    return report, _emission(user, now)


def _xlsx_sheets(report: Report, emission: Emission) -> list[Sheet]:
    rows: list[list] = [list(COLUMNS)]
    for entry in report.entries:
        rows.append([
            entry.work_date, entry.user_name, entry.project_code, entry.task_name, format_clock(entry.start_minute),
            format_clock(entry.end_minute), decimal_hours(entry.minutes), "Sim" if entry.rd_eligible else "Não",
            entry.description,
        ])
    summary: list[list] = [[REPORT_TITLE, None]]
    summary += [[label, value] for label, value in report.filter_labels]
    summary += [
        ["Apontamentos", len(report.entries)],
        ["Total de horas", decimal_hours(report.total)],
        ["Horas Lei do Bem", decimal_hours(report.rd_total)],
        ["% Lei do Bem", report.rd_percent],
        ["Horas não elegíveis", decimal_hours(report.other_total)],
        ["Emitido em", emission.at.astimezone().strftime("%d/%m/%Y %H:%M")],
        ["Emitido por", emission.by],
        ["Selo de conferência", format_seal(report.seal)],
        ["Selo completo (SHA-256)", report.seal],
        ["Sobre o selo", SEAL_EXPLANATION],
    ]
    for status in report.months:
        summary.append([f"Conferência {status.month:02d}/{status.year}", review_text(status)])
    return [
        Sheet("Apontamentos", rows, widths=(11, 24, 14, 20, 8, 8, 8, 11, 60)),
        Sheet("Resumo", summary, widths=(26, 90)),
    ]


def export_xlsx(
    conn: sqlite3.Connection, actor: User | None, filters: ReportFilters, *, now: datetime | None = None
) -> tuple[str, bytes, Report]:
    """Planilha .xlsx com as mesmas colunas e filtros do relatório; aba "Resumo" com totais e selo."""
    user = require_admin(actor)
    now = now or utcnow()
    report = _build(conn, filters)
    content = build_xlsx(_xlsx_sheets(report, _emission(user, now)))
    _audit_export(conn, user, report, "Excel", now)
    return filters.filename("xlsx"), content, report


def review_text(status: MonthReviewStatus) -> str:
    """Frase da situação da conferência do mês (tela, impressão e Excel)."""
    review = status.review
    if review is None:
        return "Mês ainda não conferido."
    text = (
        f"Conferido em {review.reviewed_at.astimezone().strftime('%d/%m/%Y %H:%M')} por {review.reviewer_name} "
        f"({review.entry_count} apontamentos, {format_minutes(review.total_minutes)})."
    )
    if status.changed:
        text += (
            f" Atenção: o mês mudou desde a conferência (agora {status.entry_count} apontamentos, "
            f"{format_minutes(status.total_minutes)})."
        )
    return text
