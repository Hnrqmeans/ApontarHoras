"""Importar projetos colando a lista da planilha (parser puro, serviço e tela). Dados fictícios."""

import re
from datetime import UTC, datetime

import pytest

from apontarhoras.domain.errors import PermissionDenied, ValidationError
from apontarhoras.domain.project_import import MAX_LINES, ImportStatus, build_preview, split_line
from apontarhoras.services import audit, project_import_service, projects_service
from tests.test_web import Browser, _setup_admin, server  # noqa: F401 (fixture do servidor)

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


# ---- parser (domain) -----------------------------------------------------------------------------------------


def test_split_line_formats():
    assert split_line("PD-001 - Cliente Exemplo - Sensor novo") == ("PD-001", "Cliente Exemplo - Sensor novo")
    assert split_line("PD-002 - Controlador") == ("PD-002", "Controlador")
    assert split_line("PD-003 – Traço longo") == ("PD-003", "Traço longo")
    assert split_line("PD-004\tCliente Exemplo\tSensor novo") == ("PD-004", "Cliente Exemplo - Sensor novo")
    assert split_line("PD-005\t\tSó nome") == ("PD-005", "Só nome")
    assert split_line("PD-006 sem separador") == ("", "")
    assert split_line("PD-007-sem-espaços") == ("", "")


def test_preview_classifies_lines():
    text = (
        "pd-001 - Cliente Exemplo - Sensor novo\n"
        "\n"
        "PD-002 - Já cadastrado\r\n"
        "   \n"
        "linha sem separador\n"
        "CÓDIGO COM ESPAÇO - Nome\n"
        "PD-003 - X\n"
        "PD-001 - Repetido\n"
        "PD-004\tCliente\tProjeto do Excel\n"
    )
    preview = build_preview(text, {"PD-002"})
    by_number = {line.number: line for line in preview.lines}
    assert sorted(by_number) == [1, 3, 5, 6, 7, 8, 9]  # linhas vazias ignoradas
    assert by_number[1].status is ImportStatus.NEW
    assert (by_number[1].code, by_number[1].name) == ("PD-001", "Cliente Exemplo - Sensor novo")
    assert by_number[3].status is ImportStatus.EXISTS
    assert by_number[5].status is ImportStatus.INVALID and "formato" in by_number[5].reason
    assert by_number[6].status is ImportStatus.INVALID and "código" in by_number[6].reason.lower()
    assert by_number[7].status is ImportStatus.INVALID and "nome" in by_number[7].reason.lower()
    assert by_number[8].status is ImportStatus.INVALID and "linha 1" in by_number[8].reason
    assert by_number[9].status is ImportStatus.NEW and by_number[9].name == "Cliente - Projeto do Excel"
    assert [line.code for line in preview.new_lines] == ["PD-001", "PD-004"]
    assert preview.count(ImportStatus.INVALID) == 4


def test_preview_line_limit():
    ok = "\n".join(f"P{n} - Projeto {n}" for n in range(MAX_LINES))
    assert len(build_preview(ok + "\n\n\n", set()).lines) == MAX_LINES
    with pytest.raises(ValidationError, match="limite"):
        build_preview(ok + "\nP999 - Um a mais", set())


# ---- serviço -------------------------------------------------------------------------------------------------


def test_import_creates_new_and_audits(conn, admin):
    projects_service.create_project(conn, admin, code="PD-002", name="Já cadastrado", now=NOW)
    text = "PD-001 - Cliente Exemplo - Sensor novo\nPD-002 - Outro nome\nruim\nPD-003 - Controlador"
    created = project_import_service.import_projects(conn, admin, text, rd_eligible=False, now=NOW)
    assert [p.code for p in created] == ["PD-001", "PD-003"]
    assert all(not p.rd_eligible for p in created)
    assert projects_service.get_project(conn, admin, created[0].id).name == "Cliente Exemplo - Sensor novo"
    log = [(a.action, a.entity, a.details.get("código")) for a in audit.list_recent(conn, admin)[:2]]
    assert sorted(log) == [("create", "project", "PD-001"), ("create", "project", "PD-003")]
    # importar de novo não duplica
    assert project_import_service.import_projects(conn, admin, text, now=NOW) == []
    assert len(projects_service.list_projects(conn, admin, include_inactive=True)) == 3


def test_import_requires_admin(conn, collaborator):
    with pytest.raises(PermissionDenied):
        project_import_service.preview(conn, collaborator, "PD-001 - Projeto")
    with pytest.raises(PermissionDenied):
        project_import_service.import_projects(conn, collaborator, "PD-001 - Projeto")


# ---- tela ----------------------------------------------------------------------------------------------------


def test_import_flow_in_two_steps(server):  # noqa: F811
    admin = _setup_admin(server)
    _, _, body, _ = admin.get("/projetos")
    assert 'href="/projetos/importar"' in body
    admin.get("/projetos/importar")
    text = "PD-001 - Cliente Exemplo - Sensor <novo>\nPD-002 - Controlador\nruim"
    _, path, body, _ = admin.post("/projetos/importar", {"lista": text, "lei_do_bem": "1"})
    assert path == "/projetos/importar"
    assert "Importar 2 projeto(s)" in body and "Inválida" in body
    assert "Sensor &lt;novo&gt;" in body
    # nada foi gravado ainda
    _, _, listing, _ = admin.get("/projetos")
    assert "PD-001" not in listing
    admin.get("/projetos/importar")
    admin.post("/projetos/importar", {"lista": text, "lei_do_bem": "1"})
    hidden = re.search(r'<input type="hidden" name="lista" value="([^"]*)"', admin.last).group(1)
    assert "PD-002" in hidden
    _, path, body, _ = admin.post("/projetos/importar/confirmar", {"lista": text, "lei_do_bem": "1"})
    assert path == "/projetos" and "Projetos importados" in body
    assert "PD-001" in body and "PD-002" in body
    # sem login vai para a tela de entrar (o colaborador é barrado no serviço: test_import_requires_admin)
    _, path, _, _ = Browser(server).get("/projetos/importar")
    assert path == "/entrar"
