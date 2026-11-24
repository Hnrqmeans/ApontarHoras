"""Ponta a ponta: servidor HTTP de verdade numa porta livre, navegando como um usuário (urllib + cookies)."""

import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

import pytest

from apontarhoras.web.app import App
from apontarhoras.web.server import AppServer

ADMIN_PASSWORD = "senha-do-admin-1"


class Browser:
    def __init__(self, base: str) -> None:
        self.base = base
        self.cookies = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.last = ""

    def _open(self, request: urllib.request.Request) -> tuple[int, str, str, dict]:
        try:
            with self.opener.open(request, timeout=10) as response:
                body = response.read().decode("utf-8")
                result = (response.status, urllib.parse.urlsplit(response.url).path, body, dict(response.headers))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8")
            result = (error.code, urllib.parse.urlsplit(error.url).path, body, dict(error.headers))
        self.last = result[2]
        return result

    def get(self, path: str):
        return self._open(urllib.request.Request(self.base + path))

    def post(self, path: str, data: dict, *, csrf: bool = True, headers: dict | None = None):
        fields = dict(data)
        if csrf:
            match = re.search(r'name="csrf" value="([^"]+)"', self.last)
            if match:
                fields["csrf"] = match.group(1)
        encoded = urllib.parse.urlencode(fields).encode()
        return self._open(urllib.request.Request(self.base + path, data=encoded, headers=headers or {}))


@pytest.fixture
def server(db):
    httpd = AppServer(("127.0.0.1", 0), App(db))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _setup_admin(server) -> Browser:
    browser = Browser(server)
    status, path, _, _ = browser.get("/")
    assert path == "/primeiro-acesso"
    status, path, body, _ = browser.post(
        "/primeiro-acesso",
        {"nome": "Ana Responsável", "login": "ana", "senha": ADMIN_PASSWORD, "confirmacao": ADMIN_PASSWORD},
    )
    assert (status, path) == (200, "/")
    assert "Responsável criado" in body
    return browser


def test_first_access_and_security_headers(server):
    browser = _setup_admin(server)
    _, _, _, headers = browser.get("/")
    assert "script-src 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Frame-Options"] == "DENY"
    assert "HttpOnly" in str(browser.cookies) or any(c.name == "ah_sessao" for c in browser.cookies)
    # primeiro acesso não pode ser refeito
    _, path, _, _ = browser.get("/primeiro-acesso")
    assert path == "/"


def test_requires_login(server):
    _setup_admin(server)
    anonymous = Browser(server)
    _, path, body, _ = anonymous.get("/usuarios")
    assert path == "/entrar"
    status, _, body, _ = anonymous.post("/entrar", {"login": "ana", "senha": "errada-123"})
    assert "Usuário ou senha inválidos" in body
    status, path, _, _ = anonymous.post("/entrar", {"login": "ana", "senha": ADMIN_PASSWORD})
    assert (status, path) == (200, "/")


def test_admin_flow_users_and_projects(server):
    admin = _setup_admin(server)
    # novo projeto
    admin.get("/projetos/novo")
    _, path, body, _ = admin.post("/projetos/novo", {"codigo": "pd-01", "nome": "Sensor <novo>", "descricao": ""})
    assert path == "/projetos"
    assert "PD-01" in body
    assert "Sensor &lt;novo&gt;" in body  # texto do usuário sempre escapado
    project_id = re.search(r"/projetos/(\d+)/excluir", body).group(1)
    # exclusão em dois cliques: link → página de confirmação → confirmar
    _, _, body, _ = admin.get(f"/projetos/{project_id}/excluir")
    assert "Confirmar exclusão" in body
    _, path, body, _ = admin.post(f"/projetos/{project_id}/excluir", {})
    assert path == "/projetos"
    assert "PD-01" not in body
    # novo colaborador
    admin.get("/usuarios/novo")
    _, path, body, _ = admin.post(
        "/usuarios/novo", {"nome": "Bruno Colaborador", "login": "bruno", "papel": "colaborador",
                           "senha": "temporaria-123"}
    )
    assert path == "/usuarios"
    assert "Aguardando 1º acesso" in body
    # auditoria mostra o que foi feito
    _, _, body, _ = admin.get("/auditoria")
    assert "Criou" in body and "Excluiu" in body


def test_collaborator_flow_and_permissions(server):
    admin = _setup_admin(server)
    admin.get("/usuarios/novo")
    admin.post("/usuarios/novo", {"nome": "Bruno Colaborador", "login": "bruno", "papel": "colaborador",
                                  "senha": "temporaria-123"})
    bruno = Browser(server)
    bruno.get("/entrar")
    _, path, _, _ = bruno.post("/entrar", {"login": "bruno", "senha": "temporaria-123"})
    assert path == "/trocar-senha"  # senha temporária: obrigado a trocar
    _, path, _, _ = bruno.get("/")
    assert path == "/trocar-senha"
    _, path, body, _ = bruno.post(
        "/trocar-senha", {"atual": "temporaria-123", "nova": "senha-do-bruno", "confirmacao": "senha-do-bruno"}
    )
    assert path == "/"
    assert "Senha alterada" in body
    # colaborador não acessa telas do responsável
    for url in ["/usuarios", "/projetos", "/auditoria", "/usuarios/1/editar"]:
        status, _, _, _ = bruno.get(url)
        assert status == 403, url
    status, _, _, _ = bruno.post("/usuarios/novo", {"nome": "X Y", "login": "xy", "papel": "admin",
                                                    "senha": "qualquer-123"})
    assert status == 403


def test_post_without_csrf_is_rejected(server):
    admin = _setup_admin(server)
    status, _, body, _ = admin.post("/projetos/novo", {"codigo": "P1", "nome": "Projeto"}, csrf=False)
    assert status == 403
    assert "expirou" in body


def test_post_from_other_site_is_rejected(server):
    admin = _setup_admin(server)
    admin.get("/projetos/novo")
    status, _, _, _ = admin.post("/projetos/novo", {"codigo": "P1", "nome": "Projeto"},
                                 headers={"Origin": "http://site-malicioso.exemplo"})
    assert status == 403


def test_logout(server):
    admin = _setup_admin(server)
    admin.get("/")
    _, path, _, _ = admin.post("/sair", {})
    assert path == "/entrar"
    _, path, _, _ = admin.get("/usuarios")
    assert path == "/entrar"


def test_static_and_not_found(server):
    browser = Browser(server)
    status, _, body, headers = browser.get("/static/style.css")
    assert status == 200 and "--primary" in body
    status, _, _, _ = browser.get("/static/../app.py")
    assert status == 404
