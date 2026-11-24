"""Confiança pelo rastro (D9): lançamento tardio, motivo da correção, auditoria encadeada, recuperação de acesso e
aviso de responsável único. Dados fictícios."""

import re
import threading
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from apontarhoras import recuperar
from apontarhoras.domain.audit_chain import GENESIS_HASH, canonical_content, chain_hash
from apontarhoras.domain.errors import AuthError, NotFound, PermissionDenied, ValidationError
from apontarhoras.domain.time_entry import MAX_REASON, is_late_entry, validate_correction_reason
from apontarhoras.services import (
    audit,
    auth_service,
    projects_service,
    tasks_service,
    time_entries_service,
    users_service,
)
from apontarhoras.storage import audit_repo, users_repo
from apontarhoras.storage.db import Database
from apontarhoras.web.app import App
from apontarhoras.web.server import AppServer
from tests.conftest import ADMIN_PASSWORD, TEMP_PASSWORD
from tests.test_web import Browser, _setup_admin

TODAY = date(2026, 11, 24)
NEW_PASSWORD = "nova-temporaria-9"


@pytest.fixture
def project(conn, admin):
    return projects_service.create_project(conn, admin, code="PD-01", name="Sensor novo")


@pytest.fixture
def task(conn, admin):
    return next(t for t in tasks_service.list_tasks(conn, admin) if t.name == "Desenvolvimento")


def _entry(conn, user, project, task, **overrides):
    values = {"work_date": "2026-11-24", "project_id": project.id, "task_id": task.id, "start": "8", "end": "12",
              "description": "Ajuste do controle", "today": TODAY}
    values.update(overrides)
    return time_entries_service.create_entry(conn, user, **values)


def _update(conn, actor, entry, **overrides):
    values = {"work_date": entry.work_date.isoformat(), "project_id": entry.project_id, "task_id": entry.task_id,
              "start": "8", "end": "11", "description": entry.description, "today": TODAY}
    values.update(overrides)
    return time_entries_service.update_entry(conn, actor, entry.id, **values)


# ---- lançamento tardio ---------------------------------------------------------------------------------------


def test_is_late_entry():
    assert not is_late_entry(date(2026, 11, 3), date(2026, 11, 30))  # mesmo mês
    assert is_late_entry(date(2026, 11, 30), date(2026, 12, 1))  # virou o mês
    assert is_late_entry(date(2026, 12, 31), date(2027, 1, 2))  # virou o ano
    assert not is_late_entry(date(2026, 11, 30), date(2026, 11, 3))  # (não acontece: data futura é recusada)


def test_entered_late_uses_local_date_of_creation(conn, collaborator, project, task):
    brazil = timezone(timedelta(hours=-3))
    # 01/12 às 01:00 UTC = 30/11 às 22:00 no Brasil: ainda é o mesmo mês
    entry = _entry(conn, collaborator, project, task, work_date="2026-11-30", today=date(2026, 11, 30),
                   now=datetime(2026, 12, 1, 1, 0, tzinfo=UTC))
    assert not time_entries_service.entered_late(entry, tz=brazil)
    assert time_entries_service.entered_late(entry, tz=UTC)
    on_time = _entry(conn, collaborator, project, task, now=datetime(2026, 11, 24, 15, 0, tzinfo=UTC))
    assert not time_entries_service.entered_late(on_time, tz=brazil)


# ---- motivo obrigatório quando o responsável mexe no apontamento de outra pessoa ----------------------------


def test_validate_correction_reason():
    assert validate_correction_reason("  Horário trocado \r\n") == "Horário trocado"
    with pytest.raises(ValidationError, match="motivo"):
        validate_correction_reason("ok")
    with pytest.raises(ValidationError, match="máximo"):
        validate_correction_reason("x" * (MAX_REASON + 1))
    assert validate_correction_reason("x" * MAX_REASON)


