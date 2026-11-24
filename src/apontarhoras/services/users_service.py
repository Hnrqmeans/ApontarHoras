"""Cadastro de usuários (só o responsável)."""

import sqlite3
from datetime import datetime

from apontarhoras.auth.passwords import hash_password
from apontarhoras.domain.audit import changes
from apontarhoras.domain.errors import NotFound, ValidationError
from apontarhoras.domain.user import (
    Role,
    User,
    normalize_login,
    normalize_name,
    parse_role,
    validate_login,
    validate_name,
    validate_password,
)
from apontarhoras.services import audit
from apontarhoras.services.common import require_admin, utcnow
from apontarhoras.storage import sessions_repo, time_entries_repo, users_repo
from apontarhoras.storage.db import transaction


def _snapshot(user: User) -> dict:
    return {"nome": user.name, "login": user.login, "papel": user.role.label, "ativo": user.active}


def _get(conn: sqlite3.Connection, user_id: int) -> User:
    user = users_repo.get(conn, user_id)
    if user is None:
        raise NotFound("Usuário não encontrado.")
    return user


def list_users(conn: sqlite3.Connection, actor: User | None) -> list[User]:
    require_admin(actor)
    return users_repo.list_all(conn)


def get_user(conn: sqlite3.Connection, actor: User | None, user_id: int) -> User:
    require_admin(actor)
    return _get(conn, user_id)


def create_user(
    conn: sqlite3.Connection,
    actor: User | None,
    *,
    name: str,
    login: str,
    role: str,
    temporary_password: str,
    now: datetime | None = None,
) -> User:
    """Cria com senha temporária: a pessoa é obrigada a trocar no primeiro acesso."""
    admin = require_admin(actor)
    name, login, parsed_role = normalize_name(name), normalize_login(login), parse_role(role)
    validate_name(name)
    validate_login(login)
    validate_password(temporary_password, login)
    with transaction(conn):
        if users_repo.login_taken(conn, login):
            raise ValidationError(f"Já existe um usuário com o login '{login}'.")
        user_id = users_repo.insert(
            conn,
            name=name,
            login=login,
            password_hash=hash_password(temporary_password),
            role=parsed_role,
            must_change_password=True,
            now=now or utcnow(),
        )
        user = users_repo.get(conn, user_id)
        audit.record(conn, admin, "create", "user", user_id, _snapshot(user), now=now)
    return user


def _ensure_admin_remains(conn: sqlite3.Connection, target: User, *, still_admin: bool) -> None:
    if target.is_admin and not still_admin and users_repo.count_active_admins(conn) <= 1:
        raise ValidationError("É preciso ter pelo menos um responsável ativo.")


def update_user(
    conn: sqlite3.Connection,
    actor: User | None,
    user_id: int,
    *,
    name: str,
    role: str,
    active: bool,
    now: datetime | None = None,
) -> User:
    admin = require_admin(actor)
    name, parsed_role = normalize_name(name), parse_role(role)
    validate_name(name)
    if user_id == admin.id and (parsed_role is not Role.ADMIN or not active):
        raise ValidationError("Você não pode tirar o seu próprio acesso de responsável nem se desativar.")
    with transaction(conn):
        before = _get(conn, user_id)
        _ensure_admin_remains(conn, before, still_admin=active and parsed_role is Role.ADMIN)
        users_repo.update_profile(conn, user_id, name=name, role=parsed_role, active=active)
        if not active:
            sessions_repo.delete_for_user(conn, user_id)
        after = users_repo.get(conn, user_id)
        diff = changes(_snapshot(before), _snapshot(after))
        if diff:
            audit.record(conn, admin, "update", "user", user_id, diff, now=now)
    return after


def reset_password(
    conn: sqlite3.Connection,
    actor: User | None,
    user_id: int,
    temporary_password: str,
    *,
    now: datetime | None = None,
) -> None:
    """Senha temporária para quem esqueceu: desbloqueia, encerra sessões e obriga a trocar no próximo acesso."""
    admin = require_admin(actor)
    with transaction(conn):
        target = _get(conn, user_id)
        validate_password(temporary_password, target.login)
        users_repo.set_password(conn, user_id, hash_password(temporary_password), must_change=True)
        sessions_repo.delete_for_user(conn, user_id)
        audit.record(conn, admin, "password_reset", "user", user_id, {"login": target.login}, now=now)


def delete_user(conn: sqlite3.Connection, actor: User | None, user_id: int, *, now: datetime | None = None) -> None:
    admin = require_admin(actor)
    if user_id == admin.id:
        raise ValidationError("Você não pode excluir o seu próprio usuário.")
    with transaction(conn):
        target = _get(conn, user_id)
        _ensure_admin_remains(conn, target, still_admin=False)
        if time_entries_repo.count_by(conn, "user_id", user_id):
            raise ValidationError("Este colaborador tem horas apontadas: desative-o em vez de excluir.")
        users_repo.delete(conn, user_id)
        audit.record(conn, admin, "delete", "user", user_id, _snapshot(target), now=now)
