"""Início: atalhos para apontar; o responsável também vê os cadastros."""

from apontarhoras.services import users_service
from apontarhoras.web.components import e, page, single_admin_notice
from apontarhoras.web.http import Response
from apontarhoras.web.routing import Access, Ctx, Route


def home(ctx: Ctx) -> Response:
    user = ctx.user
    cards = (
        '<a class="card" href="/apontamentos/novo"><strong>Apontar horas</strong>Data, projeto, tarefa, início e '
        "término.</a>"
        '<a class="card" href="/apontamentos"><strong>Meus apontamentos</strong>O mês dia a dia, com as pendências '
        "contra a jornada.</a>"
    )
    if user.is_admin:
        cards += (
            '<a class="card" href="/usuarios"><strong>Colaboradores</strong>Quem aponta horas e quem administra.</a>'
            '<a class="card" href="/projetos"><strong>Projetos</strong>Projetos de P&amp;D onde as horas são '
            "apontadas.</a>"
            '<a class="card" href="/tarefas"><strong>Tarefas</strong>Tipos de atividade e quais contam para a Lei do '
            "Bem.</a>"
            '<a class="card" href="/relatorio"><strong>Relatório</strong>Conferir o mês, pendências da equipe e '
            "exportar (Excel e PDF).</a>"
            '<a class="card" href="/feriados"><strong>Feriados</strong>Dias sem jornada (não viram pendência).</a>'
            '<a class="card" href="/auditoria"><strong>Auditoria</strong>Quem fez o quê e quando.</a>'
        )
    body = f"<p>Olá, {e(user.name.split()[0])}.</p>" + f'<div class="cards">{cards}</div>'
    if user.is_admin and users_service.has_single_admin(ctx.conn, user):
        body = single_admin_notice() + body
    return page(ctx, "Início", body)


ROUTES = [Route("GET", "/", home, Access.USER)]
