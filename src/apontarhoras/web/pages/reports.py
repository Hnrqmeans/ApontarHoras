"""Relatório do responsável: filtros, painel, conferência do mês, pendências da equipe e exportação.

Sem JavaScript e sem `style` inline (a CSP bloqueia): as barras do painel usam classes de largura em degraus
(`.w-0` … `.w-100` no style.css) e sempre mostram o número ao lado.
"""

from urllib.parse import urlencode

from apontarhoras.domain.duration import format_minutes
from apontarhoras.domain.errors import ValidationError
from apontarhoras.domain.report import (
    MonthReviewStatus,
    ReportFilters,
    bar_step,
    format_seal,
    month_bounds,
    parse_report_filters,
    share_percent,
)
from apontarhoras.domain.time_entry import format_clock, parse_month, shift_month
from apontarhoras.integrations.xlsx import MIME_TYPE
from apontarhoras.services import projects_service, reports_service, tasks_service, users_service
from apontarhoras.services.reports_service import COLUMNS, REPORT_TITLE, SEAL_EXPLANATION, Emission, Report
from apontarhoras.services.time_entries_service import local_today
from apontarhoras.web.components import (
    badge,
    date_field,
    e,
    fmt_datetime,
    form,
    page,
    select_field,
)
from apontarhoras.web.http import Response, html_response, redirect
from apontarhoras.web.routing import Access, Ctx, Route

CHANGED_LABEL = "Alterado após a conferência"


