"""Importar projetos colando a lista (só o responsável). Dois passos sem JavaScript: pré-visualizar → importar.

O texto colado vai num campo oculto do segundo formulário e é conferido de novo no servidor ao importar.
"""

from apontarhoras.domain.errors import AppError
from apontarhoras.domain.project_import import MAX_LINES, ImportPreview, ImportStatus
from apontarhoras.services import project_import_service
from apontarhoras.web.components import badge, checkbox_field, e, form, page
from apontarhoras.web.http import Response, redirect
from apontarhoras.web.routing import Access, Ctx, Route

LIST_HINT = (
    'Uma linha por projeto, como na planilha: "CÓDIGO - Cliente - Nome do projeto" ou "CÓDIGO - Nome". '
    f"Pode colar direto do Excel (colunas separadas por TAB). Até {MAX_LINES} linhas."
)
LIST_EXAMPLE = "PD-001 - Cliente Exemplo - Sensor novo\nPD-002 - Controlador de teste"
RD_HINT = "Desmarque se a lista for de projetos que não são P&D. Dá para mudar um a um depois, em Editar."
STATUS_BADGE = {ImportStatus.NEW: "ok", ImportStatus.EXISTS: "off", ImportStatus.INVALID: "warn"}


def _rd_eligible(ctx: Ctx) -> bool:
    return ctx.request.method != "POST" or ctx.form.get("lei_do_bem") == "1"


def _list_form(ctx: Ctx, text: str, submit: str) -> str:
    fields = (
        f'<label>Lista de projetos<textarea name="lista" rows="15" maxlength="100000" required '
        f'placeholder="{e(LIST_EXAMPLE)}">{e(text)}</textarea><small class="hint">{e(LIST_HINT)}</small></label>'
        + checkbox_field("lei_do_bem", "Estes projetos contam para a Lei do Bem", _rd_eligible(ctx), hint=RD_HINT)
    )
    return form(ctx, "/projetos/importar", fields, submit, cancel_href="/projetos")


def _form_page(ctx: Ctx, *, error: str | None = None) -> Response:
    return page(ctx, "Importar projetos", _list_form(ctx, ctx.form.get("lista", ""), "Pré-visualizar"), error=error)


def import_get(ctx: Ctx) -> Response:
    return _form_page(ctx)


def _preview_table(result: ImportPreview) -> str:
    rows = ""
    for line in result.lines:
        reason = f' <small class="muted">{e(line.reason)}</small>' if line.reason else ""
        code = e(line.code) if line.code else f'<span class="muted">{e(line.raw)}</span>'
        rows += (
            f"<tr><td>{line.number}</td><td><strong>{code}</strong></td><td>{e(line.name)}</td>"
            f"<td>{badge(line.status.label, STATUS_BADGE[line.status])}{reason}</td></tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr><th>Linha</th><th>Código</th><th>Nome</th><th>Situação</th>'
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def preview_post(ctx: Ctx) -> Response:
    text = ctx.form.get("lista", "")
    try:
        result = project_import_service.preview(ctx.conn, ctx.user, text)
    except AppError as exc:
        return _form_page(ctx, error=str(exc))
    if not result.lines:
        return _form_page(ctx, error="Cole pelo menos uma linha.")

    new_count = result.count(ImportStatus.NEW)
    rd_eligible = _rd_eligible(ctx)
    summary = (
        f'<p><strong>{new_count}</strong> nova(s) · {result.count(ImportStatus.EXISTS)} já existe(m) (ignorada(s)) · '
        f"{result.count(ImportStatus.INVALID)} inválida(s). "
        f"Contam para a Lei do Bem: <strong>{'Sim' if rd_eligible else 'Não'}</strong>.</p>"
    )
    if new_count:
        hidden = (
            f'<input type="hidden" name="lista" value="{e(text)}">'
            f'<input type="hidden" name="lei_do_bem" value="{"1" if rd_eligible else "0"}">'
            "<p>Confira a tabela abaixo. Só as linhas <strong>novas</strong> serão criadas.</p>"
        )
        confirm = form(ctx, "/projetos/importar/confirmar", hidden, f"Importar {new_count} projeto(s)",
                       cancel_href="/projetos")
    else:
        confirm = '<p class="muted">Nenhum projeto novo para importar. Corrija a lista abaixo, se precisar.</p>'
    body = (
        summary + confirm + _preview_table(result)
        + "<h2>Corrigir a lista</h2>" + _list_form(ctx, text, "Pré-visualizar de novo")
    )
    return page(ctx, "Importar projetos: conferir", body)


def confirm_post(ctx: Ctx) -> Response:
    try:
        project_import_service.import_projects(
            ctx.conn, ctx.user, ctx.form.get("lista", ""), rd_eligible=ctx.form.get("lei_do_bem") == "1"
        )
    except AppError as exc:
        return _form_page(ctx, error=str(exc))
    return redirect("/projetos?msg=importado")


ROUTES = [
    Route("GET", "/projetos/importar", import_get, Access.ADMIN),
    Route("POST", "/projetos/importar", preview_post, Access.ADMIN),
    Route("POST", "/projetos/importar/confirmar", confirm_post, Access.ADMIN),
]
