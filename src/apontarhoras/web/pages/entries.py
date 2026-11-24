"""Apontamentos do usuário logado: mês dia a dia (com lacunas), apontar, corrigir e excluir."""

from apontarhoras.domain.duration import format_minutes
from apontarhoras.domain.errors import AppError
from apontarhoras.domain.time_entry import (
    MAX_REASON,
    LunchChoice,
    TimeEntry,
    format_clock,
    parse_month,
    shift_month,
    spans_lunch,
)
from apontarhoras.domain.workday import DayStatus
from apontarhoras.services import projects_service, tasks_service, time_entries_service
from apontarhoras.services.time_entries_service import DaySummary, MonthSummary, local_today
from apontarhoras.web.components import (
    badge,
    date_field,
    e,
    fmt_datetime,
    form,
    page,
    select_field,
    text_field,
    textarea_field,
)
from apontarhoras.web.http import Response, redirect
from apontarhoras.web.routing import Access, Ctx, Route

MONTH_NAMES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
               "Novembro", "Dezembro")
WEEKDAYS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
STATUS_BADGE = {
    DayStatus.OK: "ok",
    DayStatus.MISSING: "warn",
    DayStatus.EXCESS: "attention",
    DayStatus.NOT_WORKDAY: "off",
}

CLOCK_HINT = "Ex.: 07:30, 7:30 ou 730."
LUNCH_HINT = "Obrigatório quando o período começa antes das 12:00 e termina depois das 13:00."
DESCRIPTION_HINT = "O que foi feito. Obrigatória quando a hora conta para a Lei do Bem (é a evidência)."
REASON_HINT = "Obrigatório ao alterar o apontamento de outra pessoa. Fica registrado na auditoria."


