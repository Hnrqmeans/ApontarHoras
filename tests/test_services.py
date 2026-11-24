from datetime import UTC, datetime, timedelta

import pytest

from apontarhoras.domain.errors import AuthError, NotFound, PermissionDenied, ValidationError
from apontarhoras.domain.user import LOCK_DURATION, MAX_FAILED_ATTEMPTS, Role
from apontarhoras.services import audit, auth_service, projects_service, users_service
from tests.conftest import ADMIN_PASSWORD, TEMP_PASSWORD

# ---- primeiro acesso e login ---------------------------------------------------------------------------------


def test_setup_only_once(conn, admin):
    assert admin.role is Role.ADMIN
    assert not auth_service.needs_setup(conn)
    with pytest.raises(PermissionDenied):
        auth_service.setup_first_admin(conn, "Outro", "outro", "outra-senha-1")


def test_login_and_session(conn, admin):
    result = auth_service.login(conn, "ANA", ADMIN_PASSWORD)  # login não diferencia maiúsculas
    assert result.user.id == admin.id
    assert auth_service.user_for_token(conn, result.token).id == admin.id
    stored = conn.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert stored != result.token  # banco guarda só o hash
    auth_service.logout(conn, result.token)
    assert auth_service.user_for_token(conn, result.token) is None


def test_session_expires(conn, admin):
    now = datetime.now(UTC)
    result = auth_service.login(conn, "ana", ADMIN_PASSWORD, now=now)
    later = now + auth_service.SESSION_DURATION + timedelta(seconds=1)
    assert auth_service.user_for_token(conn, result.token, now=later) is None


def test_wrong_password_and_unknown_user_same_message(conn, admin):
    with pytest.raises(AuthError) as wrong:
        auth_service.login(conn, "ana", "errada-123")
    with pytest.raises(AuthError) as unknown:
        auth_service.login(conn, "ninguem", "errada-123")
    assert str(wrong.value) == str(unknown.value) == auth_service.INVALID_CREDENTIALS


def test_lockout_after_attempts_is_persisted(conn, admin):
    now = datetime.now(UTC)
    for _ in range(MAX_FAILED_ATTEMPTS):
        with pytest.raises(AuthError):
            auth_service.login(conn, "ana", "errada-123", now=now)
    # bloqueado até com a senha certa
    with pytest.raises(AuthError, match="bloqueado"):
        auth_service.login(conn, "ana", ADMIN_PASSWORD, now=now)
    # depois do prazo, entra
    auth_service.login(conn, "ana", ADMIN_PASSWORD, now=now + LOCK_DURATION + timedelta(seconds=1))
    actions = [entry.action for entry in audit.list_recent(conn, admin)]
    assert "locked" in actions


def test_inactive_user_cannot_login(conn, admin, collaborator):
    users_service.update_user(conn, admin, collaborator.id, name=collaborator.name, role="colaborador", active=False)
    with pytest.raises(AuthError, match="desativado"):
        auth_service.login(conn, "bruno", TEMP_PASSWORD)


def test_temporary_password_must_be_changed(conn, collaborator):
    assert collaborator.must_change_password
    result = auth_service.login(conn, "bruno", TEMP_PASSWORD)
    other = auth_service.login(conn, "bruno", TEMP_PASSWORD)
    with pytest.raises(ValidationError, match="atual está errada"):
        auth_service.change_password(conn, result.user, result.token, "errada", "nova-senha-1", "nova-senha-1")
    with pytest.raises(ValidationError, match="confirmação"):
        auth_service.change_password(conn, result.user, result.token, TEMP_PASSWORD, "nova-senha-1", "outra")
    auth_service.change_password(conn, result.user, result.token, TEMP_PASSWORD, "nova-senha-1", "nova-senha-1")
    assert not auth_service.user_for_token(conn, result.token).must_change_password
    assert auth_service.user_for_token(conn, other.token) is None  # outras sessões encerradas
    auth_service.login(conn, "bruno", "nova-senha-1")


# ---- usuários ------------------------------------------------------------------------------------------------


