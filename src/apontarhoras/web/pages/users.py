"""Colaboradores (só o responsável): listar, criar, editar, redefinir senha, excluir."""

from apontarhoras.domain.errors import AppError
from apontarhoras.domain.user import MIN_PASSWORD_LENGTH, Role, User
from apontarhoras.services import users_service
from apontarhoras.services.common import utcnow
from apontarhoras.web.components import (
    badge,
    checkbox_field,
    e,
    form,
    page,
    password_field,
    select_field,
    single_admin_notice,
    text_field,
)
from apontarhoras.web.http import Response, redirect
from apontarhoras.web.routing import Access, Ctx, Route

ROLE_OPTIONS = [(Role.COLLABORATOR.value, Role.COLLABORATOR.label), (Role.ADMIN.value, Role.ADMIN.label)]
TEMP_HINT = f"Mínimo de {MIN_PASSWORD_LENGTH} caracteres. A pessoa troca no primeiro acesso."


def _status(user: User) -> str:
    if not user.active:
        return badge("Inativo", "off")
    if user.is_locked(utcnow()):
        return badge("Bloqueado", "warn")
    if user.must_change_password:
        return badge("Aguardando 1º acesso")
    return badge("Ativo")


def list_page(ctx: Ctx) -> Response:
    users = users_service.list_users(ctx.conn, ctx.user)
    rows = "".join(
        f"<tr><td>{e(u.name)}</td><td>{e(u.login)}</td><td>{e(u.role.label)}</td><td>{_status(u)}</td>"
        f'<td class="actions-cell"><a href="/usuarios/{u.id}/editar">Editar</a>'
        f'<a href="/usuarios/{u.id}/senha">Senha</a><a href="/usuarios/{u.id}/excluir">Excluir</a></td></tr>'
        for u in users
    )
    body = (
        '<div class="toolbar"><span class="muted">Quem aponta horas (colaborador) e quem administra (responsável).'
        '</span><a class="button primary" href="/usuarios/novo">Novo colaborador</a></div>'
        '<div class="table-wrap"><table><thead><tr><th>Nome</th><th>Login</th><th>Papel</th><th>Situação</th>'
        f"<th></th></tr></thead><tbody>{rows}</tbody></table></div>"
    )
    if users_service.has_single_admin(ctx.conn, ctx.user):
        body = single_admin_notice() + body
    return page(ctx, "Colaboradores", body)


# ---- novo ----------------------------------------------------------------------------------------------------


def _new_page(ctx: Ctx, *, error: str | None = None) -> Response:
    f = ctx.form
    fields = (
        text_field("nome", "Nome", f.get("nome", ""), maxlength=100, autofocus=True)
        + text_field("login", "Login", f.get("login", ""), maxlength=32, hint="Ex.: maria.silva")
        + select_field("papel", "Papel", ROLE_OPTIONS, f.get("papel", Role.COLLABORATOR.value))
        + password_field("senha", "Senha temporária", autocomplete="new-password", hint=TEMP_HINT)
    )
    return page(ctx, "Novo colaborador", form(ctx, "/usuarios/novo", fields, "Criar", cancel_href="/usuarios"),
                error=error)


def new_get(ctx: Ctx) -> Response:
    return _new_page(ctx)


def new_post(ctx: Ctx) -> Response:
    f = ctx.form
    try:
        users_service.create_user(
            ctx.conn,
            ctx.user,
            name=f.get("nome", ""),
            login=f.get("login", ""),
            role=f.get("papel", ""),
            temporary_password=f.get("senha", ""),
        )
    except AppError as exc:
        return _new_page(ctx, error=str(exc))
    return redirect("/usuarios?msg=criado")


# ---- editar --------------------------------------------------------------------------------------------------


def _edit_page(ctx: Ctx, user: User, *, error: str | None = None) -> Response:
    f = ctx.form
    posted = ctx.request.method == "POST"
    fields = (
        text_field("login", "Login", user.login, readonly=True, hint="O login não muda.")
        + text_field("nome", "Nome", f.get("nome", user.name), maxlength=100)
        + select_field("papel", "Papel", ROLE_OPTIONS, f.get("papel", user.role.value))
        + checkbox_field(
            "ativo",
            "Ativo",
            f.get("ativo") == "1" if posted else user.active,
            hint="Desativado não entra no sistema, mas o histórico dele continua.",
        )
    )
    action = f"/usuarios/{user.id}/editar"
    return page(ctx, f"Editar: {user.name}", form(ctx, action, fields, "Salvar", cancel_href="/usuarios"),
                error=error)


