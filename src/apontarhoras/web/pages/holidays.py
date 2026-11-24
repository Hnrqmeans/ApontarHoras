"""Feriados (só o responsável): listar por ano, adicionar, adicionar os nacionais do ano, excluir."""

from apontarhoras.domain.errors import AppError, ValidationError
from apontarhoras.domain.holiday import MAX_YEAR, MIN_YEAR, Holiday
from apontarhoras.services import holidays_service
from apontarhoras.services.time_entries_service import local_today
from apontarhoras.web.components import date_field, e, form, page, text_field
from apontarhoras.web.http import Response, redirect
from apontarhoras.web.routing import Access, Ctx, Route

WEEKDAYS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
NATIONAL_NOTE = (
    "Nacionais: 01/01, Sexta-feira Santa, 21/04, 01/05, 07/09, 12/10, 02/11, 15/11, 20/11 e 25/12. Carnaval e "
    "Corpus Christi são ponto facultativo: adicione à mão se a empresa folgar (e também os feriados da cidade)."
)


def _year(ctx: Ctx, raw: str | None = None) -> int:
    text = (raw if raw is not None else ctx.request.query.get("ano", "")).strip()
    if text.isdigit() and MIN_YEAR <= int(text) <= MAX_YEAR:
        return int(text)
    return local_today().year


def _row(holiday: Holiday) -> str:
    return (
        f"<tr><td>{holiday.day.strftime('%d/%m/%Y')}</td><td>{WEEKDAYS[holiday.day.weekday()]}</td>"
        f"<td>{e(holiday.description)}</td>"
        f'<td class="actions-cell"><a href="/feriados/{holiday.id}/excluir">Excluir</a></td></tr>'
    )


def _list_page(ctx: Ctx, year: int, *, error: str | None = None) -> Response:
    holidays = holidays_service.list_year(ctx.conn, ctx.user, year)
    rows = "".join(_row(holiday) for holiday in holidays)
    if not rows:
        rows = '<tr><td colspan="4" class="muted">Nenhum feriado cadastrado neste ano.</td></tr>'
    prev_link = f'<a href="/feriados?ano={year - 1}">‹ {year - 1}</a>' if year > MIN_YEAR else "<span></span>"
    next_link = f'<a href="/feriados?ano={year + 1}">{year + 1} ›</a>' if year < MAX_YEAR else "<span></span>"
    f = ctx.form
    add_fields = (
        date_field("data", "Data", f.get("data", ""))
        + text_field("descricao", "Descrição", f.get("descricao", ""), maxlength=80, hint="Ex.: Aniversário da cidade.")
    )
    national = form(
        ctx, "/feriados/nacionais", f'<input type="hidden" name="ano" value="{year}">'
        f'<p class="muted">{e(NATIONAL_NOTE)}</p>', f"Adicionar feriados nacionais de {year}",
    )
    body = (
        f'<div class="toolbar"><div class="month-nav">{prev_link}<strong>{year}</strong>{next_link}</div></div>'
        '<p class="muted">Feriado não tem jornada esperada: o dia não aparece como pendência em '
        "\"Meus apontamentos\".</p>"
        '<div class="table-wrap"><table><thead><tr><th>Data</th><th>Dia</th><th>Descrição</th><th></th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
        "<h2>Adicionar feriado</h2>" + form(ctx, "/feriados/novo", add_fields, "Adicionar")
        + "<h2>Feriados nacionais</h2>" + national
    )
    return page(ctx, "Feriados", body, error=error)


def list_get(ctx: Ctx) -> Response:
    return _list_page(ctx, _year(ctx))


def new_post(ctx: Ctx) -> Response:
    f = ctx.form
    try:
        holiday = holidays_service.add_holiday(ctx.conn, ctx.user, day=f.get("data", ""),
                                               description=f.get("descricao", ""))
    except AppError as exc:
        return _list_page(ctx, _year(ctx, f.get("data", "")[:4]), error=str(exc))
    return redirect(f"/feriados?ano={holiday.day.year}&msg=criado")


def national_post(ctx: Ctx) -> Response:
    raw = ctx.form.get("ano", "").strip()
    try:
        if not raw.isdigit():
            raise ValidationError("Ano inválido.")
        added = holidays_service.add_national_holidays(ctx.conn, ctx.user, int(raw))
    except AppError as exc:
        return _list_page(ctx, _year(ctx, raw), error=str(exc))
    message = "feriados_adicionados" if added else "feriados_ja_existiam"
    return redirect(f"/feriados?ano={int(raw)}&msg={message}")


def _delete_page(ctx: Ctx, holiday: Holiday, *, error: str | None = None) -> Response:
    fields = (
        f"<p>Excluir o feriado de <strong>{holiday.day.strftime('%d/%m/%Y')}</strong> — {e(holiday.description)}? "
        "O dia volta a ter jornada esperada.</p>"
    )
    back = f"/feriados?ano={holiday.day.year}"
    return page(ctx, "Excluir feriado", form(ctx, f"/feriados/{holiday.id}/excluir", fields, "Confirmar exclusão",
                                             cancel_href=back, danger=True), error=error)


def delete_get(ctx: Ctx, holiday_id: str) -> Response:
    return _delete_page(ctx, holidays_service.get_holiday(ctx.conn, ctx.user, int(holiday_id)))


def delete_post(ctx: Ctx, holiday_id: str) -> Response:
    holiday = holidays_service.get_holiday(ctx.conn, ctx.user, int(holiday_id))
    try:
        holidays_service.delete_holiday(ctx.conn, ctx.user, holiday.id)
    except AppError as exc:
        return _delete_page(ctx, holiday, error=str(exc))
    return redirect(f"/feriados?ano={holiday.day.year}&msg=excluido")


ROUTES = [
    Route("GET", "/feriados", list_get, Access.ADMIN),
    Route("POST", "/feriados/novo", new_post, Access.ADMIN),
    Route("POST", "/feriados/nacionais", national_post, Access.ADMIN),
    Route("GET", r"/feriados/(\d+)/excluir", delete_get, Access.ADMIN),
    Route("POST", r"/feriados/(\d+)/excluir", delete_post, Access.ADMIN),
]
