"""Peças de HTML usadas por várias telas: layout, campos de formulário, mensagens.

Todo texto que veio do usuário ou do banco passa por `e()` (escape) antes de entrar no HTML.
"""

from datetime import datetime
from html import escape

from apontarhoras import APP_NAME, __version__
from apontarhoras.web.http import Response, html_response
from apontarhoras.web.routing import Ctx

SESSION_COOKIE = "ah_sessao"

# ?msg=<código> depois de um redirecionamento
MESSAGES = {
    "bem_vindo": "Responsável criado. Agora cadastre os projetos e os colaboradores.",
    "criado": "Cadastro criado.",
    "salvo": "Alterações salvas.",
    "excluido": "Excluído.",
    "senha_trocada": "Senha alterada.",
    "senha_redefinida": "Senha temporária definida. Passe-a para a pessoa: ela vai trocá-la no próximo acesso.",
}


def e(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def fmt_datetime(moment: datetime | None) -> str:
    """UTC do banco → horário local do servidor."""
    return moment.astimezone().strftime("%d/%m/%Y %H:%M") if moment else ""


def session_cookie(token: str, *, secure: bool) -> tuple[str, str]:
    flags = "; Secure" if secure else ""
    return ("Set-Cookie", f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict{flags}")


def clear_session_cookie() -> tuple[str, str]:
    return ("Set-Cookie", f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")


def _nav(ctx: Ctx) -> str:
    user = ctx.user
    if user is None:
        return ""
    logout = (
        f'<form method="post" action="/sair" class="inline">{csrf_input(ctx)}'
        '<button type="submit" class="link">Sair</button></form>'
    )
    if user.must_change_password:
        return f'<div class="who"><span>{e(user.name)}</span>{logout}</div>'
    items = [("/", "Início")]
    if user.is_admin:
        items += [("/usuarios", "Colaboradores"), ("/projetos", "Projetos"), ("/auditoria", "Auditoria")]
    path = ctx.request.path
    links = ""
    for href, label in items:
        current = path == href or (href != "/" and path.startswith(href))
        links += f'<a href="{href}" class="active">{label}</a>' if current else f'<a href="{href}">{label}</a>'
    return (
        f'<nav class="menu">{links}</nav>'
        f'<div class="who"><span>{e(user.name)} · {e(user.role.label)}</span>'
        f'<a href="/trocar-senha">Trocar senha</a>{logout}</div>'
    )


def layout(ctx: Ctx, title: str, body: str, *, error: str | None = None) -> str:
    flash = MESSAGES.get(ctx.request.query.get("msg", ""))
    notices = ""
    if flash:
        notices += f'<div class="notice ok" role="status">{e(flash)}</div>'
    if error:
        notices += f'<div class="notice error" role="alert">{e(error)}</div>'
    logout_area = _nav(ctx)
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} · {APP_NAME}</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
<header class="top"><a class="brand" href="/">{APP_NAME}</a>{logout_area}</header>
<main>
<h1>{e(title)}</h1>
{notices}
{body}
</main>
<footer>{APP_NAME} v{__version__}</footer>
</body>
</html>"""


def page(ctx: Ctx, title: str, body: str, *, error: str | None = None, status: int = 200) -> Response:
    return html_response(layout(ctx, title, body, error=error), status)


def error_page(ctx: Ctx, status: int, message: str) -> Response:
    titles = {403: "Acesso negado", 404: "Não encontrado", 405: "Operação inválida"}
    body = f'<p>{e(message)}</p><p><a href="/">Voltar ao início</a></p>'
    return page(ctx, titles.get(status, "Erro"), body, status=status)


# ---- formulários ---------------------------------------------------------------------------------------------


def csrf_input(ctx: Ctx) -> str:
    return f'<input type="hidden" name="csrf" value="{e(ctx.csrf)}">' if ctx.csrf else ""


def _hint(hint: str | None) -> str:
    return f'<small class="hint">{e(hint)}</small>' if hint else ""


def text_field(
    name: str,
    label: str,
    value: str = "",
    *,
    required: bool = True,
    maxlength: int | None = None,
    hint: str | None = None,
    autofocus: bool = False,
    autocomplete: str = "off",
    readonly: bool = False,
) -> str:
    attrs = " required" if required else ""
    attrs += f' maxlength="{maxlength}"' if maxlength else ""
    attrs += " autofocus" if autofocus else ""
    attrs += " readonly" if readonly else ""
    return (
        f'<label>{e(label)}<input type="text" name="{name}" value="{e(value)}" autocomplete="{autocomplete}"{attrs}>'
        f"{_hint(hint)}</label>"
    )


def password_field(
    name: str, label: str, *, autocomplete: str = "current-password", hint: str | None = None, autofocus: bool = False
) -> str:
    attrs = " autofocus" if autofocus else ""
    return (
        f'<label>{e(label)}<input type="password" name="{name}" required maxlength="128" '
        f'autocomplete="{autocomplete}"{attrs}>{_hint(hint)}</label>'
    )


def textarea_field(name: str, label: str, value: str = "", *, maxlength: int = 2000, hint: str | None = None) -> str:
    return (
        f'<label>{e(label)}<textarea name="{name}" rows="4" maxlength="{maxlength}">{e(value)}</textarea>'
        f"{_hint(hint)}</label>"
    )


def select_field(name: str, label: str, options: list[tuple[str, str]], selected: str) -> str:
    opts = "".join(
        f'<option value="{e(value)}"{" selected" if value == selected else ""}>{e(text)}</option>'
        for value, text in options
    )
    return f'<label>{e(label)}<select name="{name}">{opts}</select></label>'


def checkbox_field(name: str, label: str, checked: bool, *, hint: str | None = None) -> str:
    return (
        f'<label class="check"><input type="checkbox" name="{name}" value="1"{" checked" if checked else ""}>'
        f"{e(label)}</label>{_hint(hint)}"
    )


def form(
    ctx: Ctx,
    action: str,
    fields: str,
    submit: str,
    *,
    cancel_href: str | None = None,
    danger: bool = False,
) -> str:
    cancel = f'<a class="button secondary" href="{e(cancel_href)}">Cancelar</a>' if cancel_href else ""
    css = "danger" if danger else "primary"
    return (
        f'<form method="post" action="{e(action)}" class="card form">{csrf_input(ctx)}{fields}'
        f'<div class="actions"><button type="submit" class="button {css}">{e(submit)}</button>{cancel}</div></form>'
    )


def badge(text: str, kind: str = "") -> str:
    return f'<span class="badge {kind}">{e(text)}</span>'
