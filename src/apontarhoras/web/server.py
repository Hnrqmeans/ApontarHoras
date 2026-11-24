"""Servidor HTTP (http.server da biblioteca padrão, uma thread por conexão)."""

import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from apontarhoras.web.app import App
from apontarhoras.web.http import Request, Response, html_response, parse_cookies, parse_fields

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 1_000_000


class _Handler(BaseHTTPRequestHandler):
    server_version = "ApontarHoras"
    sys_version = ""
    server: "AppServer"

    def do_GET(self) -> None:  # noqa: N802 (nome exigido pelo http.server)
        self._run("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._run("POST")

    def _run(self, method: str) -> None:
        try:
            response = self._handle(method)
        except Exception:
            logger.exception("Erro inesperado em %s %s", method, urlsplit(self.path).path)
            response = html_response("<h1>Erro inesperado</h1><p>Tente de novo. Se repetir, avise o responsável.</p>",
                                     500)
        self._send(response)

    def _handle(self, method: str) -> Response:
        parsed = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            return Response(status=413, body=b"Envio grande demais.", content_type="text/plain; charset=utf-8")
        raw_body = self.rfile.read(length) if length else b""
        request = Request(
            method=method,
            path=parsed.path or "/",
            query=parse_fields(parsed.query),
            form=parse_fields(raw_body.decode("utf-8", errors="replace")) if method == "POST" else {},
            cookies=parse_cookies(self.headers.get("Cookie")),
            headers={key: value for key, value in self.headers.items()},
        )
        return self.server.app.handle(request)

    def _send(self, response: Response) -> None:
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        for name, value in response.headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(response.body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 (assinatura do http.server)
        logger.info("%s %s", self.address_string(), format % args)


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: App) -> None:
        self.app = app
        super().__init__(address, _Handler)
