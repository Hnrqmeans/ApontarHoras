"""Apontamento: horário de início/término, almoço, duração e regras de validação.

Horários são guardados como minutos desde 00:00 (int). Regras vindas da planilha antiga (VBA do formulário de
apontamento), com os mesmos limites.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from apontarhoras.domain.errors import ValidationError

LUNCH_START = 12 * 60
LUNCH_END = 13 * 60
LUNCH_BREAK_MINUTES = 60
MAX_DESCRIPTION = 1000
MIN_REASON = 3
MAX_REASON = 500

_DIGITS = re.compile(r"^\d+$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")


class LunchChoice(StrEnum):
    """Resposta do colaborador quando o período passa pelo almoço (12:00–13:00)."""

    NOT_ASKED = ""
    DEDUCT = "descontar"
    NO_BREAK = "sem_intervalo"

    @property
    def label(self) -> str:
        return {
            LunchChoice.NOT_ASKED: "Não passa pelo almoço",
            LunchChoice.DEDUCT: "Descontar 1 h de almoço",
            LunchChoice.NO_BREAK: "Trabalhei sem intervalo",
        }[self]


@dataclass(frozen=True)
class TimeEntry:
    id: int
    user_id: int
    user_name: str
    work_date: date
    project_id: int
    project_code: str
    project_name: str
    task_id: int
    task_name: str
    start_minute: int
    end_minute: int
    break_minutes: int
    minutes: int
    rd_eligible: bool  # retrato no momento do apontamento (não muda se o cadastro mudar depois)
    description: str
    created_at: datetime
    updated_at: datetime


def parse_clock(text: str) -> int:
    """Horário digitado → minutos desde 00:00. Aceita 7 | 07 | 730 | 0730 | 7:30 | 07:30 | 7: | 7h30."""
    raw = text.strip().lower().replace("h", ":")
    if not raw:
        raise ValidationError("Informe o horário.")
    if ":" in raw:
        parts = raw.split(":")
        if len(parts) != 2:
            raise ValidationError(f"Horário inválido: '{text}'. Use 07:30.")
        hours_text, minutes_text = parts[0], parts[1] or "0"
        if not _DIGITS.match(hours_text) or not _DIGITS.match(minutes_text) or len(minutes_text) > 2:
            raise ValidationError(f"Horário inválido: '{text}'. Use 07:30.")
    else:
        if not _DIGITS.match(raw) or len(raw) > 4:
            raise ValidationError(f"Horário inválido: '{text}'. Use 07:30.")
        hours_text, minutes_text = (raw, "0") if len(raw) <= 2 else (raw[:-2], raw[-2:])
    hours, minutes = int(hours_text), int(minutes_text)
    if hours > 23 or minutes > 59:
        raise ValidationError(f"Horário inválido: '{text}'. Vai de 00:00 a 23:59.")
    return hours * 60 + minutes


def format_clock(minute_of_day: int) -> str:
    """450 → "07:30"."""
    hours, minutes = divmod(minute_of_day, 60)
    return f"{hours:02d}:{minutes:02d}"


def spans_lunch(start: int, end: int) -> bool:
    """Começa antes das 12:00 e termina depois das 13:00: certamente passou pelo almoço."""
    return start < LUNCH_START and end > LUNCH_END


def compute_minutes(start: int, end: int, lunch: LunchChoice) -> tuple[int, int]:
    """Valida o período e devolve (intervalo descontado, minutos trabalhados)."""
    if end <= start:
        raise ValidationError("O horário de término deve ser maior que o de início.")
    if spans_lunch(start, end):
        if lunch is LunchChoice.NOT_ASKED:
            raise ValidationError(
                f"O período {format_clock(start)} às {format_clock(end)} passa pelo horário de almoço: "
                "escolha se desconta 1 h ou se trabalhou sem intervalo."
            )
        break_minutes = LUNCH_BREAK_MINUTES if lunch is LunchChoice.DEDUCT else 0
    else:
        break_minutes = 0
    return break_minutes, end - start - break_minutes


def parse_lunch(value: str) -> LunchChoice:
    try:
        return LunchChoice(value)
    except ValueError:
        raise ValidationError("Opção de almoço inválida.") from None


def parse_work_date(text: str, today: date) -> date:
    try:
        work_date = date.fromisoformat(text.strip())
    except ValueError:
        raise ValidationError("Data inválida.") from None
    if work_date > today:
        raise ValidationError("Não é permitido apontar em data futura.")
    return work_date


def validate_description(description: str, *, rd_eligible: bool) -> None:
    if len(description) > MAX_DESCRIPTION:
        raise ValidationError(f"A descrição deve ter no máximo {MAX_DESCRIPTION} caracteres.")
    if rd_eligible and not description:
        raise ValidationError("Descreva brevemente a atividade executada (obrigatório para horas da Lei do Bem).")


def overlaps(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and end > other_start


def parse_month(text: str | None, today: date) -> tuple[int, int]:
    """ "2026-11" → (2026, 11); vazio ou inválido → mês de hoje."""
    match = _MONTH.match((text or "").strip())
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 2000 <= year <= 2100 and 1 <= month <= 12:
            return year, month
    return today.year, today.month


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def is_late_entry(work_date: date, created_local: date) -> bool:
    """Lançado depois do fim do mês da data trabalhada (data local do lançamento). O mês não trava (D9): só sinaliza."""
    return (created_local.year, created_local.month) > (work_date.year, work_date.month)


def validate_correction_reason(reason: str) -> str:
    """Motivo de quem corrige/exclui o apontamento de outra pessoa (vai para a auditoria). Devolve o texto limpo."""
    text = reason.replace("\r", "").strip()
    if len(text) < MIN_REASON:
        raise ValidationError("Informe o motivo da correção (quem altera o apontamento de outra pessoa).")
    if len(text) > MAX_REASON:
        raise ValidationError(f"O motivo deve ter no máximo {MAX_REASON} caracteres.")
    return text