def test_admin_needs_reason_to_change_others_entry(conn, admin, collaborator, project, task):
    entry = _entry(conn, collaborator, project, task)
    with pytest.raises(ValidationError, match="motivo"):
        _update(conn, admin, entry)
    assert time_entries_service.get_entry(conn, admin, entry.id).end_minute == 12 * 60  # nada mudou
    _update(conn, admin, entry, reason="  Colaborador informou o término errado ")
    record = audit.list_recent(conn, admin, 1)[0]
    assert (record.action, record.entity_id) == ("update", entry.id)
    assert record.details["motivo"] == "Colaborador informou o término errado"
    assert record.details["término"] == ["12:00", "11:00"]


def test_owner_does_not_need_reason(conn, admin, collaborator, project, task):
    entry = _entry(conn, collaborator, project, task)
    _update(conn, collaborator, entry)
    assert "motivo" not in audit.list_recent(conn, admin, 1)[0].details
    # o responsável no próprio apontamento também não precisa
    own = _entry(conn, admin, project, task)
    _update(conn, admin, own)
    time_entries_service.delete_entry(conn, admin, own.id)
    assert "motivo" not in audit.list_recent(conn, admin, 1)[0].details


def test_admin_needs_reason_to_delete_others_entry(conn, admin, collaborator, project, task):
    entry = _entry(conn, collaborator, project, task)
    with pytest.raises(ValidationError, match="motivo"):
        time_entries_service.delete_entry(conn, admin, entry.id, reason=" ")
    assert time_entries_service.get_entry(conn, collaborator, entry.id)  # continua lá
    time_entries_service.delete_entry(conn, admin, entry.id, reason="Lançado em duplicidade")
    record = audit.list_recent(conn, admin, 1)[0]
    assert (record.action, record.details["motivo"]) == ("delete", "Lançado em duplicidade")
    assert record.details["colaborador"] == "Bruno Colaborador"


# ---- auditoria encadeada -------------------------------------------------------------------------------------


def _activity(conn, admin, collaborator, project, task):
    """Alguns registros de auditoria (setup, criação de usuário/projeto e apontamentos já existem)."""
    entry = _entry(conn, collaborator, project, task)
    _update(conn, collaborator, entry)
    _entry(conn, collaborator, project, task, start="13", end="14")


def _ids(conn):
    return [row[0] for row in conn.execute("SELECT id FROM audit_log ORDER BY id")]


def test_chain_hash_is_deterministic():
    content = canonical_content(at="2026-11-24T10:00:00+00:00", actor_id=1, actor_name="Ana (ana)", action="create",
                                entity="user", entity_id=2, details={"b": 1, "a": "ç"})
    same = canonical_content(at="2026-11-24T10:00:00+00:00", actor_id=1, actor_name="Ana (ana)", action="create",
                             entity="user", entity_id=2, details={"a": "ç", "b": 1})
    assert content == same
    assert chain_hash(GENESIS_HASH, content) == chain_hash(GENESIS_HASH, same)
    assert chain_hash(GENESIS_HASH, content) != chain_hash("1" * 64, content)


def test_chain_is_intact_after_normal_use(conn, admin, collaborator, project, task):
    _activity(conn, admin, collaborator, project, task)
    check = audit.verify_integrity(conn, admin)
    ids = _ids(conn)
    assert check.ok and check.total == len(ids) and check.last_id == ids[-1]
    assert check.last_hash == audit.seal_of(conn, admin, ids[-1])
    first = conn.execute("SELECT prev_hash FROM audit_log ORDER BY id LIMIT 1").fetchone()[0]
    assert first == GENESIS_HASH