def edit_get(ctx: Ctx, user_id: str) -> Response:
    return _edit_page(ctx, users_service.get_user(ctx.conn, ctx.user, int(user_id)))


def edit_post(ctx: Ctx, user_id: str) -> Response:
    f = ctx.form
    try:
        users_service.update_user(
            ctx.conn, ctx.user, int(user_id), name=f.get("nome", ""), role=f.get("papel", ""),
            active=f.get("ativo") == "1",
        )
    except AppError as exc:
        return _edit_page(ctx, users_service.get_user(ctx.conn, ctx.user, int(user_id)), error=str(exc))
    return redirect("/usuarios?msg=salvo")


# ---- redefinir senha -----------------------------------------------------------------------------------------


def _password_page(ctx: Ctx, user: User, *, error: str | None = None) -> Response:
    fields = (
        f'<p class="muted">Defina uma senha temporária para <strong>{e(user.name)}</strong> ({e(user.login)}). '
        "Isso também desbloqueia o acesso e encerra as sessões abertas dessa pessoa.</p>"
        + password_field("senha", "Senha temporária", autocomplete="new-password", hint=TEMP_HINT, autofocus=True)
    )
    action = f"/usuarios/{user.id}/senha"
    return page(ctx, "Redefinir senha", form(ctx, action, fields, "Definir senha", cancel_href="/usuarios"),
                error=error)


def password_get(ctx: Ctx, user_id: str) -> Response:
    return _password_page(ctx, users_service.get_user(ctx.conn, ctx.user, int(user_id)))


def password_post(ctx: Ctx, user_id: str) -> Response:
    try:
        users_service.reset_password(ctx.conn, ctx.user, int(user_id), ctx.form.get("senha", ""))
    except AppError as exc:
        return _password_page(ctx, users_service.get_user(ctx.conn, ctx.user, int(user_id)), error=str(exc))
    return redirect("/usuarios?msg=senha_redefinida")


# ---- excluir (2 cliques: link → confirmar) -------------------------------------------------------------------


def _delete_page(ctx: Ctx, user: User, *, error: str | None = None) -> Response:
    fields = (
        f"<p>Excluir <strong>{e(user.name)}</strong> ({e(user.login)})? Esta ação não pode ser desfeita.</p>"
        '<p class="muted">Se a pessoa só saiu da equipe, prefira <em>desativar</em> em Editar.</p>'
    )
    action = f"/usuarios/{user.id}/excluir"
    return page(ctx, "Excluir colaborador",
                form(ctx, action, fields, "Confirmar exclusão", cancel_href="/usuarios", danger=True), error=error)


def delete_get(ctx: Ctx, user_id: str) -> Response:
    return _delete_page(ctx, users_service.get_user(ctx.conn, ctx.user, int(user_id)))


def delete_post(ctx: Ctx, user_id: str) -> Response:
    try:
        users_service.delete_user(ctx.conn, ctx.user, int(user_id))
    except AppError as exc:
        return _delete_page(ctx, users_service.get_user(ctx.conn, ctx.user, int(user_id)), error=str(exc))
    return redirect("/usuarios?msg=excluido")


ROUTES = [
    Route("GET", "/usuarios", list_page, Access.ADMIN),
    Route("GET", "/usuarios/novo", new_get, Access.ADMIN),
    Route("POST", "/usuarios/novo", new_post, Access.ADMIN),
    Route("GET", r"/usuarios/(\d+)/editar", edit_get, Access.ADMIN),
    Route("POST", r"/usuarios/(\d+)/editar", edit_post, Access.ADMIN),
    Route("GET", r"/usuarios/(\d+)/senha", password_get, Access.ADMIN),
    Route("POST", r"/usuarios/(\d+)/senha", password_post, Access.ADMIN),
    Route("GET", r"/usuarios/(\d+)/excluir", delete_get, Access.ADMIN),
    Route("POST", r"/usuarios/(\d+)/excluir", delete_post, Access.ADMIN),
]
