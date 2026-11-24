"""Feriados: Páscoa, feriados nacionais, cadastro, jornada e tela. Dados fictícios."""

import re
from datetime import UTC, date, datetime

import pytest

from apontarhoras.domain.errors import PermissionDenied, ValidationError
from apontarhoras.domain.holiday import easter, national_holidays
from apontarhoras.domain.workday import DayStatus, expected_minutes
from apontarhoras.services import audit, holidays_service, projects_service, time_entries_service
from tests.test_web import Browser, _setup_admin, server  # noqa: F401 (fixture do servidor)

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


# ---- domain --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("year", "expected"),
    [
        (2000, date(2000, 4, 23)),
        (2008, date(2008, 3, 23)),
        (2011, date(2011, 4, 24)),
        (2019, date(2019, 4, 21)),
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
        (2038, date(2038, 4, 25)),
    ],
)
def test_easter_known_years(year, expected):
    assert easter(year) == expected


def test_national_holidays():
    days = dict(national_holidays(2026))
    assert len(days) == 10
    assert days[date(2026, 4, 3)] == "Sexta-feira Santa"
    assert days[date(2026, 11, 20)].startswith("Dia Nacional de Zumbi")
    assert date(2026, 2, 17) not in days  # Carnaval: ponto facultativo
    assert date(2026, 6, 4) not in days  # Corpus Christi: ponto facultativo
    assert list(days) == sorted(days)
    assert date(2023, 11, 20) not in dict(national_holidays(2023))  # nacional só desde 2024
    with pytest.raises(ValidationError):
        national_holidays(1999)


def test_expected_minutes_on_holiday():
    tuesday = date(2026, 11, 24)
    assert expected_minutes(tuesday) == 480  # jornada padrão: 8:00 seg–sex
    assert expected_minutes(tuesday, frozenset({tuesday})) == 0
    assert expected_minutes(date(2026, 11, 27), {tuesday}) == 480  # outro dia não muda


# ---- serviço -------------------------------------------------------------------------------------------------


def test_holidays_crud_and_audit(conn, admin):
    holiday = holidays_service.add_holiday(conn, admin, day="2026-01-20", description="  Aniversário  da cidade ",
                                           now=NOW)
    assert holiday.description == "Aniversário da cidade"
    with pytest.raises(ValidationError, match="Já existe"):
        holidays_service.add_holiday(conn, admin, day="2026-01-20", description="Outro")
    with pytest.raises(ValidationError, match="data"):
        holidays_service.add_holiday(conn, admin, day="20/01/2026", description="Outro")
    with pytest.raises(ValidationError, match="descrição"):
        holidays_service.add_holiday(conn, admin, day="2026-01-21", description="x")
    holidays_service.delete_holiday(conn, admin, holiday.id, now=NOW)
    assert holidays_service.list_year(conn, admin, 2026) == []
    log = [(a.action, a.entity) for a in audit.list_recent(conn, admin)[:2]]
    assert log == [("delete", "holiday"), ("create", "holiday")]


def test_national_holidays_without_duplicates(conn, admin):
    holidays_service.add_holiday(conn, admin, day="2026-12-25", description="Natal (já cadastrado)")
    added = holidays_service.add_national_holidays(conn, admin, 2026, now=NOW)
    assert len(added) == 9
    assert holidays_service.add_national_holidays(conn, admin, 2026) == []
    listed = holidays_service.list_year(conn, admin, 2026)
    assert len(listed) == 10
    assert listed[-1].description == "Natal (já cadastrado)"


def test_holidays_require_admin(conn, admin, collaborator):
    holiday = holidays_service.add_holiday(conn, admin, day="2026-01-20", description="Feriado local")
    with pytest.raises(PermissionDenied):
        holidays_service.list_year(conn, collaborator, 2026)
    with pytest.raises(PermissionDenied):
        holidays_service.add_holiday(conn, collaborator, day="2026-01-21", description="Folga")
    with pytest.raises(PermissionDenied):
        holidays_service.add_national_holidays(conn, collaborator, 2026)
    with pytest.raises(PermissionDenied):
        holidays_service.delete_holiday(conn, collaborator, holiday.id)


def test_month_summary_holiday_is_not_pending(conn, admin, collaborator):
    project = projects_service.create_project(conn, admin, code="PD-01", name="Sensor novo")
    holidays_service.add_national_holidays(conn, admin, 2026)
    summary = time_entries_service.month_summary(conn, collaborator, 2026, 11, today=date(2026, 11, 24))
    days = {d.day: d for d in summary.days}
    finados = days[date(2026, 11, 2)]  # segunda-feira
    assert finados.holiday == "Finados" and finados.expected == 0 and finados.status is DayStatus.NOT_WORKDAY
    assert days[date(2026, 11, 15)].holiday == "Proclamação da República"  # domingo: aparece como feriado
    assert days[date(2026, 11, 20)].status is DayStatus.NOT_WORKDAY  # sexta
    assert days[date(2026, 11, 3)].status is DayStatus.MISSING
    # 17 dias úteis até 24/11, menos Finados (02) e Consciência Negra (20)
    assert summary.missing_days == 15
    assert project.active


# ---- tela ----------------------------------------------------------------------------------------------------


def test_holidays_page_flow(server):  # noqa: F811
    admin = _setup_admin(server)
    _, _, body, _ = admin.get("/feriados?ano=2026")
    assert 'href="/feriados"' in body and "Adicionar feriados nacionais de 2026" in body
    _, path, body, _ = admin.post("/feriados/nacionais", {"ano": "2026"})
    assert path == "/feriados" and "Feriados nacionais adicionados" in body
    assert "03/04/2026" in body and "Sexta-feira Santa" in body
    _, _, body, _ = admin.post("/feriados/novo", {"data": "2026-01-20", "descricao": "Aniversário <da cidade>"})
    assert "Aniversário &lt;da cidade&gt;" in body
    first_id = re.search(r"/feriados/(\d+)/excluir", body).group(1)  # lista em ordem de data: 01/01
    _, _, body, _ = admin.get(f"/feriados/{first_id}/excluir")
    assert "Confirmar exclusão" in body and "01/01/2026" in body
    _, path, body, _ = admin.post(f"/feriados/{first_id}/excluir", {})
    assert path == "/feriados" and "01/01/2026" not in body
    # Meus apontamentos mostra o feriado no lugar da pendência
    _, _, body, _ = admin.get("/apontamentos?mes=2026-11")
    assert "Feriado: Finados" in body
    _, path, _, _ = Browser(server).get("/feriados")
    assert path == "/entrar"


def test_favicon(server):  # noqa: F811
    browser = Browser(server)
    _setup_admin(server)
    status, path, body, headers = browser.get("/favicon.ico")  # sem login
    assert (status, path) == (200, "/favicon.ico")
    assert headers["Content-Type"] == "image/svg+xml" and "<svg" in body
    status, _, _, _ = browser.get("/static/favicon.svg")
    assert status == 200
    _, _, page, _ = browser.get("/entrar")
    assert '<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">' in page
