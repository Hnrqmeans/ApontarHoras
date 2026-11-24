"""Configuração: onde ficam os dados, endereço e porta."""

import os
from dataclasses import dataclass
from pathlib import Path

from apontarhoras.domain.workday import DEFAULT_SCHEDULE

DATA_ENV = "APONTARHORAS_DADOS"
DB_FILENAME = "apontarhoras.db"


def default_data_dir() -> Path:
    """Variável APONTARHORAS_DADOS, senão %LOCALAPPDATA%\\ApontarHoras (ou ~/.apontarhoras fora do Windows)."""
    if os.environ.get(DATA_ENV):
        return Path(os.environ[DATA_ENV])
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "ApontarHoras" if local else Path.home() / ".apontarhoras"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8080
    secure_cookies: bool = False
    schedule: tuple[int, ...] = DEFAULT_SCHEDULE  # jornada seg … dom, em minutos

    @property
    def db_path(self) -> Path:
        return self.data_dir / DB_FILENAME
