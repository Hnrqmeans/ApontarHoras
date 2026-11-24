"""Tarefa (tipo de atividade): define se as horas contam para a Lei do Bem."""

from dataclasses import dataclass
from datetime import datetime

from apontarhoras.domain.errors import ValidationError


@dataclass(frozen=True)
class Task:
    id: int
    name: str
    rd_eligible: bool  # horas desta tarefa contam para a Lei do Bem ("Grau P&D" da planilha antiga)
    active: bool
    created_at: datetime


def validate_name(name: str) -> None:
    if not 2 <= len(name) <= 60:
        raise ValidationError("O nome da tarefa deve ter de 2 a 60 caracteres.")