def test_tampered_row_is_detected(conn, admin, collaborator, project, task):
    _activity(conn, admin, collaborator, project, task)
    target = _ids(conn)[3]
    conn.execute("UPDATE audit_log SET details = '{\"horas\": \"9:00\"}' WHERE id = ?", (target,))
    check = audit.verify_integrity(conn, admin)
    assert not check.ok and check.broken_id == target
    # quem também recalcula o selo da linha alterada quebra a ligação com a seguinte
    row = conn.execute("SELECT * FROM audit_log WHERE id = ?", (target,)).fetchone()
    content = canonical_content(at=row["at"], actor_id=row["actor_id"], actor_name=row["actor_name"],
                                action=row["action"], entity=row["entity"], entity_id=row["entity_id"],
                                details={"horas": "9:00"})
    conn.execute("UPDATE audit_log SET hash = ? WHERE id = ?", (chain_hash(row["prev_hash"], content), target))
    assert audit.verify_integrity(conn, admin).broken_id == _ids(conn)[4]


def test_other_tampering_is_detected(conn, admin, collaborator, project, task):
    _activity(conn, admin, collaborator, project, task)
    ids = _ids(conn)
    conn.execute("UPDATE audit_log SET actor_name = 'Outra pessoa' WHERE id = ?", (ids[1],))
    assert audit.verify_integrity(conn, admin).broken_id == ids[1]
    conn.execute("UPDATE audit_log SET actor_name = 'x', details = 'não é json' WHERE id = ?", (ids[0],))
    assert audit.verify_integrity(conn, admin).broken_id == ids[0]


def test_deleted_middle_row_is_detected(conn, admin, collaborator, project, task):
    _activity(conn, admin, collaborator, project, task)
    ids = _ids(conn)
    conn.execute("DELETE FROM audit_log WHERE id = ?", (ids[2],))
    check = audit.verify_integrity(conn, admin)
    assert not check.ok and check.broken_id == ids[3]


def test_deleted_last_row_needs_an_external_note(conn, admin, collaborator, project, task):
    """Limitação conhecida: apagar os últimos registros mantém a corrente íntegra. Por isso o responsável anota
    o número e o selo do último registro fora do servidor e confere depois (tela Verificar integridade)."""
    _activity(conn, admin, collaborator, project, task)
    noted = audit.verify_integrity(conn, admin)
    conn.execute("DELETE FROM audit_log WHERE id = ?", (noted.last_id,))
    later = audit.verify_integrity(conn, admin)
    assert later.ok  # a corrente sozinha não percebe
    assert later.last_id < noted.last_id and later.total == noted.total - 1  # a anotação, sim
    assert audit.seal_of(conn, admin, noted.last_id) is None


def test_old_records_are_sealed_on_startup(db, conn, admin, collaborator, project, task):
    """Registros gravados antes da migração 003 (sem selo) são selados ao abrir o banco, em ordem de id."""
    _activity(conn, admin, collaborator, project, task)
    sealed = [tuple(row) for row in conn.execute("SELECT id, prev_hash, hash FROM audit_log ORDER BY id")]
    conn.execute("UPDATE audit_log SET prev_hash = NULL, hash = NULL")
    assert not audit.verify_integrity(conn, admin).ok
    db.initialize()
    assert [tuple(row) for row in conn.execute("SELECT id, prev_hash, hash FROM audit_log ORDER BY id")] == sealed
    assert audit.verify_integrity(conn, admin).ok
    assert audit_repo.seal_pending(conn) == 0


def test_only_admin_verifies(conn, admin, collaborator):
    with pytest.raises(PermissionDenied):
        audit.verify_integrity(conn, collaborator)
    with pytest.raises(PermissionDenied):
        audit.seal_of(conn, collaborator, 1)
    with pytest.raises(PermissionDenied):
        audit.verify_integrity(conn, None)


