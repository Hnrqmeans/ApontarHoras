"""Relatório do responsável: filtros, totais, selo (SHA-256) e conferência do mês. Regras puras, sem I/O.

Selo = SHA-256 de uma forma canônica (JSON compacto, ordem fixa) do conteúdo. Mudou um caractere → muda o selo.
- Selo do mês (conferência): usa os ids e valores gravados (renomear colaborador/projeto não muda o selo).
- Selo da exportação: usa o que aparece no relatório (nomes, códigos, filtros), igual no Excel e na impressão.
"""

import calendar
import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from apontarhoras.domain.errors import ValidationError
from apontarhoras.domain.time_entry import TimeEntry, format_clock

MAX_PERIOD_DAYS = 366
BAR_STEP_PERCENT = 5  # barras do painel em degraus de 5% (classes .w-0 … .w-100 no style.css)
SEAL_SHORT_HEX = 16


class ReportKind(StrEnum):
    """Filtro "tipo" do relatório."""

    ALL = ""
    RD = "lei"
    OTHER = "nao"

    @property
    def label(self) -> str:
        return {ReportKind.ALL: "Todos", ReportKind.RD: "Lei do Bem", ReportKind.OTHER: "Não elegível"}[self]


@dataclass(frozen=True)
class ReportFilters:
    start: date
    end: date
    user_id: int | None = None
    project_id: int | None = None
    task_id: int | None = None
    kind: ReportKind = ReportKind.ALL

    @property
    def rd_eligible(self) -> bool | None:
        """None = todos; True = só Lei do Bem; False = só não elegíveis."""
        return {ReportKind.ALL: None, ReportKind.RD: True, ReportKind.OTHER: False}[self.kind]

    def query(self) -> dict[str, str]:
        """Os mesmos nomes de campo do formulário (para montar links de exportação)."""
        return {
            "inicio": self.start.isoformat(),
            "fim": self.end.isoformat(),
            "colaborador": str(self.user_id or ""),
            "projeto": str(self.project_id or ""),
            "tarefa": str(self.task_id or ""),
            "tipo": self.kind.value,
        }

    def filename(self, extension: str) -> str:
        return f"apontamentos_{self.start.isoformat()}_{self.end.isoformat()}.{extension}"


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _parse_date(text: str, label: str) -> date:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise ValidationError(f"{label} inválida. Use o seletor de data.") from None


def _parse_optional_id(text: str | None, label: str) -> int | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise ValidationError(f"{label} inválido.")
    return int(raw)


def parse_report_filters(query: Mapping[str, str], today: date) -> ReportFilters:
    """Campos do formulário (GET) → filtros. Período padrão = mês de hoje; no máximo 366 dias."""
    default_start, default_end = month_bounds(today.year, today.month)
    start_text = (query.get("inicio") or "").strip()
    end_text = (query.get("fim") or "").strip()
    start = _parse_date(start_text, "Data inicial") if start_text else default_start
    end = _parse_date(end_text, "Data final") if end_text else default_end
    if end < start:
        raise ValidationError("A data final deve ser igual ou posterior à data inicial.")
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        raise ValidationError(f"O período pode ter no máximo {MAX_PERIOD_DAYS} dias.")
    try:
        kind = ReportKind((query.get("tipo") or "").strip())
    except ValueError:
        raise ValidationError("Tipo inválido.") from None
    return ReportFilters(
        start=start,
        end=end,
        user_id=_parse_optional_id(query.get("colaborador"), "Colaborador"),
        project_id=_parse_optional_id(query.get("projeto"), "Projeto"),
        task_id=_parse_optional_id(query.get("tarefa"), "Tarefa"),
        kind=kind,
    )


# ---- totais --------------------------------------------------------------------------------------------------


def share_percent(part: int, total: int) -> int:
    """Percentual inteiro (para baixo), como em "Meus apontamentos"."""
    return part * 100 // total if total else 0


