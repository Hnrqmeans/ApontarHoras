"""Jornada esperada por dia e situação do dia (base da conferência de lacunas)."""

from datetime import date
from enum import StrEnum

# Jornada da empresa (planilha antiga, tela "Inconsistências"): seg–qui 8h27, sex 7h42, fim de semana não conta.
EXPECTED_MINUTES_BY_WEEKDAY = (507, 507, 507, 507, 462, 0, 0)  # índice = date.weekday() (0 = segunda)


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


def expected_minutes(day: date) -> int:
    return EXPECTED_MINUTES_BY_WEEKDAY[day.weekday()]


def day_status(worked: int, expected: int) -> DayStatus:
    """Dia não útil com horas apontadas não é erro: aparece só como informação."""
    if expected == 0:
        return DayStatus.NOT_WORKDAY
    if worked < expected:
        return DayStatus.MISSING
    if worked > expected:
        return DayStatus.EXCESS
    return DayStatus.OK