def _month_param(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _link(path: str, filters: ReportFilters) -> str:
    return f"{path}?{urlencode(filters.query())}"


# ---- peças ---------------------------------------------------------------------------------------------------


def _filters_form(ctx: Ctx, filters: ReportFilters) -> str:
    users = [(str(u.id), u.name + ("" if u.active else " (inativo)")) for u in users_service.list_users(ctx.conn,
                                                                                                         ctx.user)]
    projects = [(str(p.id), f"{p.code} — {p.name}") for p in
                projects_service.list_projects(ctx.conn, ctx.user, include_inactive=True)]
    tasks = [(str(t.id), t.name) for t in tasks_service.list_tasks(ctx.conn, ctx.user, include_inactive=True)]
    kinds = [("lei", "Lei do Bem"), ("nao", "Não elegível")]
    query = filters.query()
    return (
        '<form method="get" action="/relatorio" class="card filters">'
        + date_field("inicio", "Data inicial", query["inicio"])
        + date_field("fim", "Data final", query["fim"])
        + select_field("colaborador", "Colaborador", [("", "Todos"), *users], query["colaborador"])
        + select_field("projeto", "Projeto", [("", "Todos"), *projects], query["projeto"])
        + select_field("tipo", "Tipo", [("", "Todos"), *kinds], query["tipo"])
        + select_field("tarefa", "Tarefa", [("", "Todas"), *tasks], query["tarefa"])
        + '<div class="actions"><button type="submit" class="button primary">Filtrar</button>'
        '<a class="button secondary" href="/relatorio">Mês atual</a></div></form>'
    )


def _stats(report: Report) -> str:
    items = [
        ("Apontamentos", str(len(report.entries))),
        ("Total de horas", format_minutes(report.total)),
        ("Lei do Bem", f"{format_minutes(report.rd_total)} ({report.rd_percent}%)"),
        ("Não elegíveis", format_minutes(report.other_total)),
        ("Projetos com horas", str(report.project_count)),
    ]
    return '<div class="stats">' + "".join(
        f'<div class="stat"><span>{e(label)}</span><strong>{e(value)}</strong></div>' for label, value in items
    ) + "</div>"


def _bars(title: str, items: list[tuple[str, int]], total: int) -> str:
    if not items:
        return ""
    maximum = items[0][1]
    rows = "".join(
        f'<div class="bar-label" title="{e(label)}">{e(label)}</div>'
        f'<div class="bar-track"><span class="bar w-{bar_step(minutes, maximum)}"></span></div>'
        f'<div class="bar-value">{format_minutes(minutes)} <small class="muted">'
        f"({share_percent(minutes, total)}%)</small></div>"
        for label, minutes in items
    )
    return f'<section class="card chart"><h2>{e(title)}</h2><div class="bars">{rows}</div></section>'


def _panel(report: Report) -> str:
    charts = (
        _bars("Horas por projeto", report.by_project, report.total)
        + _bars("Horas por tarefa", report.by_task, report.total)
        + _bars("Horas por colaborador", report.by_user, report.total)
    )
    return f'<div class="charts">{charts}</div>' if charts else ""


def _month_notices(months: list[MonthReviewStatus]) -> str:
    parts = []
    for status in months:
        label = f"{status.month:02d}/{status.year}"
        text = reports_service.review_text(status)
        if status.changed:
            parts.append(f'<div class="notice error" role="alert"><strong>{label}:</strong> {e(text)}</div>')
        elif status.review is not None:
            parts.append(f'<div class="notice ok"><strong>{label}:</strong> {e(text)}</div>')
        else:
            parts.append(f'<p class="muted"><strong>{label}:</strong> {e(text)}</p>')
    return "".join(parts)


def _table(report: Report) -> str:
    rows = []
    for entry in report.entries:
        changed = (f' {badge(CHANGED_LABEL, "attention")}' if entry.id in report.changed_after_review else "")
        rd = "Sim" if entry.rd_eligible else badge("Não", "off")
        rows.append(
            f"<tr><td>{entry.work_date.strftime('%d/%m/%Y')}{changed}</td><td>{e(entry.user_name)}</td>"
            f'<td title="{e(entry.project_name)}">{e(entry.project_code)}</td><td>{e(entry.task_name)}</td>'
            f"<td>{format_clock(entry.start_minute)}</td><td>{format_clock(entry.end_minute)}</td>"
            f"<td><strong>{format_minutes(entry.minutes)}</strong></td><td>{rd}</td>"
            f'<td class="desc">{e(entry.description)}</td></tr>'
        )
    if not rows:
        rows.append(f'<tr><td colspan="{len(COLUMNS)}" class="muted">Nenhum apontamento com estes filtros.</td></tr>')
    head = "".join(f"<th>{e(column)}</th>" for column in COLUMNS)
    return (
        f'<div class="table-wrap"><table class="report"><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


# ---- relatório -----------------------------------------------------------------------------------------------


def report_page(ctx: Ctx) -> Response:
    today = local_today()
    try:
        filters = parse_report_filters(ctx.request.query, today)
        report = reports_service.build_report(ctx.conn, ctx.user, filters)
    except ValidationError as exc:
        defaults = parse_report_filters({}, today)
        return page(ctx, "Relatório", _filters_form(ctx, defaults), error=str(exc))
    month = _month_param(filters.start.year, filters.start.month)
    toolbar = (
        '<div class="toolbar"><div class="actions">'
        f'<a class="button primary" href="{e(_link("/relatorio/excel", filters))}">Exportar Excel</a>'
        f'<a class="button" href="{e(_link("/relatorio/imprimir", filters))}">Imprimir / PDF</a></div>'
        f'<a href="/relatorio/pendencias?mes={month}">Pendências da equipe e conferência do mês ›</a></div>'
    )
    body = (
        _filters_form(ctx, filters)
        + toolbar
        + _month_notices(report.months)
        + _stats(report)
        + _panel(report)
        + "<h2>Apontamentos</h2>"
        + _table(report)
    )
    return page(ctx, "Relatório", body)


def excel_export(ctx: Ctx) -> Response:
    try:
        filters = parse_report_filters(ctx.request.query, local_today())
        filename, content, _ = reports_service.export_xlsx(ctx.conn, ctx.user, filters)
    except ValidationError:
        return report_page(ctx)
    return Response(body=content, content_type=MIME_TYPE,
                    headers=[("Content-Disposition", f'attachment; filename="{filename}"')])


def _print_document(report: Report, emission: Emission) -> str:
    filters = "".join(f"<dt>{e(label)}</dt><dd>{e(value)}</dd>" for label, value in report.filter_labels)
    months = "".join(
        f"<li>{status.month:02d}/{status.year}: {e(reports_service.review_text(status))}</li>"
        for status in report.months
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(REPORT_TITLE)}</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body class="print-page">
<main>
<p class="no-print notice ok">Para gerar o PDF: <strong>Imprimir › Salvar como PDF</strong> (Ctrl+P).
<a href="{e(_link("/relatorio", report.filters))}">‹ Voltar ao relatório</a></p>
<h1>{e(REPORT_TITLE)}</h1>
<dl class="filters-summary">{filters}</dl>
{_stats(report)}
<ul class="review-list">{months}</ul>
{_table(report)}
<footer class="print-footer">
<p>Emitido em {e(fmt_datetime(emission.at))} por {e(emission.by)}.</p>
<p>Selo de conferência: <strong class="seal">{e(format_seal(report.seal))}</strong>
<small>(SHA-256: {e(report.seal)})</small></p>
<p class="muted">{e(SEAL_EXPLANATION)}</p>
</footer>
</main>
</body>
</html>"""


def print_page(ctx: Ctx) -> Response:
    try:
        filters = parse_report_filters(ctx.request.query, local_today())
        report, emission = reports_service.print_report(ctx.conn, ctx.user, filters)
    except ValidationError:
        return report_page(ctx)
    return html_response(_print_document(report, emission))


# ---- pendências da equipe e conferência do mês ---------------------------------------------------------------


def _pending_page(ctx: Ctx, year: int, month: int, *, error: str | None = None) -> Response:
    today = local_today()
    team = reports_service.team_pending(ctx.conn, ctx.user, year, month, today=today)
    first_day, last_day = month_bounds(year, month)
    prev_y, prev_m = shift_month(year, month, -1)
    next_y, next_m = shift_month(year, month, 1)
    next_link = (
        f'<a href="/relatorio/pendencias?mes={_month_param(next_y, next_m)}">{next_m:02d}/{next_y} ›</a>'
        if (next_y, next_m) <= (today.year, today.month) else "<span></span>"
    )
    nav = (
        f'<div class="month-nav"><a href="/relatorio/pendencias?mes={_month_param(prev_y, prev_m)}">'
        f"‹ {prev_m:02d}/{prev_y}</a><strong>{month:02d}/{year}</strong>{next_link}</div>"
    )
    rows = []
    for member in team.members:
        link = "/relatorio?" + urlencode({"inicio": first_day.isoformat(), "fim": last_day.isoformat(),
                                          "colaborador": member.user.id})
        missing = badge(str(member.missing_days), "warn") if member.missing_days else "0"
        excess = badge(str(member.excess_days), "attention") if member.excess_days else "0"
        rows.append(
            f"<tr><td>{e(member.user.name)}</td><td>{missing}</td><td>{excess}</td>"
            f"<td>{format_minutes(member.worked)}</td><td>{format_minutes(member.expected)}</td>"
            f"<td>{format_minutes(member.balance)}</td>"
            f'<td class="actions-cell"><a href="{e(link)}">Ver apontamentos</a></td></tr>'
        )
    if not rows:
        rows.append('<tr><td colspan="7" class="muted">Nenhum colaborador ativo.</td></tr>')
    status = team.status
    review_form = form(
        ctx, "/relatorio/conferir",
        f'<input type="hidden" name="mes" value="{_month_param(year, month)}">'
        f"<p>{e(reports_service.review_text(status))}</p>"
        '<p class="muted">Conferir não trava o mês: lançamentos e correções continuam permitidos e o que for '
        f"criado ou alterado depois aparece como “{CHANGED_LABEL}” no relatório. Pode conferir de novo (vale a "
        "última).</p>",
        "Marcar mês como conferido",
    )
    body = (
        f'<div class="toolbar">{nav}<a href="/relatorio?inicio={first_day.isoformat()}&amp;fim={last_day.isoformat()}">'
        "Relatório do mês ›</a></div>"
        + _month_notices([status])
        + "<h2>Pendências da equipe</h2>"
        '<p class="muted">Dias úteis até hoje contra a jornada (seg–qui 8:27, sex 7:42). <strong>Pendência</strong> = '
        "apontou menos; <strong>Verificar</strong> = apontou mais.</p>"
        '<div class="table-wrap"><table><thead><tr><th>Colaborador</th><th>Dias com pendência</th>'
        "<th>Dias a verificar</th><th>Apontadas</th><th>Esperadas</th><th>Saldo</th><th></th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        "<h2>Conferência do mês</h2>"
        + review_form
    )
    return page(ctx, f"Pendências e conferência — {month:02d}/{year}", body, error=error)


def pending_page(ctx: Ctx) -> Response:
    year, month = parse_month(ctx.request.query.get("mes"), local_today())
    return _pending_page(ctx, year, month)


def review_post(ctx: Ctx) -> Response:
    today = local_today()
    text = ctx.form.get("mes", "").strip()
    year, month = parse_month(text, today)
    try:
        if _month_param(year, month) != text:
            raise ValidationError("Mês inválido.")
        reports_service.review_month(ctx.conn, ctx.user, year, month, today=today)
    except ValidationError as exc:
        return _pending_page(ctx, year, month, error=str(exc))
    return redirect(f"/relatorio/pendencias?mes={_month_param(year, month)}&msg=conferido")


ROUTES = [
    Route("GET", "/relatorio", report_page, Access.ADMIN),
    Route("GET", "/relatorio/excel", excel_export, Access.ADMIN),
    Route("GET", "/relatorio/imprimir", print_page, Access.ADMIN),
    Route("GET", "/relatorio/pendencias", pending_page, Access.ADMIN),
    Route("POST", "/relatorio/conferir", review_post, Access.ADMIN),
]