def group_minutes(entries: Iterable[TimeEntry], key: Callable[[TimeEntry], str]) -> list[tuple[str, int]]:
    """Minutos por grupo, do maior para o menor (empate: ordem alfabética)."""
    totals: dict[str, int] = {}
    for entry in entries:
        label = key(entry)
        totals[label] = totals.get(label, 0) + entry.minutes
    return sorted(totals.items(), key=lambda item: (-item[1], item[0].casefold()))


def bar_step(value: int, maximum: int) -> int:
    """Largura da barra em % (múltiplo de 5). Valor positivo nunca some (mínimo um degrau)."""
    if value <= 0 or maximum <= 0:
        return 0
    steps = 100 // BAR_STEP_PERCENT
    step = round(value * steps / maximum)
    return max(1, min(steps, step)) * BAR_STEP_PERCENT


def decimal_hours(minutes: int) -> Decimal:
    """510 → Decimal("8.50"): horas com 2 casas para a planilha (sem float)."""
    return (Decimal(minutes) / Decimal(60)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---- selo ----------------------------------------------------------------------------------------------------


def _sha256(content: object) -> str:
    canonical = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def month_seal(entries: Iterable[TimeEntry]) -> str:
    """Selo dos apontamentos de um mês (todos os colaboradores), na ordem dos ids."""
    rows = [
        [entry.id, entry.user_id, entry.work_date.isoformat(), entry.project_id, entry.task_id, entry.start_minute,
         entry.end_minute, entry.break_minutes, entry.minutes, int(entry.rd_eligible), entry.description]
        for entry in sorted(entries, key=lambda item: item.id)
    ]
    return _sha256(rows)


def export_row(entry: TimeEntry) -> list:
    """Uma linha do relatório: Data, Colaborador, Projeto, Tarefa, Início, Término, Minutos, Lei do Bem, Descrição."""
    return [entry.work_date.isoformat(), entry.user_name, entry.project_code, entry.task_name,
            format_clock(entry.start_minute), format_clock(entry.end_minute), entry.minutes,
            "Sim" if entry.rd_eligible else "Não", entry.description]


def export_seal(filter_labels: Iterable[tuple[str, str]], entries: Iterable[TimeEntry]) -> str:
    """Selo do conteúdo exportado: filtros + linhas, na ordem do relatório."""
    return _sha256({"filtros": [list(item) for item in filter_labels], "linhas": [export_row(e) for e in entries]})


def format_seal(seal: str) -> str:
    """Primeiros 16 hex em grupos de 4: "a1b2 c3d4 e5f6 a7b8"."""
    short = seal[:SEAL_SHORT_HEX]
    return " ".join(short[i:i + 4] for i in range(0, len(short), 4))


# ---- conferência do mês --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MonthReview:
    id: int
    year: int
    month: int
    reviewer_name: str
    reviewed_at: datetime
    entry_count: int
    total_minutes: int
    seal: str


@dataclass(frozen=True)
class MonthReviewStatus:
    """Situação de um mês: última conferência (se houver) × apontamentos de agora."""

    year: int
    month: int
    review: MonthReview | None
    entry_count: int
    total_minutes: int
    seal: str

    @property
    def changed(self) -> bool:
        """O conteúdo do mês mudou desde a conferência (inclusão, correção ou exclusão)."""
        if self.review is None:
            return False
        return (self.seal, self.entry_count, self.total_minutes) != (
            self.review.seal, self.review.entry_count, self.review.total_minutes
        )


def changed_after_review(entry: TimeEntry, review: MonthReview | None) -> bool:
    """Criado ou alterado depois da última conferência do mês (`updated_at` ≥ `created_at`)."""
    return review is not None and entry.updated_at > review.reviewed_at


def months_in(start: date, end: date) -> list[tuple[int, int]]:
    """Meses (ano, mês) que o período toca, em ordem."""
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months
