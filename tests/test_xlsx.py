"""Gerador de .xlsx (zipfile + XML): estrutura válida, tipos de célula, escape e proteção contra fórmula."""

import io
import zipfile
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree

from apontarhoras.integrations.xlsx import MIME_TYPE, Sheet, build_xlsx, clean_text
from apontarhoras.integrations.xlsx.writer import column_letter

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REQUIRED_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "xl/workbook.xml",
    "xl/_rels/workbook.xml.rels",
    "xl/styles.xml",
    "xl/worksheets/sheet1.xml",
    "xl/worksheets/sheet2.xml",
}


def _build() -> bytes:
    return build_xlsx([
        Sheet("Apontamentos", [["Data", "Horas", "Qtd", "Texto", "Vazio"],
                               [date(2026, 11, 24), Decimal("8.50"), 3, "a\x00b\x1fc\nd", None]],
                widths=(11, 8)),
        Sheet("Resumo/[x]", [["Selo", "abcd"]], header=False),
    ])


def test_structure_is_valid_xml():
    content = _build()
    assert MIME_TYPE.endswith("spreadsheetml.sheet")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == REQUIRED_PARTS
        for name in archive.namelist():
            ElementTree.fromstring(archive.read(name))  # todo XML bem formado
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        names = [s.get("name") for s in workbook.findall(".//m:sheet", NS)]
        assert names == ["Apontamentos", "Resumo  x"]  # caracteres proibidos em nome de aba trocados
        styles = archive.read("xl/styles.xml").decode()
        assert 'formatCode="dd/mm/yyyy"' in styles
    assert build_xlsx([Sheet("A", [["x"]])]) == build_xlsx([Sheet("A", [["x"]])])  # determinístico


def test_cell_types_and_cleaning():
    with zipfile.ZipFile(io.BytesIO(_build())) as archive:
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    cells = {c.get("r"): c for c in sheet.findall(".//m:c", NS)}
    assert cells["A1"].get("t") == "inlineStr" and cells["A1"].get("s") == "3"  # cabeçalho em negrito
    assert cells["A2"].find("m:v", NS).text == str((date(2026, 11, 24) - date(1899, 12, 30)).days)
    assert cells["A2"].get("s") == "1"  # formato de data
    assert cells["B2"].find("m:v", NS).text == "8.50" and cells["B2"].get("s") == "2"
    assert cells["C2"].find("m:v", NS).text == "3"
    assert cells["D2"].find("m:is/m:t", NS).text == "abc\nd"  # controle inválido removido, quebra mantida
    assert "E2" not in cells  # None = célula vazia
    assert sheet.find(".//m:pane", NS).get("state") == "frozen"


def test_formula_injection_and_escape():
    for dangerous in ("=1+1", "+1", "-1", "@SUM(A1)", "\tx", "\rx"):
        assert clean_text(dangerous) == "'" + dangerous
    assert clean_text("Normal") == "Normal"
    content = build_xlsx([Sheet("A", [["=CMD()", "<b>&\"'"]])])
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        raw = archive.read("xl/worksheets/sheet1.xml").decode()
    assert "<f>" not in raw  # nunca uma célula de fórmula
    sheet = ElementTree.fromstring(raw)
    texts = [t.text for t in sheet.findall(".//m:t", NS)]
    assert texts == ["'=CMD()", "<b>&\"'"]


def test_column_letters():
    assert [column_letter(i) for i in (0, 25, 26, 27, 701, 702)] == ["A", "Z", "AA", "AB", "ZZ", "AAA"]
