"""Requisição/resposta simples, independentes do http.server (facilita testar)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from http.cookies import CookieError, SimpleCookie
from urllib.parse import parse_qs


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    form: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass
class Response:
    status: int = 200
    body: bytes = b""
    content_type: str = "text/html; charset=utf-8"
    headers: list[tuple[str, str]] = field(default_factory=list)


def parse_fields(raw: str) -> dict[str, str]:
    """`a=1&b=2` → {"a": "1", "b": "2"} (primeiro valor de cada campo; campos vazios mantidos)."""
    return {key: values[0] for key, values in parse_qs(raw, keep_blank_values=True).items()}


def parse_cookies(header: str | None) -> dict[str, str]:
    if not header:
        return {}
    cookie = SimpleCookie()
    try:
        cookie.load(header)
    except CookieError:
        return {}
    return {key: morsel.value for key, morsel in cookie.items()}


def html_response(body: str, status: int = 200) -> Response:
    return Response(status=status, body=body.encode("utf-8"))


def redirect(location: str) -> Response:
    """303: depois de um POST, o navegador volta com GET (F5 não reenvia o formulário)."""
    return Response(status=303, headers=[("Location", location)])
