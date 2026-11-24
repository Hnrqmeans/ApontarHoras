"""Jornada esperada por dia e situação do dia (base da conferência de lacunas).

A jornada é da empresa, não do código: vem do `ApontarHoras.ini` (`jornada = ...`) e é aplicada na partida com
`configure_schedule`. Sem configuração vale o padrão genérico: 8:00 de segunda a sexta.
"""

import re
from datetime import date
from enum import StrEnum

from apontarhoras.domain.errors import ValidationError

DEFAULT_SCHEDULE = (480, 480, 480, 480, 480, 0, 0)  # índice = date.weekday() (0 = segunda)
WEEKDAY_NAMES = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
MAX_DAY_MINUTES = 24 * 60

_CLOCK = re.compile(r"^(\d{1,2})(?::(\d{2}))?$")

_schedule: tuple[int, ...] = DEFAULT_SCHEDULE


class DayStatus(StrEnum):
    OK = "ok"
    MISSING = "pendencia"  # apontou menos que a jornada
    EXCESS = "verificar"  # apontou mais que a jornada (hora extra ou erro de digitação)
    NOT_WORKDAY = "nao_util"

    @property
    def label(self) -> str:
        return {
            DayStatus.OK: "OK",
            DayStatus.MISSING: "Pendência",
            DayStatus.EXCESS: "Verificar",
            DayStatus.NOT_WORKDAY: "—",
        }[self]


def parse_schedule(text: str) -> tuple[int, ...]:
    """ "8:00, 8:00, 8:00, 8:00, 8:00, 0, 0" (seg … dom) → minutos por dia da semana."""
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 7:
        raise ValidationError(
            "jornada: informe 7 valores, de segunda a domingo (ex.: 8:00, 8:00, 8:00, 8:00, 8:00, 0, 0)."
        )
    minutes = []
    for name, part in zip(WEEKDAY_NAMES, parts, strict=True):
        match = _CLOCK.match(part)
        if not match or int(match.group(2) or 0) > 59:
            raise ValidationError(f"jornada: valor inválido para {name}: '{part}' (use H:MM, ex.: 8:00, ou 0).")
        total = int(match.group(1)) * 60 + int(match.group(2) or 0)
        if total > MAX_DAY_MINUTES:
            raise ValidationError(f"jornada: {name} passa de 24 horas.")
        minutes.append(total)
    return tuple(minutes)


def configure_schedule(schedule: tuple[int, ...]) -> None:
    """Aplicada uma vez na partida do servidor (vem do .ini)."""
    global _schedule
    if len(schedule) != 7:
        raise ValueError("A jornada tem 7 dias (segunda a domingo).")
    _schedule = tuple(schedule)


def current_schedule() -> tuple[int, ...]:
    return _schedule


def schedule_text(schedule: tuple[int, ...] | None = None) -> str:
    """Resumo legível: dias seguidos com a mesma jornada viram faixa (ex.: "seg–sex 8:00")."""
    schedule = schedule or _schedule
    groups: list[tuple[int, int, int]] = []  # (primeiro dia, último dia, minutos)
    for index, minutes in enumerate(schedule):
        if minutes == 0:
            continue
        if groups and groups[-1][1] == index - 1 and groups[-1][2] == minutes:
            groups[-1] = (groups[-1][0], index, minutes)
        else:
            groups.append((index, index, minutes))
    if not groups:
        return "sem jornada configurada"
    parts = []
    for first, last, minutes in groups:
        days = WEEKDAY_NAMES[first] if first == last else f"{WEEKDAY_NAMES[first]}–{WEEKDAY_NAMES[last]}"
        parts.append(f"{days} {minutes // 60}:{minutes % 60:02d}")
    return ", ".join(parts)


def expected_minutes(day: date, holidays: frozenset[date] | set[date] = frozenset()) -> int:
    """Minutos esperados no dia; feriado (cadastrado pelo responsável) não tem jornada."""
    if day in holidays:
        return 0
    return _schedule[day.weekday()]


def day_status(worked: int, expected: int) -> DayStatus:
    """Dia não útil com horas apontadas não é erro: aparece só como informação."""
    if expected == 0:
        return DayStatus.NOT_WORKDAY
    if worked < expected:
        return DayStatus.MISSING
    if worked > expected:
        return DayStatus.EXCESS
    return DayStatus.OK
