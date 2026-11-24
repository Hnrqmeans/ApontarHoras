"""Despacha cada requisição: sessão → primeiro acesso → rota → login/permissão/CSRF → tela.

As travas daqui são a primeira barreira; os `services` conferem a permissão de novo (segunda barreira).
"""

import logging
import re
from importlib import resources
from urllib.parse import urlsplit

from apontarhoras.auth.tokens import csrf_matches
from apontarhoras.domain.errors import NotFound, PermissionDenied
from apontarhoras.services import auth_service
from apontarhoras.storage.db import Database
from apontarhoras.web.components import SESSION_COOKIE, clear_session_cookie, error_page
from apontarhoras.web.http import Request, Response, redirect
from apontarhoras.web.pages import audit, auth, entries, home, projects, reports, tasks, users
from apontarhoras.web.routing import Access, Ctx, Route

logger = logging.getLogger(__name__)

ALL_ROUTES: list[Route] = [
    *auth.ROUTES,
    *home.ROUTES,
    *entries.ROUTES,
    *users.ROUTES,
    *projects.ROUTES,
    *tasks.ROUTES,
    *audit.ROUTES,
    *reports.ROUTES,
]

_STATIC_NAME = re.compile(r"^[a-z0-9_-]+\.(css|svg|png|ico)$")
_STATIC_TYPES = {"css": "text/css; charset=utf-8", "svg": "image/svg+xml", "png": "image/png", "ico": "image/x-icon"}

SECURITY_HEADERS = [
    ("Content-Security-Policy",
     "default-src 'self'; script-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self'; "
     "frame-ancestors 'none'"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    # Não use "no-referrer": com ela o navegador manda `Origin: null` no POST e a trava de origem recusa tudo.
    ("Referrer-Policy", "same-origin"),
]


class App:
    def __init__(self, db: Database, *, secure_cookies: bool = False) -> None:
        self.db = db
        self.secure_cookies = secure_cookies
        self.routes = ALL_ROUTES

    def handle(self, request: Request) -> Response:
        if request.path.startswith("/static/"):
            response = self._static(request.path.removeprefix("/static/"))
        else:
            conn = self.db.connect()
            try:
                response = self._dispatch(Ctx(request, conn, secure_cookies=self.secure_cookies))
            finally:
                conn.close()
            response.headers.append(("Cache-Control", "no-store"))
        response.headers.extend(SECURITY_HEADERS)
        return response

    # ---- partes ----------------------------------------------------------------------------------------------

    def _static(self, name: str) -> Response:
        if not _STATIC_NAME.match(name):
            return Response(status=404, body=b"", content_type="text/plain")
        resource = resources.files("apontarhoras.web") / "static" / name
        if not resource.is_file():
            return Response(status=404, body=b"", content_type="text/plain")
        content_type = _STATIC_TYPES[name.rsplit(".", 1)[1]]
        return Response(body=resource.read_bytes(), content_type=content_type,
                        headers=[("Cache-Control", "max-age=3600")])

    def _match(self, method: str, path: str) -> tuple[Route | None, tuple[str, ...], bool]:
        path_exists = False
        for route in self.routes:
            match = route.regex.match(path)
            if match:
                path_exists = True
                if route.method == method:
                    return route, match.groups(), True
        return None, (), path_exists

    def _dispatch(self, ctx: Ctx) -> Response:
        request = ctx.request
        token = request.cookies.get(SESSION_COOKIE)
        stale_cookie = False
        if token:
            ctx.user = auth_service.user_for_token(ctx.conn, token)
            if ctx.user:
                ctx.token = token
            else:
                stale_cookie = True

        if request.method == "POST" and not _same_origin(request):
            return error_page(ctx, 403, "Formulário enviado de outro site.")

        if auth_service.needs_setup(ctx.conn) and request.path != "/primeiro-acesso":
            return redirect("/primeiro-acesso")

        route, groups, path_exists = self._match(request.method, request.path)
        if route is None:
            if path_exists:
                return error_page(ctx, 405, "Operação inválida para este endereço.")
            return error_page(ctx, 404, "Página não encontrada.")

        if route.access is not Access.PUBLIC:
            if ctx.user is None:
                response = redirect("/entrar")
                if stale_cookie:
                    response.headers.append(clear_session_cookie())
                return response
            if ctx.user.must_change_password and not route.allowed_before_password_change:
                return redirect("/trocar-senha")
            if route.access is Access.ADMIN and not ctx.user.is_admin:
                return error_page(ctx, 403, "Somente o responsável pode acessar esta página.")
            if request.method == "POST" and not csrf_matches(ctx.token, ctx.form.get("csrf", "")):
                return error_page(ctx, 403, "O formulário expirou. Volte, recarregue a página e tente de novo.")

        try:
            return route.handler(ctx, *groups)
        except PermissionDenied as exc:
            return error_page(ctx, 403, str(exc))
        except NotFound as exc:
            return error_page(ctx, 404, str(exc))


def _same_origin(request: Request) -> bool:
    """Navegadores mandam `Origin` em todo POST: se veio de outro endereço, recusa."""
    origin = request.headers.get("Origin")
    if not origin or origin == "null":
        return origin is None
    return urlsplit(origin).netloc.lower() == (request.headers.get("Host") or "").lower()
