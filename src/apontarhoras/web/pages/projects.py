"""Projetos de P&D (só o responsável): listar, criar, editar/desativar, excluir."""

from apontarhoras.domain.errors import AppError
from apontarhoras.domain.project import Project
from apontarhoras.services import projects_service
from apontarhoras.web.components import badge, checkbox_field, e, form, page, text_field, textarea_field
from apontarhoras.web.http import Response, redirect
from apontarhoras.web.routing import Access, Ctx, Route

CODE_HINT = "Identificação curta, única. Ex.: PD-2026-01."
DESCRIPTION_HINT = "Opcional: objetivo do projeto (ajuda na documentação da Lei do Bem)."
RD_HINT = "Desmarque para projetos que não são P&D (ex.: tarefas internas): nenhuma hora dele conta."


def list_page(ctx: Ctx) -> Response:
    projects = projects_service.list_projects(ctx.conn, ctx.user, include_inactive=True)
    rows = "".join(
        f"<tr><td><strong>{e(p.code)}</strong></td><td>{e(p.name)}</td>"
        f"<td>{'Sim' if p.rd_eligible else badge('Não', 'off')}</td>"
        f"<td>{badge('Ativo') if p.active else badge('Inativo', 'off')}</td>"
        f'<td class="actions-cell"><a href="/projetos/{p.id}/editar">Editar</a>'
        f'<a href="/projetos/{p.id}/excluir">Excluir</a></td></tr>'
        for p in projects
    )
    if not rows:
        rows = '<tr><td colspan="5" class="muted">Nenhum projeto cadastrado.</td></tr>'
    body = (
        '<div class="toolbar"><span class="muted">Só projetos ativos aparecem para os colaboradores.</span>'
        '<a class="button primary" href="/projetos/novo">Novo projeto</a></div>'
        '<div class="table-wrap"><table><thead><tr><th>Código</th><th>Nome</th><th>Lei do Bem</th><th>Situação</th>'
        f"<th></th></tr></thead><tbody>{rows}</tbody></table></div>"
    )
    return page(ctx, "Projetos", body)


def _fields(ctx: Ctx, project: Project | None) -> str:
    f = ctx.form
    posted = ctx.request.method == "POST"
    fields = (
        text_field("codigo", "Código", f.get("codigo", project.code if project else ""), maxlength=20,
                   hint=CODE_HINT, autofocus=project is None)
        + text_field("nome", "Nome", f.get("nome", project.name if project else ""), maxlength=120)
        + textarea_field("descricao", "Descrição", f.get("descricao", project.description if project else ""),
                         hint=DESCRIPTION_HINT)
    )
    rd_eligible = f.get("lei_do_bem") == "1" if posted else (project.rd_eligible if project else True)
    fields += checkbox_field("lei_do_bem", "Conta para a Lei do Bem", rd_eligible, hint=RD_HINT)
    if project:
        active = f.get("ativo") == "1" if posted else project.active
        fields += checkbox_field("ativo", "Ativo", active, hint="Inativo some da lista dos colaboradores.")
    return fields


def _new_page(ctx: Ctx, *, error: str | None = None) -> Response:
    return page(ctx, "Novo projeto", form(ctx, "/projetos/novo", _fields(ctx, None), "Criar",
                                          cancel_href="/projetos"), error=error)


def new_get(ctx: Ctx) -> Response:
    return _new_page(ctx)


def new_post(ctx: Ctx) -> Response:
    f = ctx.form
    try:
        projects_service.create_project(
            ctx.conn, ctx.user, code=f.get("codigo", ""), name=f.get("nome", ""), description=f.get("descricao", ""),
            rd_eligible=f.get("lei_do_bem") == "1",
        )
    except AppError as exc:
        return _new_page(ctx, error=str(exc))
    return redirect("/projetos?msg=criado")


def _edit_page(ctx: Ctx, project: Project, *, error: str | None = None) -> Response:
    action = f"/projetos/{project.id}/editar"
    return page(ctx, f"Editar: {project.code}",
                form(ctx, action, _fields(ctx, project), "Salvar", cancel_href="/projetos"), error=error)


def edit_get(ctx: Ctx, project_id: str) -> Response:
    return _edit_page(ctx, projects_service.get_project(ctx.conn, ctx.user, int(project_id)))


def edit_post(ctx: Ctx, project_id: str) -> Response:
    f = ctx.form
    try:
        projects_service.update_project(
            ctx.conn, ctx.user, int(project_id), code=f.get("codigo", ""), name=f.get("nome", ""),
            description=f.get("descricao", ""), active=f.get("ativo") == "1", rd_eligible=f.get("lei_do_bem") == "1",
        )
    except AppError as exc:
        return _edit_page(ctx, projects_service.get_project(ctx.conn, ctx.user, int(project_id)), error=str(exc))
    return redirect("/projetos?msg=salvo")


def _delete_page(ctx: Ctx, project: Project, *, error: str | None = None) -> Response:
    fields = (
        f"<p>Excluir o projeto <strong>{e(project.code)}</strong> — {e(project.name)}? Esta ação não pode ser "
        "desfeita.</p>"
        '<p class="muted">Se o projeto só terminou, prefira <em>desativar</em> em Editar.</p>'
    )
    action = f"/projetos/{project.id}/excluir"
    return page(ctx, "Excluir projeto",
                form(ctx, action, fields, "Confirmar exclusão", cancel_href="/projetos", danger=True), error=error)


def delete_get(ctx: Ctx, project_id: str) -> Response:
    return _delete_page(ctx, projects_service.get_project(ctx.conn, ctx.user, int(project_id)))


def delete_post(ctx: Ctx, project_id: str) -> Response:
    try:
        projects_service.delete_project(ctx.conn, ctx.user, int(project_id))
    except AppError as exc:
        return _delete_page(ctx, projects_service.get_project(ctx.conn, ctx.user, int(project_id)), error=str(exc))
    return redirect("/projetos?msg=excluido")


ROUTES = [
    Route("GET", "/projetos", list_page, Access.ADMIN),
    Route("GET", "/projetos/novo", new_get, Access.ADMIN),
    Route("POST", "/projetos/novo", new_post, Access.ADMIN),
    Route("GET", r"/projetos/(\d+)/editar", edit_get, Access.ADMIN),
    Route("POST", r"/projetos/(\d+)/editar", edit_post, Access.ADMIN),
    Route("GET", r"/projetos/(\d+)/excluir", delete_get, Access.ADMIN),
    Route("POST", r"/projetos/(\d+)/excluir", delete_post, Access.ADMIN),
]
