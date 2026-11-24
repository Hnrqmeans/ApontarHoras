"""Duração de trabalho: sempre em minutos inteiros (nunca float de horas)."""

import re
from decimal import Decimal

from apontarhoras.domain.errors import ValidationError

MAX_ENTRY_MINUTES = 24 * 60

_HOURS_MINUTES = re.compile(r"^(\d{1,3})(?:[:h](\d{2})?)?$")
_DECIMAL_HOURS = re.compile(r"^(\d{1,3})[.,](\d{1,2})$")


def format_minutes(minutes: int) -> str:
    """480 → "8:00"; 1530 → "25:30"; -90 → "-1:30"."""
    sign = "-" if minutes < 0 else ""
    hours, rest = divmod(abs(minutes), 60)
    return f"{sign}{hours}:{rest:02d}"


def parse_duration(text: str) -> int:
    """Aceita "8", "8:30", "8h", "8h30", "8,5" ou "8.5" e devolve minutos."""
    raw = text.strip().lower().replace(" ", "")
    if not raw:
        raise ValidationError("Informe a duração.")
    decimal_match = _DECIMAL_HOURS.match(raw)
    if decimal_match:
        minutes = Decimal(f"{decimal_match.group(1)}.{decimal_match.group(2)}") * 60
        if minutes != minutes.to_integral_value():
            raise ValidationError(f"Duração '{text}' não dá minutos inteiros. Use horas:minutos (ex.: 1:20).")
        total = int(minutes)
    else:
        match = _HOURS_MINUTES.match(raw)
        if not match:
            raise ValidationError(f"Duração inválida: '{text}'. Use 8, 8:30 ou 8,5.")
        rest = int(match.group(2) or 0)
        if rest >= 60:
            raise ValidationError("Os minutos vão de 00 a 59.")
        total = int(match.group(1)) * 60 + rest
    if total <= 0:
        raise ValidationError("A duração precisa ser maior que zero.")
    if total > MAX_ENTRY_MINUTES:
        raise ValidationError("A duração não pode passar de 24 horas.")
    return total