def test_concurrent_writes_keep_the_chain(db, admin):
    """Várias conexões gravando ao mesmo tempo (servidor com várias pessoas) não bifurcam a corrente."""

    def work(number):
        connection = db.connect()
        try:
            for attempt in range(5):
                with pytest.raises(AuthError):
                    auth_service.login(connection, "ana", f"errada-{number}-{attempt}")
                users_repo.set_login_state(connection, admin.id, failed_attempts=0, locked_until=None)
        finally:
            connection.close()

    threads = [threading.Thread(target=work, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    connection = db.connect()
    try:
        check = audit.verify_integrity(connection, admin)
        assert check.ok and check.total >= 20
    finally:
        connection.close()


# ---- recuperação de acesso pelo servidor ---------------------------------------------------------------------


def _lock_and_deactivate(conn, admin, user):
    users_service.update_user(conn, admin, user.id, name=user.name, role=user.role.value, active=False)
    users_repo.set_login_state(conn, user.id, failed_attempts=5, locked_until=datetime.now(UTC) + timedelta(hours=1))


def test_recover_access(conn, admin, collaborator):
    session = auth_service.login(conn, "bruno", TEMP_PASSWORD)
    _lock_and_deactivate(conn, admin, collaborator)
    recovered = users_service.recover_access(conn, " BRUNO ", NEW_PASSWORD)
    assert recovered.active and recovered.must_change_password and not recovered.is_locked(datetime.now(UTC))
    assert recovered.failed_attempts == 0
    assert auth_service.user_for_token(conn, session.token) is None  # sessões encerradas
    assert auth_service.login(conn, "bruno", NEW_PASSWORD).user.must_change_password
    record = next(a for a in audit.list_recent(conn, admin) if a.action == "password_reset")
    assert record.actor_name == users_service.RECOVERY_ACTOR and record.actor_id is None
    assert record.details["login"] == "bruno" and record.details["ativo"] == [False, True]
    assert NEW_PASSWORD not in str(record.details)
    assert audit.verify_integrity(conn, admin).ok


def test_recover_access_errors(conn, admin):
    with pytest.raises(NotFound):
        users_service.recover_access(conn, "ninguem", NEW_PASSWORD)
    with pytest.raises(ValidationError):
        users_service.recover_access(conn, "ana", "curta")
    with pytest.raises(ValidationError):
        users_service.recover_access(conn, "ana", "ana")
    assert auth_service.login(conn, "ana", ADMIN_PASSWORD)  # nada mudou


@pytest.fixture
def server_data(tmp_path):
    """Pasta de dados como a do servidor (arquivo `apontarhoras.db`), com o responsável, e o .ini apontando para ela."""
    data_dir = tmp_path / "servidor" / "dados"
    database = Database(data_dir / "apontarhoras.db")
    database.initialize()
    connection = database.connect()
    try:
        auth_service.setup_first_admin(connection, "Ana Responsável", "ana", ADMIN_PASSWORD)
    finally:
        connection.close()
    ini = tmp_path / "servidor" / "ApontarHoras.ini"
    ini.write_text(f"[servidor]\nrede = sim\ndados = {data_dir}\n", encoding="utf-8-sig")
    return database, ini


def _answers(*values):
    answers = iter(values)
    return lambda prompt: next(answers)


def test_recover_command(server_data):
    database, ini = server_data
    output = []
    code = recuperar.run(["ana", "--config", str(ini)], read_password=_answers(NEW_PASSWORD, NEW_PASSWORD),
                         out=output.append)
    assert code == 0, output
    assert any("Pronto" in line for line in output)
    connection = database.connect()
    try:
        assert auth_service.login(connection, "ana", NEW_PASSWORD).user.must_change_password
    finally:
        connection.close()


def test_recover_command_failures(server_data, tmp_path):
    database, ini = server_data
    output = []
    # senhas diferentes
    assert recuperar.run(["ana", "--config", str(ini)], read_password=_answers(NEW_PASSWORD, "outra-senha-1"),
                         out=output.append) == 1
    assert "não conferem" in output[-1]
    # login que não existe
    assert recuperar.run(["ninguem", "--config", str(ini)], read_password=_answers(NEW_PASSWORD, NEW_PASSWORD),
                         out=output.append) == 1
    assert "ninguem" in output[-1]

    # cancelado no meio (Ctrl+C / fim da entrada)
    def cancel(prompt):
        raise EOFError

    assert recuperar.run(["ana", "--config", str(ini)], read_password=cancel, out=output.append) == 1
    # pasta errada: não cria um banco novo vazio
    empty = tmp_path / "vazia"
    assert recuperar.run(["ana", "--config", str(ini), "--dados", str(empty)],
                         read_password=_answers(NEW_PASSWORD, NEW_PASSWORD), out=output.append) == 1
    assert "não encontrado" in output[-1] and not empty.exists()
    connection = database.connect()
    try:
        assert auth_service.login(connection, "ana", ADMIN_PASSWORD)  # nada mudou
    finally:
        connection.close()


# ---- aviso de responsável único ------------------------------------------------------------------------------


def test_single_admin_warning(conn, admin, collaborator):
    assert users_service.has_single_admin(conn, admin)
    with pytest.raises(PermissionDenied):
        users_service.has_single_admin(conn, collaborator)
    users_service.update_user(conn, admin, collaborator.id, name=collaborator.name, role="admin", active=True)
    assert not users_service.has_single_admin(conn, admin)


# ---- telas ---------------------------------------------------------------------------------------------------


@pytest.fixture
def server(db):
    httpd = AppServer(("127.0.0.1", 0), App(db))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _with_collaborator_entry(server, db):
    """Responsável + colaborador com um apontamento de hoje (criado pelo service, na mesma base do servidor)."""
    browser = _setup_admin(server)
    conn = db.connect()
    try:
        admin = users_repo.get_by_login(conn, "ana")
        bruno = users_service.create_user(conn, admin, name="Bruno Colaborador", login="bruno", role="colaborador",
                                          temporary_password=TEMP_PASSWORD)
        project = projects_service.create_project(conn, admin, code="PD-01", name="Sensor novo")
        task = next(t for t in tasks_service.list_tasks(conn, admin) if t.name == "Desenvolvimento")
        entry = time_entries_service.create_entry(conn, bruno, work_date=date.today().isoformat(),
                                                  project_id=project.id, task_id=task.id, start="8", end="12",
                                                  description="Ajuste do controle")
    finally:
        conn.close()
    return browser, entry


def test_web_admin_corrects_with_reason(server, db):
    admin, entry = _with_collaborator_entry(server, db)
    _, _, body, _ = admin.get(f"/apontamentos/{entry.id}/editar")
    assert "Motivo da correção" in body
    fields = {"data": entry.work_date.isoformat(), "projeto": str(entry.project_id), "tarefa": str(entry.task_id),
              "inicio": "8", "termino": "11", "almoco": "", "descricao": "Ajuste do controle"}
    _, path, body, _ = admin.post(f"/apontamentos/{entry.id}/editar", fields)
    assert path == f"/apontamentos/{entry.id}/editar" and "Informe o motivo" in body
    _, path, _, _ = admin.post(f"/apontamentos/{entry.id}/editar", {**fields, "motivo": "Término informado errado"})
    assert path == "/apontamentos"
    _, _, body, _ = admin.get(f"/apontamentos/{entry.id}/excluir")
    assert "Motivo da correção" in body
    _, _, body, _ = admin.post(f"/apontamentos/{entry.id}/excluir", {})
    assert "Informe o motivo" in body
    _, path, _, _ = admin.post(f"/apontamentos/{entry.id}/excluir", {"motivo": "Lançado em duplicidade"})
    assert path == "/apontamentos"
    _, _, body, _ = admin.get("/auditoria")
    assert "motivo: Término informado errado" in body and "motivo: Lançado em duplicidade" in body


def test_web_owner_has_no_reason_field(server):
    admin = _setup_admin(server)
    admin.get("/projetos/novo")
    admin.post("/projetos/novo", {"codigo": "pd-01", "nome": "Sensor novo", "descricao": "", "lei_do_bem": "1"})
    _, _, form_page, _ = admin.get("/apontamentos/novo")
    project_id = re.search(r'<option value="(\d+)">PD-01', form_page).group(1)
    task_id = re.search(r'<option value="(\d+)">Desenvolvimento', form_page).group(1)
    _, _, body, _ = admin.post("/apontamentos/novo", {"data": date.today().isoformat(), "projeto": project_id,
                                                      "tarefa": task_id, "inicio": "8", "termino": "9",
                                                      "almoco": "", "descricao": "Revisão"})
    entry_id = re.search(r"/apontamentos/(\d+)/editar", body).group(1)
    _, _, body, _ = admin.get(f"/apontamentos/{entry_id}/editar")
    assert "Motivo da correção" not in body
    assert "Lançado depois do mês" not in admin.get("/apontamentos")[2]


def test_web_late_entry_is_flagged(server, db):
    admin, entry = _with_collaborator_entry(server, db)
    previous = (date.today().replace(day=1) - timedelta(days=1))
    conn = db.connect()
    try:  # o mesmo apontamento, como se a data trabalhada fosse do mês passado
        conn.execute("UPDATE time_entries SET work_date = ? WHERE id = ?", (previous.isoformat(), entry.id))
    finally:
        conn.close()
    bruno = Browser(server)
    bruno.get("/entrar")
    bruno.post("/entrar", {"login": "bruno", "senha": TEMP_PASSWORD})
    bruno.post("/trocar-senha", {"atual": TEMP_PASSWORD, "nova": "senha-do-bruno", "confirmacao": "senha-do-bruno"})
    _, _, body, _ = bruno.get(f"/apontamentos?mes={previous:%Y-%m}")
    assert "Lançado depois do mês" in body


def test_web_integrity_page(server, db):
    admin = _setup_admin(server)
    _, _, body, _ = admin.get("/auditoria")
    assert 'href="/auditoria/integridade"' in body
    _, _, body, _ = admin.get("/auditoria/integridade")
    assert "Íntegro:" in body and "registros conferidos" in body
    _, _, body, _ = admin.get("/auditoria/integridade?registro=1")
    assert "Registro <strong>#1</strong>: selo" in body
    _, _, body, _ = admin.get("/auditoria/integridade?registro=99999")
    assert "não existe" in body
    conn = db.connect()
    try:
        conn.execute("UPDATE audit_log SET actor_name = 'Outra pessoa' WHERE id = 1")
    finally:
        conn.close()
    _, _, body, _ = admin.get("/auditoria/integridade")
    assert "ALTERAÇÃO DETECTADA a partir do registro #1" in body


def test_web_integrity_is_admin_only(server, db):
    _with_collaborator_entry(server, db)
    bruno = Browser(server)
    bruno.get("/entrar")
    bruno.post("/entrar", {"login": "bruno", "senha": TEMP_PASSWORD})
    bruno.post("/trocar-senha", {"atual": TEMP_PASSWORD, "nova": "senha-do-bruno", "confirmacao": "senha-do-bruno"})
    status, _, _, _ = bruno.get("/auditoria/integridade")
    assert status == 403
    _, _, body, _ = bruno.get("/")
    assert "segundo responsável" not in body


def test_web_single_admin_notice(server):
    admin = _setup_admin(server)
    notice = "Cadastre um segundo responsável para não perder o acesso"
    assert notice in admin.get("/")[2]
    assert notice in admin.get("/usuarios")[2]
    admin.get("/usuarios/novo")
    admin.post("/usuarios/novo", {"nome": "Carla Responsável", "login": "carla", "papel": "admin",
                                  "senha": TEMP_PASSWORD})
    assert notice not in admin.get("/")[2]
    assert notice not in admin.get("/usuarios")[2]
