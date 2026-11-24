import pytest

from apontarhoras.storage.db import Database, available_migrations, migrate, transaction


def test_migrations_apply_once(db, conn):
    latest = available_migrations()[-1][0]
    assert conn.execute("PRAGMA user_version").fetchone()[0] == latest
    assert migrate(conn) == latest  # rodar de novo não faz nada
    db.initialize()


def test_refuses_newer_database(conn):
    conn.execute("PRAGMA user_version = 999")
    with pytest.raises(RuntimeError, match="versão mais nova"):
        migrate(conn)


def test_transaction_rolls_back(conn):
    with pytest.raises(ValueError), transaction(conn):
        conn.execute(
            "INSERT INTO projects (code, name, created_at) VALUES ('X', 'Projeto X', '2026-11-23T00:00:00+00:00')"
        )
        raise ValueError
    assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0


def test_wal_mode(tmp_path):
    database = Database(tmp_path / "novo" / "a.db")
    database.initialize()
    conn = database.connect()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()
