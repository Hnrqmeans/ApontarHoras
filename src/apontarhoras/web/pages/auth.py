"""Primeiro acesso, entrar, sair e trocar a própria senha."""

from apontarhoras.domain.errors import AppError, AuthError
from apontarhoras.domain.user import MIN_PASSWORD_LENGTH
from apontarhoras.services import auth_service
from apontarhoras.web.components import (
    clear_session_cookie,
    form,
    page,
    password_field,
    session_cookie,
    text_field,
)
from apontarhoras.web.http import Response, redirect
from apontarhoras.web.routing import Access, Ctx, Route

PASSWORD_HINT = f"Mínimo de {MIN_PASSWORD_LENGTH} caracteres; diferente do login."


# ---- primeiro acesso -----------------------------------------------------------------------------------------


def _setup_page(ctx: Ctx, *, error: str | None = None) -> Response:
    f = ctx.form
    fields = (
        '<p class="muted">Ninguém foi cadastrado ainda. Crie o usuário do <strong>responsável</strong>: ele cadastra '
        "os projetos e os colaboradores e vê as horas de todos.</p>"
        + text_field("nome", "Seu nome", f.get("nome", ""), maxlength=100, autofocus=True)
        + text_field(
            "login", "Login", f.get("login", ""), maxlength=32, hint="Ex.: maria.silva", autocomplete="username"
        )
        + password_field("senha", "Senha", autocomplete="new-password", hint=PASSWORD_HINT)
        + password_field("confirmacao", "Repita a senha", autocomplete="new-password")
    )
    return page(ctx, "Primeiro acesso", form(ctx, "/primeiro-acesso", fields, "Criar responsável"), error=error)


def setup_get(ctx: Ctx) -> Response:
    if not auth_service.needs_setup(ctx.conn):
        return redirect("/")
    return _setup_page(ctx)


def setup_post(ctx: Ctx) -> Response:
    f = ctx.form
    if f.get("senha", "") != f.get("confirmacao", ""):
        return _setup_page(ctx, error="As senhas não são iguais.")
    try:
        auth_service.setup_first_admin(ctx.conn, f.get("nome", ""), f.get("login", ""), f.get("senha", ""))
        result = auth_service.login(ctx.conn, f.get("login", ""), f.get("senha", ""))
    except AppError as exc:
        return _setup_page(ctx, error=str(exc))
    response = redirect("/?msg=bem_vindo")
    response.headers.append(session_cookie(result.token, secure=ctx.secure_cookies))
    return response


# ---- entrar / sair -------------------------------------------------------------------------------------------


def _login_page(ctx: Ctx, *, error: str | None = None) -> Response:
    fields = text_field(
        "login", "Login", ctx.form.get("login", ""), maxlength=32, autofocus=True, autocomplete="username"
    ) + password_field("senha", "Senha")
    body = form(ctx, "/entrar", fields, "Entrar") + '<p class="muted">Esqueceu a senha? Fale com o responsável.</p>'
    return page(ctx, "Entrar", body, error=error)


def login_get(ctx: Ctx) -> Response:
    if ctx.user:
        return redirect("/")
    return _login_page(ctx)


def login_post(ctx: Ctx) -> Response:
    try:
        result = auth_service.login(ctx.conn, ctx.form.get("login", ""), ctx.form.get("senha", ""))
    except AuthError as exc:
        return _login_page(ctx, error=str(exc))
    response = redirect("/")
    response.headers.append(session_cookie(result.token, secure=ctx.secure_cookies))
    return response


def logout_post(ctx: Ctx) -> Response:
    auth_service.logout(ctx.conn, ctx.token)
    response = redirect("/entrar")
    response.headers.append(clear_session_cookie())
    return response


# ---- trocar senha --------------------------------------------------------------------------------------------


def _password_page(ctx: Ctx, *, error: str | None = None) -> Response:
    intro = ""
    if ctx.user.must_change_password:
        intro = '<p class="muted">Você entrou com uma senha temporária. Crie a sua senha para continuar.</p>'
    fields = (
        intro
        + password_field("atual", "Senha atual", autofocus=True)
        + password_field("nova", "Nova senha", autocomplete="new-password", hint=PASSWORD_HINT)
        + password_field("confirmacao", "Repita a nova senha", autocomplete="new-password")
    )
    cancel = None if ctx.user.must_change_password else "/"
    body = form(ctx, "/trocar-senha", fields, "Trocar senha", cancel_href=cancel)
    return page(ctx, "Trocar senha", body, error=error)


def password_get(ctx: Ctx) -> Response:
    return _password_page(ctx)


def password_post(ctx: Ctx) -> Response:
    f = ctx.form
    try:
        auth_service.change_password(
            ctx.conn, ctx.user, ctx.token, f.get("atual", ""), f.get("nova", ""), f.get("confirmacao", "")
        )
    except AppError as exc:
        return _password_page(ctx, error=str(exc))
    return redirect("/?msg=senha_trocada")


ROUTES = [
    Route("GET", "/primeiro-acesso", setup_get, Access.PUBLIC),
    Route("POST", "/primeiro-acesso", setup_post, Access.PUBLIC),
    Route("GET", "/entrar", login_get, Access.PUBLIC),
    Route("POST", "/entrar", login_post, Access.PUBLIC),
    Route("POST", "/sair", logout_post, Access.USER, allowed_before_password_change=True),
    Route("GET", "/trocar-senha", password_get, Access.USER, allowed_before_password_change=True),
    Route("POST", "/trocar-senha", password_post, Access.USER, allowed_before_password_change=True),
]
