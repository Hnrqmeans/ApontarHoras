"""Fixtures comuns. Dados sempre fictícios."""

import sqlite3

import pytest

from apontarhoras.domain.user import User
from apontarhoras.services import auth_service, users_service
from apontarhoras.storage.db import Database

ADMIN_PASSWORD = "senha-do-admin-1"
TEMP_PASSWORD = "temporaria-123"


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(tmp_path / "dados" / "teste.db")
    database.initialize()
    return database


@pytest.fixture
def conn(db) -> sqlite3.Connection:
    connection = db.connect()
    yield connection
    connection.close()


@pytest.fixture
def admin(conn) -> User:
    return auth_service.setup_first_admin(conn, "Ana Responsável", "ana", ADMIN_PASSWORD)


@pytest.fixture
def collaborator(conn, admin) -> User:
    return users_service.create_user(
        conn, admin, name="Bruno Colaborador", login="bruno", role="colaborador", temporary_password=TEMP_PASSWORD
    )
