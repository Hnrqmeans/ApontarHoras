"""Conexão, transação e migrações.

Servidor com várias pessoas ao mesmo tempo: uma conexão por requisição, modo WAL (leitura não espera escrita) e
`BEGIN IMMEDIATE` nas escritas (quem chega depois espera, em vez de falhar no meio).
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from importlib import resources
from pathlib import Path


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def initialize(self) -> None:
        """Cria a pasta/arquivo se preciso, aplica as migrações pendentes e sela a auditoria antiga (sem selo)."""
        # import aqui: audit_repo usa este módulo (transaction, datas)
        from apontarhoras.storage.audit_repo import seal_pending

        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = self.connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            migrate(conn)
            seal_pending(conn)
        finally:
            conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Tudo ou nada. Dentro de outra transação, apenas participa dela."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def available_migrations() -> list[tuple[int, str]]:
    folder = resources.files("apontarhoras.storage") / "migrations"
    found = []
    for entry in folder.iterdir():
        if entry.name.endswith(".sql"):
            found.append((int(entry.name.split("_", 1)[0]), entry.read_text(encoding="utf-8")))
    return sorted(found)


def migrate(conn: sqlite3.Connection) -> int:
    """Aplica as migrações novas (cada uma na sua transação). Devolve a versão final."""
    migrations = available_migrations()
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    latest = migrations[-1][0] if migrations else 0
    if current > latest:
        raise RuntimeError(
            f"O banco de dados é de uma versão mais nova do ApontarHoras (estrutura {current}; este programa "
            f"conhece até {latest}). Atualize o programa."
        )
    for version, sql in migrations:
        if version <= current:
            continue
        try:
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        current = version
    return current


def to_db_time(moment: datetime) -> str:
    """Data-hora em UTC, ISO (ordena certo como texto)."""
    return moment.isoformat(timespec="seconds")


def from_db_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
