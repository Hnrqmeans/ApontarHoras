"""Importar projetos colando a lista da planilha atual (uma linha por projeto).

Formato aceito: `CÓDIGO - Cliente - Nome do projeto` (o primeiro pedaço é o código; o resto, o nome) ou
`CÓDIGO - Nome`. Linhas copiadas do Excel com várias colunas chegam separadas por TAB e valem igual.
Puro: quem chama informa os códigos que já existem no banco.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from apontarhoras.domain.errors import ValidationError
from apontarhoras.domain.project import normalize_code, normalize_text, validate_code, validate_name

MAX_LINES = 500

# " - " (com espaços dos dois lados) separa código e nome; aceita também traço longo (– —) vindo do Word/Excel.
# Sem os espaços, o hífen faz parte do código (ex.: PD-001).
_SEPARATOR = re.compile(r"\s+[-–—]\s+")


class ImportStatus(StrEnum):
    NEW = "nova"
    EXISTS = "existe"  # já cadastrado: ignorado
    INVALID = "invalida"

    @property
    def label(self) -> str:
        return {
            ImportStatus.NEW: "Nova",
            ImportStatus.EXISTS: "Já existe (ignorada)",
            ImportStatus.INVALID: "Inválida",
        }[self]


@dataclass(frozen=True)
class ImportLine:
    number: int  # linha no texto colado (1 = primeira)
    raw: str
    code: str
    name: str
    status: ImportStatus
    reason: str = ""


@dataclass(frozen=True)
class ImportPreview:
    lines: list[ImportLine]

    @property
    def new_lines(self) -> list[ImportLine]:
        return [line for line in self.lines if line.status is ImportStatus.NEW]

    def count(self, status: ImportStatus) -> int:
        return sum(1 for line in self.lines if line.status is status)


def split_line(line: str) -> tuple[str, str]:
    """Separa código e nome. Sem separador → ("", "")."""
    cells = [cell.strip() for cell in line.split("\t") if cell.strip()]
    if len(cells) > 1:
        return cells[0], " - ".join(cells[1:])
    parts = _SEPARATOR.split(line.strip(), maxsplit=1)
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[1]


def build_preview(text: str, existing_codes: set[str] | frozenset[str]) -> ImportPreview:
    """Classifica cada linha não vazia: nova, já existe (ignorada) ou inválida (com o motivo).

    `existing_codes` em maiúsculas (como ficam guardados). Mais de `MAX_LINES` linhas → ValidationError.
    """
    numbered = [(number, raw) for number, raw in enumerate(text.splitlines(), start=1) if raw.strip()]
    if len(numbered) > MAX_LINES:
        raise ValidationError(f"A lista tem {len(numbered)} linhas; o limite é {MAX_LINES} por vez. Divida em partes.")

    lines: list[ImportLine] = []
    seen: dict[str, int] = {}  # código → linha onde apareceu primeiro
    for number, raw in numbered:
        raw = raw.strip()
        code_text, name_text = split_line(raw)
        if not code_text:
            lines.append(ImportLine(number, raw, "", "", ImportStatus.INVALID,
                                    'Use o formato "CÓDIGO - Nome do projeto".'))
            continue
        code, name = normalize_code(code_text), normalize_text(name_text)
        try:
            validate_code(code)
            validate_name(name)
        except ValidationError as exc:
            lines.append(ImportLine(number, raw, code, name, ImportStatus.INVALID, str(exc)))
            continue
        if code in seen:
            lines.append(ImportLine(number, raw, code, name, ImportStatus.INVALID,
                                    f"Código repetido na lista (já está na linha {seen[code]})."))
            continue
        seen[code] = number
        status = ImportStatus.EXISTS if code in existing_codes else ImportStatus.NEW
        lines.append(ImportLine(number, raw, code, name, status))
    return ImportPreview(lines)
