"""Cadastro de feriados (só o responsável). Feriado não tem jornada esperada: não vira pendência."""

import sqlite3
from datetime import date, datetime

from apontarhoras.domain.errors import NotFound, ValidationError
from apontarhoras.domain.holiday import (
    Holiday,
    national_holidays,
    normalize_description,
    parse_day,
    validate_description,
    validate_year,
)
from apontarhoras.domain.user import User
from apontarhoras.services import audit
from apontarhoras.services.common import require_admin, utcnow
from apontarhoras.storage import holidays_repo
from apontarhoras.storage.db import transaction


def _snapshot(holiday: Holiday) -> dict:
    return {"data": holiday.day.isoformat(), "descrição": holiday.description}


def _insert(conn: sqlite3.Connection, admin: User, day: date, description: str, now: datetime | None) -> Holiday:
    holiday_id = holidays_repo.insert(conn, day=day, description=description, now=now or utcnow())
    holiday = holidays_repo.get(conn, holiday_id)
    audit.record(conn, admin, "create", "holiday", holiday_id, _snapshot(holiday), now=now)
    return holiday


def holidays_in(conn: sqlite3.Connection, first: date, last: date) -> dict[date, str]:
    """Feriados do intervalo → descrição. Sem checagem de papel: só alimenta o resumo do mês de cada usuário."""
    return {holiday.day: holiday.description for holiday in holidays_repo.list_between(conn, first, last)}


def list_year(conn: sqlite3.Connection, actor: User | None, year: int) -> list[Holiday]:
    require_admin(actor)
    validate_year(year)
    return holidays_repo.list_between(conn, date(year, 1, 1), date(year, 12, 31))


def get_holiday(conn: sqlite3.Connection, actor: User | None, holiday_id: int) -> Holiday:
    require_admin(actor)
    holiday = holidays_repo.get(conn, holiday_id)
    if holiday is None:
        raise NotFound("Feriado não encontrado.")
    return holiday


def add_holiday(
    conn: sqlite3.Connection, actor: User | None, *, day: str, description: str, now: datetime | None = None
) -> Holiday:
    admin = require_admin(actor)
    parsed = parse_day(day)
    description = normalize_description(description)
    validate_description(description)
    with transaction(conn):
        if holidays_repo.day_taken(conn, parsed):
            raise ValidationError(f"Já existe um feriado em {parsed.strftime('%d/%m/%Y')}.")
        return _insert(conn, admin, parsed, description, now)


def add_national_holidays(
    conn: sqlite3.Connection, actor: User | None, year: int, *, now: datetime | None = None
) -> list[Holiday]:
    """Cadastra os feriados nacionais do ano que ainda faltam (data já cadastrada fica como está)."""
    admin = require_admin(actor)
    days = national_holidays(year)
    with transaction(conn):
        return [
            _insert(conn, admin, day, description, now)
            for day, description in days
            if not holidays_repo.day_taken(conn, day)
        ]


def delete_holiday(
    conn: sqlite3.Connection, actor: User | None, holiday_id: int, *, now: datetime | None = None
) -> None:
    admin = require_admin(actor)
    with transaction(conn):
        holiday = get_holiday(conn, admin, holiday_id)
        holidays_repo.delete(conn, holiday_id)
        audit.record(conn, admin, "delete", "holiday", holiday_id, _snapshot(holiday), now=now)
