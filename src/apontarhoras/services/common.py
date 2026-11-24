"""Peças comuns aos serviços: relógio e checagem de permissão."""

from datetime import UTC, datetime

from apontarhoras.domain.errors import PermissionDenied
from apontarhoras.domain.user import User


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def require_user(actor: User | None) -> User:
    if actor is None or not actor.active:
        raise PermissionDenied("Entre no sistema para continuar.")
    return actor


def require_admin(actor: User | None) -> User:
    user = require_user(actor)
    if not user.is_admin:
        raise PermissionDenied("Somente o responsável pode fazer isso.")
    return user
