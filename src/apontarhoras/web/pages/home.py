"""Início: atalhos do responsável; para o colaborador, os projetos ativos."""

from apontarhoras.services import projects_service
from apontarhoras.web.components import e, page
from apontarhoras.web.http import Response
from apontarhoras.web.routing import Access, Ctx, Route


def home(ctx: Ctx) -> Response:
    user = ctx.user
    greeting = f"<p>Olá, {e(user.name.split()[0])}.</p>"
    if user.is_admin:
        body = greeting + (
            '<div class="cards">'
            '<a class="card" href="/usuarios"><strong>Colaboradores</strong>Quem aponta horas e quem administra.</a>'
            '<a class="card" href="/projetos"><strong>Projetos</strong>Projetos de P&amp;D onde as horas são '
            "apontadas.</a>"
            '<a class="card" href="/auditoria"><strong>Auditoria</strong>Quem fez o quê e quando.</a>'
            "</div>"
        )
    else:
        projects = projects_service.list_projects(ctx.conn, user)
        items = "".join(f"<li><strong>{e(p.code)}</strong> — {e(p.name)}</li>" for p in projects)
        listing = f"<ul>{items}</ul>" if items else '<p class="muted">Nenhum projeto ativo ainda.</p>'
        body = (
            greeting
            + '<p class="muted">O apontamento de horas chega na próxima versão.</p>'
            + "<h2>Projetos ativos</h2>"
            + listing
        )
    return page(ctx, "Início", body)


ROUTES = [Route("GET", "/", home, Access.USER)]
