"""Projeto de P&D onde as horas são apontadas."""

import re
from dataclasses import dataclass
from datetime import datetime

from apontarhoras.domain.errors import ValidationError

_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,19}$")


@dataclass(frozen=True)
class Project:
    id: int
    code: str
    name: str
    description: str
    active: bool
    rd_eligible: bool  # projeto de P&D (Lei do Bem); "tarefas internas" = não elegível
    created_at: datetime


def normalize_code(raw: str) -> str:
    return raw.strip().upper()


def validate_code(code: str) -> None:
    if not _CODE_RE.match(code):
        raise ValidationError(
            "O código deve ter de 1 a 20 caracteres: letras sem acento, números, ponto, hífen ou sublinhado."
        )


def normalize_text(raw: str) -> str:
    return " ".join(raw.split())


def validate_name(name: str) -> None:
    if not 2 <= len(name) <= 120:
        raise ValidationError("O nome do projeto deve ter de 2 a 120 caracteres.")


def validate_description(description: str) -> None:
    if len(description) > 2000:
        raise ValidationError("A descrição deve ter no máximo 2000 caracteres.")
