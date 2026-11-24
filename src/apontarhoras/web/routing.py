"""Rota e contexto da requisição (compartilhados por todas as telas)."""

import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from apontarhoras.auth.tokens import csrf_for
from apontarhoras.domain.user import User
from apontarhoras.web.http import Request, Response


class Access(Enum):
    PUBLIC = "public"  # sem login (entrar, primeiro acesso)
    USER = "user"  # qualquer usuário logado
    ADMIN = "admin"  # só o responsável


@dataclass
class Ctx:
    request: Request
    conn: sqlite3.Connection
    user: User | None = None
    token: str | None = None
    secure_cookies: bool = False

    @property
    def csrf(self) -> str:
        return csrf_for(self.token) if self.token else ""

    @property
    def form(self) -> dict[str, str]:
        return self.request.form


Handler = Callable[..., Response]


@dataclass
class Route:
    method: str
    pattern: str
    handler: Handler
    access: Access
    # rotas que continuam abertas quando o usuário ainda precisa trocar a senha temporária
    allowed_before_password_change: bool = False
    regex: re.Pattern = field(init=False)

    def __post_init__(self) -> None:
        self.regex = re.compile(f"^{self.pattern}$")
