"""Primeiro acesso, login, sessão e troca da própria senha."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from apontarhoras.auth.passwords import dummy_hash, hash_password, verify_password
from apontarhoras.auth.tokens import new_token, token_hash
from apontarhoras.domain.errors import AuthError, PermissionDenied, ValidationError
from apontarhoras.domain.user import (
    Role,
    User,
    after_failed_attempt,
    normalize_login,
    normalize_name,
    validate_login,
    validate_name,
    validate_password,
)
from apontarhoras.services import audit
from apontarhoras.services.common import require_user, utcnow
from apontarhoras.storage import sessions_repo, users_repo
from apontarhoras.storage.db import transaction

SESSION_DURATION = timedelta(hours=12)

INVALID_CREDENTIALS = "Usuário ou senha inválidos."
LOCKED = "Acesso bloqueado por excesso de tentativas. Tente de novo em 15 minutos ou peça ao responsável."
INACTIVE = "Este usuário está desativado. Fale com o responsável."


@dataclass(frozen=True)
class LoginResult:
    token: str
    user: User


def needs_setup(conn: sqlite3.Connection) -> bool:
    """Banco sem nenhum usuário: o primeiro acesso cria o responsável."""
    return users_repo.count(conn) == 0


def setup_first_admin(
    conn: sqlite3.Connection, name: str, login: str, password: str, *, now: datetime | None = None
) -> User:
    now = now or utcnow()
    name, login = normalize_name(name), normalize_login(login)
    validate_name(name)
    validate_login(login)
    validate_password(password, login)
    with transaction(conn):
        if users_repo.count(conn):
            raise PermissionDenied("O primeiro acesso já foi feito. Entre com seu usuário.")
        user_id = users_repo.insert(
            conn,
            name=name,
            login=login,
            password_hash=hash_password(password),
            role=Role.ADMIN,
            must_change_password=False,
            now=now,
        )
        user = users_repo.get(conn, user_id)
        audit.record(conn, user, "setup", "user", user_id, {"nome": name, "login": login}, now=now)
    return user


def login(conn: sqlite3.Connection, login_name: str, password: str, *, now: datetime | None = None) -> LoginResult:
    now = now or utcnow()
    login_name = normalize_login(login_name)
    error: str | None = None
    with transaction(conn):
        sessions_repo.delete_expired(conn, now)
        found = users_repo.get_with_hash(conn, login_name)
        if found is None:
            verify_password(password, dummy_hash())  # mesmo tempo de resposta de uma senha errada
            error = INVALID_CREDENTIALS
        else:
            user, stored_hash = found
            if user.is_locked(now):
                error = LOCKED
            elif not verify_password(password, stored_hash):
                attempts, locked_until = after_failed_attempt(user.failed_attempts, now)
                users_repo.set_login_state(conn, user.id, failed_attempts=attempts, locked_until=locked_until)
                action = "locked" if locked_until else "login_failed"
                audit.record(conn, None, action, "user", user.id, now=now, actor_name=user.login)
                error = LOCKED if locked_until else INVALID_CREDENTIALS
            elif not user.active:
                error = INACTIVE
            else:
                users_repo.set_login_state(conn, user.id, failed_attempts=0, locked_until=None)
                token = new_token()
                sessions_repo.insert(conn, token_hash(token), user.id, now=now, expires=now + SESSION_DURATION)
                audit.record(conn, user, "login", "user", user.id, now=now)
                result = LoginResult(token, users_repo.get(conn, user.id))
    # o erro sai depois do commit: a contagem de tentativas erradas precisa ficar gravada
    if error:
        raise AuthError(error)
    return result


def user_for_token(conn: sqlite3.Connection, token: str, *, now: datetime | None = None) -> User | None:
    user_id = sessions_repo.user_id_for(conn, token_hash(token), now or utcnow())
    if user_id is None:
        return None
    user = users_repo.get(conn, user_id)
    return user if user and user.active else None


def logout(conn: sqlite3.Connection, token: str) -> None:
    with transaction(conn):
        sessions_repo.delete(conn, token_hash(token))


def change_password(
    conn: sqlite3.Connection,
    actor: User | None,
    token: str,
    current: str,
    new: str,
    confirmation: str,
    *,
    now: datetime | None = None,
) -> None:
    """Troca a própria senha. Encerra as outras sessões do usuário (fica só a atual)."""
    user = require_user(actor)
    if new != confirmation:
        raise ValidationError("A confirmação não é igual à nova senha.")
    validate_password(new, user.login)
    if new == current:
        raise ValidationError("A nova senha precisa ser diferente da atual.")
    with transaction(conn):
        stored = users_repo.get_password_hash(conn, user.id)
        if stored is None or not verify_password(current, stored):
            raise ValidationError("A senha atual está errada.")
        users_repo.set_password(conn, user.id, hash_password(new), must_change=False)
        sessions_repo.delete_for_user(conn, user.id, keep=token_hash(token))
        audit.record(conn, user, "password_change", "user", user.id, now=now)
