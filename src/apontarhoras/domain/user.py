"""Usuário, papel e regras de login/senha."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from apontarhoras.domain.errors import ValidationError


class Role(StrEnum):
    ADMIN = "admin"
    COLLABORATOR = "colaborador"

    @property
    def label(self) -> str:
        return "Responsável" if self is Role.ADMIN else "Colaborador"


MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=15)
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

_LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")


@dataclass(frozen=True)
class User:
    id: int
    name: str
    login: str
    role: Role
    active: bool
    must_change_password: bool
    failed_attempts: int
    locked_until: datetime | None
    created_at: datetime

    @property
    def is_admin(self) -> bool:
        return self.active and self.role is Role.ADMIN

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and now < self.locked_until


def parse_role(value: str) -> Role:
    try:
        return Role(value)
    except ValueError:
        raise ValidationError("Papel inválido.") from None


def normalize_login(raw: str) -> str:
    return raw.strip().lower()


def validate_login(login: str) -> None:
    if not _LOGIN_RE.match(login):
        raise ValidationError(
            "O login deve ter de 3 a 32 caracteres: letras minúsculas sem acento, números, ponto, hífen ou "
            "sublinhado, começando por letra ou número."
        )


def normalize_name(raw: str) -> str:
    return " ".join(raw.split())


def validate_name(name: str) -> None:
    if not 2 <= len(name) <= 100:
        raise ValidationError("O nome deve ter de 2 a 100 caracteres.")


def validate_password(password: str, login: str = "") -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValidationError(f"A senha deve ter no máximo {MAX_PASSWORD_LENGTH} caracteres.")
    if login and password.strip().lower() == login.lower():
        raise ValidationError("A senha não pode ser igual ao login.")


def after_failed_attempt(failed_attempts: int, now: datetime) -> tuple[int, datetime | None]:
    """Conta a tentativa errada. Na 5ª seguida, bloqueia por 15 minutos e zera a contagem."""
    attempts = failed_attempts + 1
    if attempts >= MAX_FAILED_ATTEMPTS:
        return 0, now + LOCK_DURATION
    return attempts, None
