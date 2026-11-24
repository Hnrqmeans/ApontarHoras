"""Feriados: dias sem jornada esperada (não viram pendência em "Meus apontamentos").

Feriados nacionais oferecidos pelo botão "Adicionar feriados nacionais": os fixos da lei federal + Sexta-feira
Santa (data móvel, pela Páscoa). Carnaval e Corpus Christi são **ponto facultativo** (não são feriado nacional):
não entram automaticamente; o responsável os cadastra à mão se a empresa folgar. Feriados estaduais/municipais
também são cadastrados à mão.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from apontarhoras.domain.errors import ValidationError

MIN_YEAR = 2000
MAX_YEAR = 2100

# (mês, dia, descrição) — Lei 662/1949, Lei 6.802/1980 (Aparecida), Lei 14.759/2023 (Consciência Negra)
FIXED_NATIONAL_HOLIDAYS = (
    (1, 1, "Confraternização Universal"),
    (4, 21, "Tiradentes"),
    (5, 1, "Dia do Trabalho"),
    (9, 7, "Independência do Brasil"),
    (10, 12, "Nossa Senhora Aparecida"),
    (11, 2, "Finados"),
    (11, 15, "Proclamação da República"),
    (11, 20, "Dia Nacional de Zumbi e da Consciência Negra"),
    (12, 25, "Natal"),
)
CONSCIENCIA_NEGRA_SINCE = 2024  # feriado nacional a partir da Lei 14.759/2023


@dataclass(frozen=True)
class Holiday:
    id: int
    day: date
    description: str
    created_at: datetime


def normalize_description(raw: str) -> str:
    return " ".join(raw.split())


def validate_description(description: str) -> None:
    if not 2 <= len(description) <= 80:
        raise ValidationError("A descrição do feriado deve ter de 2 a 80 caracteres.")


def parse_day(raw: str) -> date:
    """Data do formulário (AAAA-MM-DD, como o navegador envia)."""
    try:
        day = date.fromisoformat(raw.strip())
    except ValueError:
        raise ValidationError("Informe uma data válida.") from None
    validate_year(day.year)
    return day


def validate_year(year: int) -> None:
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValidationError(f"O ano deve estar entre {MIN_YEAR} e {MAX_YEAR}.")


def easter(year: int) -> date:
    """Domingo de Páscoa (calendário gregoriano) pelo algoritmo de Meeus/Jones/Butcher."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 (nome do algoritmo original)
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def national_holidays(year: int) -> list[tuple[date, str]]:
    """Feriados nacionais do ano, em ordem de data (sem os pontos facultativos)."""
    validate_year(year)
    days = [
        (date(year, month, day), description)
        for month, day, description in FIXED_NATIONAL_HOLIDAYS
        if not (month == 11 and day == 20 and year < CONSCIENCIA_NEGRA_SINCE)
    ]
    days.append((easter(year) - timedelta(days=2), "Sexta-feira Santa"))
    return sorted(days)