def test_collaborator_cannot_manage(conn, collaborator):
    with pytest.raises(PermissionDenied):
        users_service.list_users(conn, collaborator)
    with pytest.raises(PermissionDenied):
        users_service.create_user(conn, collaborator, name="X Y", login="xy", role="admin",
                                  temporary_password=TEMP_PASSWORD)
    with pytest.raises(PermissionDenied):
        projects_service.create_project(conn, collaborator, code="P1", name="Projeto")
    with pytest.raises(PermissionDenied):
        audit.list_recent(conn, collaborator)
    with pytest.raises(PermissionDenied):
        users_service.list_users(conn, None)


def test_duplicate_login(conn, admin, collaborator):
    with pytest.raises(ValidationError, match="Já existe"):
        users_service.create_user(conn, admin, name="Outro Bruno", login="Bruno", role="colaborador",
                                  temporary_password=TEMP_PASSWORD)


def test_admin_cannot_remove_own_access(conn, admin):
    with pytest.raises(ValidationError):
        users_service.update_user(conn, admin, admin.id, name=admin.name, role="colaborador", active=True)
    with pytest.raises(ValidationError):
        users_service.update_user(conn, admin, admin.id, name=admin.name, role="admin", active=False)
    with pytest.raises(ValidationError):
        users_service.delete_user(conn, admin, admin.id)


def test_admin_can_demote_other_admin(conn, admin):
    second = users_service.create_user(conn, admin, name="Carla Admin", login="carla", role="admin",
                                       temporary_password=TEMP_PASSWORD)
    users_service.update_user(conn, second, admin.id, name=admin.name, role="colaborador", active=True)
    demoted = users_service.get_user(conn, second, admin.id)
    assert not demoted.is_admin
    with pytest.raises(PermissionDenied):
        users_service.delete_user(conn, demoted, second.id)


def test_update_and_audit_diff(conn, admin, collaborator):
    users_service.update_user(conn, admin, collaborator.id, name="Bruno Souza", role="colaborador", active=True)
    entry = audit.list_recent(conn, admin)[0]
    assert entry.action == "update"
    assert entry.details == {"nome": ["Bruno Colaborador", "Bruno Souza"]}


def test_deactivating_ends_sessions(conn, admin, collaborator):
    session = auth_service.login(conn, "bruno", TEMP_PASSWORD)
    users_service.update_user(conn, admin, collaborator.id, name=collaborator.name, role="colaborador", active=False)
    assert auth_service.user_for_token(conn, session.token) is None


def test_reset_password_unlocks_and_forces_change(conn, admin, collaborator):
    for _ in range(MAX_FAILED_ATTEMPTS):
        with pytest.raises(AuthError):
            auth_service.login(conn, "bruno", "errada-123")
    users_service.reset_password(conn, admin, collaborator.id, "nova-temporaria-1")
    result = auth_service.login(conn, "bruno", "nova-temporaria-1")
    assert result.user.must_change_password
    details = str([e.details for e in audit.list_recent(conn, admin)])
    assert "nova-temporaria-1" not in details  # senha nunca vai para a auditoria


def test_delete_user(conn, admin, collaborator):
    users_service.delete_user(conn, admin, collaborator.id)
    with pytest.raises(NotFound):
        users_service.get_user(conn, admin, collaborator.id)
    entry = audit.list_recent(conn, admin)[0]
    assert (entry.action, entry.details["login"]) == ("delete", "bruno")


# ---- projetos ------------------------------------------------------------------------------------------------


def test_projects_crud_and_visibility(conn, admin, collaborator):
    project = projects_service.create_project(conn, admin, code="pd-01", name="Sensor novo", description="Objetivo")
    assert project.code == "PD-01"
    with pytest.raises(ValidationError, match="Já existe"):
        projects_service.create_project(conn, admin, code="PD-01", name="Outro")
    other = projects_service.create_project(conn, admin, code="PD-02", name="Outro projeto")
    projects_service.update_project(conn, admin, other.id, code="PD-02", name="Outro projeto", description="",
                                    active=False)
    assert [p.code for p in projects_service.list_projects(conn, collaborator)] == ["PD-01"]
    # colaborador não vê inativos nem pedindo
    assert len(projects_service.list_projects(conn, collaborator, include_inactive=True)) == 1
    assert len(projects_service.list_projects(conn, admin, include_inactive=True)) == 2
    projects_service.delete_project(conn, admin, other.id)
    with pytest.raises(NotFound):
        projects_service.get_project(conn, admin, other.id)