def _month_param(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


# ---- mês -----------------------------------------------------------------------------------------------------


def _stats(summary: MonthSummary) -> str:
    share = f" ({summary.rd_total * 100 // summary.total}%)" if summary.total else ""
    items = [
        ("Horas no mês", format_minutes(summary.total)),
        ("Lei do Bem", format_minutes(summary.rd_total) + share),
        ("Não elegíveis", format_minutes(summary.other_total)),
        ("Dias com pendência", str(summary.missing_days)),
        ("Dias a verificar", str(summary.excess_days)),
    ]
    return '<div class="stats">' + "".join(
        f'<div class="stat"><span>{e(label)}</span><strong>{e(value)}</strong></div>' for label, value in items
    ) + "</div>"


def _entry_row(entry: TimeEntry) -> str:
    rd = "Sim" if entry.rd_eligible else badge("Não", "off")
    lunch = f' <small class="muted">(−{format_minutes(entry.break_minutes)} almoço)</small>' if entry.break_minutes \
        else ""
    late = ""
    if time_entries_service.entered_late(entry):
        late = (f' <span title="Lançado em {e(fmt_datetime(entry.created_at))}">'
                f'{badge("Lançado depois do mês", "attention")}</span>')
    return (
        f"<tr><td></td><td>{format_clock(entry.start_minute)}–{format_clock(entry.end_minute)}{lunch}{late}</td>"
        f"<td><strong>{format_minutes(entry.minutes)}</strong></td>"
        f'<td title="{e(entry.project_name)}">{e(entry.project_code)}</td><td>{e(entry.task_name)}</td>'
        f'<td>{rd}</td><td class="desc">{e(entry.description)}</td>'
        f'<td class="actions-cell"><a href="/apontamentos/{entry.id}/editar">Editar</a>'
        f'<a href="/apontamentos/{entry.id}/excluir">Excluir</a></td></tr>'
    )


def _day_rows(day: DaySummary) -> str:
    label = f"{day.day.strftime('%d/%m')} {WEEKDAYS[day.day.weekday()]}"
    if day.holiday:
        situation = badge(f"Feriado: {day.holiday}", "off")
    elif day.status is DayStatus.NOT_WORKDAY:
        situation = badge("Fim de semana", "off")
    else:
        diff = day.worked - day.expected
        detail = "" if diff == 0 else f" ({'+' if diff > 0 else '−'}{format_minutes(abs(diff))})"
        situation = badge(day.status.label + detail, STATUS_BADGE[day.status])
    expected = f" de {format_minutes(day.expected)}" if day.expected else ""
    add = f'<a href="/apontamentos/novo?data={day.day.isoformat()}">Apontar</a>'
    header = (
        f'<tr class="day"><td><strong>{e(label)}</strong></td>'
        f'<td colspan="2">{format_minutes(day.worked)}{expected}</td><td colspan="4">{situation}</td>'
        f'<td class="actions-cell">{add}</td></tr>'
    )
    return header + "".join(_entry_row(entry) for entry in day.entries)


def month_page(ctx: Ctx) -> Response:
    today = local_today()
    year, month = parse_month(ctx.request.query.get("mes"), today)
    summary = time_entries_service.month_summary(ctx.conn, ctx.user, year, month, today=today)
    prev_y, prev_m = shift_month(year, month, -1)
    next_y, next_m = shift_month(year, month, 1)
    next_link = (
        f'<a href="/apontamentos?mes={_month_param(next_y, next_m)}">{MONTH_NAMES[next_m - 1]} ›</a>'
        if (next_y, next_m) <= (today.year, today.month) else "<span></span>"
    )
    nav = (
        f'<div class="month-nav"><a href="/apontamentos?mes={_month_param(prev_y, prev_m)}">'
        f"‹ {MONTH_NAMES[prev_m - 1]}</a><strong>{MONTH_NAMES[month - 1]} de {year}</strong>{next_link}</div>"
    )
    rows = "".join(_day_rows(day) for day in reversed(summary.days))
    if not rows:
        rows = '<tr><td colspan="8" class="muted">Nenhum dia para mostrar neste mês.</td></tr>'
    body = (
        '<div class="toolbar">'
        f"{nav}"
        '<a class="button primary" href="/apontamentos/novo">Novo apontamento</a></div>'
        + _stats(summary)
        + '<p class="muted">Jornada esperada: seg–qui 8:27, sex 7:42. <strong>Pendência</strong> = apontou menos; '
        "<strong>Verificar</strong> = apontou mais (hora extra ou erro). Feriado não tem jornada.</p>"
        '<div class="table-wrap"><table class="entries"><thead><tr><th>Dia</th><th>Horário</th><th>Horas</th>'
        "<th>Projeto</th><th>Tarefa</th><th>Lei do Bem</th><th>Descrição</th><th></th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )
    return page(ctx, "Meus apontamentos", body)


# ---- formulário ----------------------------------------------------------------------------------------------


def _fields(ctx: Ctx, entry: TimeEntry | None) -> str:
    f = ctx.form
    today = local_today()
    default_date = ctx.request.query.get("data", today.isoformat())
    projects = projects_service.list_projects(ctx.conn, ctx.user)
    project_options = [(str(p.id), f"{p.code} — {p.name}") for p in projects]
    tasks = tasks_service.list_tasks(ctx.conn, ctx.user)
    task_options = [(str(t.id), f"{t.name}{' (Lei do Bem)' if t.rd_eligible else ''}") for t in tasks]
    if entry:
        # projeto/tarefa desativados depois continuam aparecendo na correção do apontamento antigo
        if all(value != str(entry.project_id) for value, _ in project_options):
            project_options.append((str(entry.project_id), f"{entry.project_code} — {entry.project_name} (inativo)"))
        if all(value != str(entry.task_id) for value, _ in task_options):
            task_options.append((str(entry.task_id), f"{entry.task_name} (inativa)"))
    lunch_options = [(choice.value, choice.label) for choice in LunchChoice]
    current_lunch = ""
    if entry and entry.break_minutes:
        current_lunch = LunchChoice.DEDUCT.value
    elif entry and spans_lunch(entry.start_minute, entry.end_minute):
        current_lunch = LunchChoice.NO_BREAK.value
    return (
        date_field("data", "Data", f.get("data", entry.work_date.isoformat() if entry else default_date),
                   max_value=today.isoformat())
        + select_field("projeto", "Projeto", project_options, f.get("projeto", str(entry.project_id) if entry else ""),
                       placeholder="Selecione o projeto…")
        + select_field("tarefa", "Tarefa", task_options, f.get("tarefa", str(entry.task_id) if entry else ""),
                       placeholder="Selecione a tarefa…")
        + '<div class="row">'
        + text_field("inicio", "Início", f.get("inicio", format_clock(entry.start_minute) if entry else ""),
                     maxlength=5, hint=CLOCK_HINT, autofocus=entry is None)
        + text_field("termino", "Término", f.get("termino", format_clock(entry.end_minute) if entry else ""),
                     maxlength=5, hint=CLOCK_HINT)
        + "</div>"
        + select_field("almoco", "Almoço", lunch_options, f.get("almoco", current_lunch), hint=LUNCH_HINT)
        + textarea_field("descricao", "Descrição da atividade", f.get("descricao", entry.description if entry else ""),
                         maxlength=1000, hint=DESCRIPTION_HINT)
    )


def _values(ctx: Ctx) -> dict:
    f = ctx.form
    return {
        "work_date": f.get("data", ""),
        "project_id": f.get("projeto", ""),
        "task_id": f.get("tarefa", ""),
        "start": f.get("inicio", ""),
        "end": f.get("termino", ""),
        "lunch": f.get("almoco", ""),
        "description": f.get("descricao", ""),
    }


def _reason_field(ctx: Ctx, entry: TimeEntry) -> str:
    """Só aparece quando quem altera não é o dono (o responsável corrigindo outra pessoa)."""
    if entry.user_id == ctx.user.id:
        return ""
    return text_field("motivo", "Motivo da correção", ctx.form.get("motivo", ""), maxlength=MAX_REASON,
                      hint=REASON_HINT)


def _back(entry: TimeEntry) -> str:
    return f"/apontamentos?mes={_month_param(entry.work_date.year, entry.work_date.month)}"


def _new_page(ctx: Ctx, *, error: str | None = None) -> Response:
    return page(ctx, "Novo apontamento",
                form(ctx, "/apontamentos/novo", _fields(ctx, None), "Salvar", cancel_href="/apontamentos"),
                error=error)


def new_get(ctx: Ctx) -> Response:
    return _new_page(ctx)


def new_post(ctx: Ctx) -> Response:
    try:
        entry = time_entries_service.create_entry(ctx.conn, ctx.user, **_values(ctx))
    except AppError as exc:
        return _new_page(ctx, error=str(exc))
    return redirect(_back(entry) + "&msg=apontado")


def _edit_page(ctx: Ctx, entry: TimeEntry, *, error: str | None = None) -> Response:
    title = "Corrigir apontamento"
    if entry.user_id != ctx.user.id:
        title += f" de {entry.user_name}"
    action = f"/apontamentos/{entry.id}/editar"
    fields = _fields(ctx, entry) + _reason_field(ctx, entry)
    return page(ctx, title, form(ctx, action, fields, "Salvar", cancel_href=_back(entry)), error=error)


def edit_get(ctx: Ctx, entry_id: str) -> Response:
    return _edit_page(ctx, time_entries_service.get_entry(ctx.conn, ctx.user, int(entry_id)))


def edit_post(ctx: Ctx, entry_id: str) -> Response:
    try:
        entry = time_entries_service.update_entry(ctx.conn, ctx.user, int(entry_id), **_values(ctx),
                                                  reason=ctx.form.get("motivo", ""))
    except AppError as exc:
        return _edit_page(ctx, time_entries_service.get_entry(ctx.conn, ctx.user, int(entry_id)), error=str(exc))
    return redirect(_back(entry) + "&msg=salvo")


def _delete_page(ctx: Ctx, entry: TimeEntry, *, error: str | None = None) -> Response:
    fields = (
        f"<p>Excluir o apontamento de <strong>{entry.work_date.strftime('%d/%m/%Y')}</strong>, "
        f"{format_clock(entry.start_minute)}–{format_clock(entry.end_minute)} ({format_minutes(entry.minutes)}), "
        f"projeto <strong>{e(entry.project_code)}</strong>, tarefa {e(entry.task_name)}?</p>"
        '<p class="muted">A exclusão fica registrada na auditoria.</p>'
        + _reason_field(ctx, entry)
    )
    action = f"/apontamentos/{entry.id}/excluir"
    return page(ctx, "Excluir apontamento",
                form(ctx, action, fields, "Confirmar exclusão", cancel_href=_back(entry), danger=True), error=error)


def delete_get(ctx: Ctx, entry_id: str) -> Response:
    return _delete_page(ctx, time_entries_service.get_entry(ctx.conn, ctx.user, int(entry_id)))


def delete_post(ctx: Ctx, entry_id: str) -> Response:
    entry = time_entries_service.get_entry(ctx.conn, ctx.user, int(entry_id))
    try:
        time_entries_service.delete_entry(ctx.conn, ctx.user, entry.id, reason=ctx.form.get("motivo", ""))
    except AppError as exc:
        return _delete_page(ctx, entry, error=str(exc))
    return redirect(_back(entry) + "&msg=excluido")


ROUTES = [
    Route("GET", "/apontamentos", month_page, Access.USER),
    Route("GET", "/apontamentos/novo", new_get, Access.USER),
    Route("POST", "/apontamentos/novo", new_post, Access.USER),
    Route("GET", r"/apontamentos/(\d+)/editar", edit_get, Access.USER),
    Route("POST", r"/apontamentos/(\d+)/editar", edit_post, Access.USER),
    Route("GET", r"/apontamentos/(\d+)/excluir", delete_get, Access.USER),
    Route("POST", r"/apontamentos/(\d+)/excluir", delete_post, Access.USER),
]
