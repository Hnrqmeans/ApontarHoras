"""Auditoria (só o responsável): últimos registros."""

from typing import Any

from apontarhoras.services import audit
from apontarhoras.web.components import e, fmt_datetime, page
from apontarhoras.web.http import Response
from apontarhoras.web.routing import Access, Ctx, Route

LIMIT = 200


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "sim" if value else "não"
    if value in (None, ""):
        return "—"
    return str(value)


def _details(details: dict[str, Any]) -> str:
    parts = []
    for key, value in details.items():
        if isinstance(value, list) and len(value) == 2:
            parts.append(f"{key}: {_value(value[0])} → {_value(value[1])}")
        else:
            parts.append(f"{key}: {_value(value)}")
    return "<br>".join(e(part) for part in parts)


def audit_page(ctx: Ctx) -> Response:
    entries = audit.list_recent(ctx.conn, ctx.user, LIMIT)
    rows = "".join(
        f"<tr><td>{entry.id}</td><td>{e(fmt_datetime(entry.at))}</td><td>{e(entry.actor_name)}</td>"
        f"<td>{e(entry.action_label)}</td><td>{e(entry.entity_label)}</td><td>{_details(entry.details)}</td></tr>"
        for entry in entries
    )
    body = (
        '<div class="toolbar">'
        f'<span class="muted">Últimos {LIMIT} registros. A auditoria não pode ser editada nem apagada pelo app.</span>'
        '<a class="button" href="/auditoria/integridade">Verificar integridade</a></div>'
        '<div class="table-wrap"><table><thead><tr><th>#</th><th>Quando</th><th>Quem</th><th>Ação</th><th>Item</th>'
        f"<th>Detalhes</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )
    return page(ctx, "Auditoria", body)


def integrity_page(ctx: Ctx) -> Response:
    check = audit.verify_integrity(ctx.conn, ctx.user)
    if check.ok:
        result = (
            f'<div class="notice ok" role="status">Íntegro: {check.total} registros conferidos.</div>'
            + (f"<p>Último registro: <strong>#{check.last_id}</strong>, selo <code>{e(check.short_hash)}</code>.</p>"
               if check.last_id else "")
        )
    else:
        result = (
            f'<div class="notice error" role="alert">ALTERAÇÃO DETECTADA a partir do registro #{check.broken_id}. '
            "O arquivo do banco foi modificado fora do ApontarHoras (registro alterado, apagado ou inserido).</div>"
            "<p>Não apague nada: guarde uma cópia do arquivo do banco como está e avise a TI. Compare com o backup "
            "para ver o que mudou.</p>"
        )
    lookup = ""
    wanted = ctx.request.query.get("registro", "").strip().lstrip("#")
    if wanted.isascii() and wanted.isdigit() and len(wanted) <= 10:
        seal = audit.seal_of(ctx.conn, ctx.user, int(wanted))
        lookup = (f"<p>Registro <strong>#{int(wanted)}</strong>: selo <code>{e(seal[:16])}</code>.</p>" if seal
                  else f'<p class="notice error">Registro #{int(wanted)} não existe (ou está sem selo).</p>')
    body = (
        result
        + '<p class="muted">Cada registro da auditoria leva um selo calculado a partir do anterior, como uma corrente: '
        "alterar ou apagar um registro direto no arquivo do banco quebra a corrente daquele ponto em diante.</p>"
        '<p class="muted">Anote o número e o selo do último registro de tempos em tempos (por exemplo, ao conferir '
        "o mês) e guarde fora do servidor. Depois, confira aqui: se o registro anotado sumiu ou o selo dele mudou, "
        "os últimos registros foram apagados ou a corrente foi refeita por alguém com acesso ao arquivo.</p>"
        '<form method="get" action="/auditoria/integridade" class="card form">'
        '<label>Conferir o selo do registro nº<input type="text" name="registro" inputmode="numeric" maxlength="10" '
        f'value="{e(wanted)}"></label><div class="actions"><button type="submit" class="button">Conferir</button>'
        "</div></form>"
        + lookup
        + '<p><a href="/auditoria">Voltar à auditoria</a></p>'
    )
    return page(ctx, "Verificar integridade", body)


ROUTES = [
    Route("GET", "/auditoria", audit_page, Access.ADMIN),
    Route("GET", "/auditoria/integridade", integrity_page, Access.ADMIN),
]
