"""Planilha Excel (.xlsx) mínima com `zipfile` + XML (SpreadsheetML), sem bibliotecas de terceiros.

Partes geradas: `[Content_Types].xml`, `_rels/.rels`, `xl/workbook.xml`, `xl/_rels/workbook.xml.rels`,
`xl/styles.xml` e `xl/worksheets/sheetN.xml`.

Tipos de célula: `str` → texto em linha (`inlineStr`); `int` → número; `Decimal` → número com 2 casas;
`date` → número de série com formato dd/mm/aaaa; `None` → célula vazia.

Fórmula injetada: célula `inlineStr` é sempre texto — o Excel/LibreOffice não a avaliam como fórmula, mesmo que
comece com `=`. Por garantia (o usuário pode copiar a célula, salvar como CSV, ou outro programa pode reinterpretar),
texto que começa com `= + - @`, tabulação ou CR recebe um apóstrofo na frente (recomendação OWASP "CSV injection").
"""

import re
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

Cell = str | int | Decimal | date | None

MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
# Fora do XML 1.0: caracteres de controle (exceto tab, LF, CR), substitutos soltos e U+FFFE/U+FFFF.
_INVALID_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")
_SHEET_NAME_FORBIDDEN = re.compile(r"[\[\]:*?/\\]")
_EXCEL_EPOCH = date(1899, 12, 30)
_ZIP_DATE = (2000, 1, 1, 0, 0, 0)  # data fixa nas entradas do zip: mesmo conteúdo → mesmo arquivo

# índices de `cellXfs` em styles.xml
_STYLE_DEFAULT, _STYLE_DATE, _STYLE_DECIMAL, _STYLE_HEADER = 0, 1, 2, 3

_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


@dataclass
class Sheet:
    name: str
    rows: Sequence[Sequence[Cell]]
    widths: Sequence[int] = field(default_factory=tuple)  # largura de cada coluna (em caracteres)
    header: bool = True  # primeira linha em negrito e congelada


def clean_text(text: str) -> str:
    """Remove o que o XML não aceita e neutraliza texto que pareça fórmula."""
    text = _INVALID_XML.sub("", text)
    if text.startswith(_FORMULA_START):
        text = "'" + text
    return text


def column_letter(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def _sheet_name(name: str) -> str:
    cleaned = _SHEET_NAME_FORBIDDEN.sub(" ", _INVALID_XML.sub("", name)).strip().strip("'")[:31]
    return cleaned or "Planilha"


def _cell(ref: str, value: Cell, header: bool) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):  # bool é int em Python: vira texto para não sair 1/0
        value = "Sim" if value else "Não"
    if isinstance(value, str):
        style = f' s="{_STYLE_HEADER}"' if header else ""
        text = escape(clean_text(value))
        return f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{text}</t></is></c>'
    if isinstance(value, date):
        return f'<c r="{ref}" s="{_STYLE_DATE}"><v>{(value - _EXCEL_EPOCH).days}</v></c>'
    if isinstance(value, Decimal):
        return f'<c r="{ref}" s="{_STYLE_DECIMAL}"><v>{value:f}</v></c>'
    if isinstance(value, int):
        return f'<c r="{ref}"><v>{value}</v></c>'
    raise TypeError(f"Tipo de célula não suportado: {type(value).__name__}")


def _worksheet(sheet: Sheet) -> str:
    views = ""
    if sheet.header and sheet.rows:
        views = ('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
                 'state="frozen"/></sheetView></sheetViews>')
    cols = "".join(
        f'<col min="{i + 1}" max="{i + 1}" width="{width}" customWidth="1"/>' for i, width in enumerate(sheet.widths)
    )
    cols = f"<cols>{cols}</cols>" if cols else ""
    rows = []
    for row_index, row in enumerate(sheet.rows, start=1):
        is_header = sheet.header and row_index == 1
        cells = "".join(
            _cell(f"{column_letter(col)}{row_index}", value, is_header) for col, value in enumerate(row)
        )
        rows.append(f'<row r="{row_index}">{cells}</row>')
    return f'{_XML_DECL}<worksheet xmlns="{_NS_MAIN}">{views}{cols}<sheetData>{"".join(rows)}</sheetData></worksheet>'


_STYLES = (
    f'{_XML_DECL}<styleSheet xmlns="{_NS_MAIN}">'
    '<numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts>'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
    "</fills>"
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="4">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '<xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
    "</cellXfs>"
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    "</styleSheet>"
)


def build_xlsx(sheets: Sequence[Sheet]) -> bytes:
    """Monta o arquivo .xlsx (bytes) com as planilhas na ordem dada."""
    if not sheets:
        raise ValueError("A planilha precisa de pelo menos uma aba.")
    names: list[str] = []
    for sheet in sheets:
        name = _sheet_name(sheet.name)
        if name.casefold() in (existing.casefold() for existing in names):
            name = f"{name[:28]} {len(names) + 1}"
        names.append(name)

    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1)
    )
    content_types = (
        f'{_XML_DECL}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{overrides}</Types>"
    )
    root_rels = (
        f'{_XML_DECL}<Relationships xmlns="{_NS_PKG_REL}">'
        f'<Relationship Id="rId1" Type="{_NS_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    )
    sheet_entries = "".join(
        f'<sheet name="{escape(name, {chr(34): "&quot;"})}" sheetId="{i}" r:id="rId{i}"/>'
        for i, name in enumerate(names, start=1)
    )
    workbook = (
        f'{_XML_DECL}<workbook xmlns="{_NS_MAIN}" xmlns:r="{_NS_REL}"><sheets>{sheet_entries}</sheets></workbook>'
    )
    sheet_rels = "".join(
        f'<Relationship Id="rId{i}" Type="{_NS_REL}/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, len(sheets) + 1)
    )
    workbook_rels = (
        f'{_XML_DECL}<Relationships xmlns="{_NS_PKG_REL}">{sheet_rels}'
        f'<Relationship Id="rId{len(sheets) + 1}" Type="{_NS_REL}/styles" Target="styles.xml"/></Relationships>'
    )

    parts = [
        ("[Content_Types].xml", content_types),
        ("_rels/.rels", root_rels),
        ("xl/workbook.xml", workbook),
        ("xl/_rels/workbook.xml.rels", workbook_rels),
        ("xl/styles.xml", _STYLES),
    ]
    parts += [(f"xl/worksheets/sheet{i}.xml", _worksheet(sheet)) for i, sheet in enumerate(sheets, start=1)]

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, xml in parts:
            info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, xml.encode("utf-8"))
    return buffer.getvalue()
