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
        f"<tr><td>{e(fmt_datetime(entry.at))}</td><td>{e(entry.actor_name)}</td><td>{e(entry.action_label)}</td>"
        f"<td>{e(entry.entity_label)}</td><td>{_details(entry.details)}</td></tr>"
        for entry in entries
    )
    body = (
        f'<p class="muted">Últimos {LIMIT} registros. A auditoria não pode ser editada nem apagada pelo app.</p>'
        '<div class="table-wrap"><table><thead><tr><th>Quando</th><th>Quem</th><th>Ação</th><th>Item</th>'
        f"<th>Detalhes</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )
    return page(ctx, "Auditoria", body)


ROUTES = [Route("GET", "/auditoria", audit_page, Access.ADMIN)]
