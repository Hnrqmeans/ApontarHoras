"""Tarefas (só o responsável): listar, criar, editar/desativar, excluir. Define o que conta para a Lei do Bem."""

from apontarhoras.domain.errors import AppError
from apontarhoras.domain.task import Task
from apontarhoras.services import tasks_service
from apontarhoras.web.components import badge, checkbox_field, e, form, page, text_field
from apontarhoras.web.http import Response, redirect
from apontarhoras.web.routing import Access, Ctx, Route

RD_HINT = "Horas desta tarefa contam para a Lei do Bem (exigem descrição da atividade)."
RD_CHANGE_NOTE = "Mudar \"Lei do Bem\" vale para os próximos apontamentos; os já feitos guardam o valor da época."


def list_page(ctx: Ctx) -> Response:
    tasks = tasks_service.list_tasks(ctx.conn, ctx.user, include_inactive=True)
    rows = "".join(
        f"<tr><td>{e(t.name)}</td><td>{'Sim' if t.rd_eligible else badge('Não', 'off')}</td>"
        f"<td>{badge('Ativa') if t.active else badge('Inativa', 'off')}</td>"
        f'<td class="actions-cell"><a href="/tarefas/{t.id}/editar">Editar</a>'
        f'<a href="/tarefas/{t.id}/excluir">Excluir</a></td></tr>'
        for t in tasks
    )
    if not rows:
        rows = '<tr><td colspan="4" class="muted">Nenhuma tarefa cadastrada.</td></tr>'
    body = (
        '<div class="toolbar"><span class="muted">O tipo de atividade decide se a hora conta para a Lei do Bem.'
        '</span><a class="button primary" href="/tarefas/nova">Nova tarefa</a></div>'
        '<div class="table-wrap"><table><thead><tr><th>Tarefa</th><th>Lei do Bem</th><th>Situação</th><th></th>'
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )
    return page(ctx, "Tarefas", body)


def _fields(ctx: Ctx, task: Task | None) -> str:
    f = ctx.form
    posted = ctx.request.method == "POST"
    rd_eligible = f.get("lei_do_bem") == "1" if posted else (task.rd_eligible if task else True)
    fields = text_field("nome", "Nome", f.get("nome", task.name if task else ""), maxlength=60,
                        autofocus=task is None)
    fields += checkbox_field("lei_do_bem", "Conta para a Lei do Bem", rd_eligible, hint=RD_HINT)
    if task:
        active = f.get("ativo") == "1" if posted else task.active
        fields += checkbox_field("ativo", "Ativa", active, hint="Inativa some da lista de quem aponta.")
        fields += f'<p class="muted">{e(RD_CHANGE_NOTE)}</p>'
    return fields


def _new_page(ctx: Ctx, *, error: str | None = None) -> Response:
    return page(ctx, "Nova tarefa", form(ctx, "/tarefas/nova", _fields(ctx, None), "Criar", cancel_href="/tarefas"),
                error=error)


def new_get(ctx: Ctx) -> Response:
    return _new_page(ctx)


def new_post(ctx: Ctx) -> Response:
    f = ctx.form
    try:
        tasks_service.create_task(ctx.conn, ctx.user, name=f.get("nome", ""), rd_eligible=f.get("lei_do_bem") == "1")
    except AppError as exc:
        return _new_page(ctx, error=str(exc))
    return redirect("/tarefas?msg=criado")


def _edit_page(ctx: Ctx, task: Task, *, error: str | None = None) -> Response:
    action = f"/tarefas/{task.id}/editar"
    return page(ctx, f"Editar: {task.name}", form(ctx, action, _fields(ctx, task), "Salvar", cancel_href="/tarefas"),
                error=error)


def edit_get(ctx: Ctx, task_id: str) -> Response:
    return _edit_page(ctx, tasks_service.get_task(ctx.conn, ctx.user, int(task_id)))


def edit_post(ctx: Ctx, task_id: str) -> Response:
    f = ctx.form
    try:
        tasks_service.update_task(
            ctx.conn, ctx.user, int(task_id), name=f.get("nome", ""), rd_eligible=f.get("lei_do_bem") == "1",
            active=f.get("ativo") == "1",
        )
    except AppError as exc:
        return _edit_page(ctx, tasks_service.get_task(ctx.conn, ctx.user, int(task_id)), error=str(exc))
    return redirect("/tarefas?msg=salvo")


def _delete_page(ctx: Ctx, task: Task, *, error: str | None = None) -> Response:
    fields = (
        f"<p>Excluir a tarefa <strong>{e(task.name)}</strong>? Esta ação não pode ser desfeita.</p>"
        '<p class="muted">Tarefa já usada em apontamentos só pode ser <em>desativada</em> (em Editar).</p>'
    )
    action = f"/tarefas/{task.id}/excluir"
    return page(ctx, "Excluir tarefa",
                form(ctx, action, fields, "Confirmar exclusão", cancel_href="/tarefas", danger=True), error=error)


def delete_get(ctx: Ctx, task_id: str) -> Response:
    return _delete_page(ctx, tasks_service.get_task(ctx.conn, ctx.user, int(task_id)))


def delete_post(ctx: Ctx, task_id: str) -> Response:
    try:
        tasks_service.delete_task(ctx.conn, ctx.user, int(task_id))
    except AppError as exc:
        return _delete_page(ctx, tasks_service.get_task(ctx.conn, ctx.user, int(task_id)), error=str(exc))
    return redirect("/tarefas?msg=excluido")


ROUTES = [
    Route("GET", "/tarefas", list_page, Access.ADMIN),
    Route("GET", "/tarefas/nova", new_get, Access.ADMIN),
    Route("POST", "/tarefas/nova", new_post, Access.ADMIN),
    Route("GET", r"/tarefas/(\d+)/editar", edit_get, Access.ADMIN),
    Route("POST", r"/tarefas/(\d+)/editar", edit_post, Access.ADMIN),
    Route("GET", r"/tarefas/(\d+)/excluir", delete_get, Access.ADMIN),
    Route("POST", r"/tarefas/(\d+)/excluir", delete_post, Access.ADMIN),
]
