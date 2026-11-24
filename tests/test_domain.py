from datetime import UTC, datetime

import pytest

from apontarhoras.auth.passwords import hash_password, verify_password
from apontarhoras.auth.tokens import csrf_for, csrf_matches, new_token, token_hash
from apontarhoras.domain.audit import changes
from apontarhoras.domain.duration import format_minutes, parse_duration
from apontarhoras.domain.errors import ValidationError
from apontarhoras.domain.project import normalize_code, validate_code
from apontarhoras.domain.user import (
    LOCK_DURATION,
    MAX_FAILED_ATTEMPTS,
    after_failed_attempt,
    normalize_login,
    validate_login,
    validate_password,
)

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("minutes", "text"), [(0, "0:00"), (5, "0:05"), (480, "8:00"), (1530, "25:30"), (-90, "-1:30")]
)
def test_format_minutes(minutes, text):
    assert format_minutes(minutes) == text


@pytest.mark.parametrize(
    ("text", "minutes"),
    [("8", 480), ("8:30", 510), ("8h", 480), ("8h30", 510), ("8,5", 510), ("8.25", 495), (" 1:05 ", 65), ("24", 1440)],
)
def test_parse_duration(text, minutes):
    assert parse_duration(text) == minutes


@pytest.mark.parametrize("text", ["", "abc", "8:60", "0", "0:00", "25", "8,33", "-1", "8:5"])
def test_parse_duration_rejects(text):
    with pytest.raises(ValidationError):
        parse_duration(text)


def test_login_rules():
    assert normalize_login("  Maria.Silva ") == "maria.silva"
    validate_login("maria.silva")
    for bad in ["ab", "maria silva", "joão", ".maria", "a" * 33]:
        with pytest.raises(ValidationError):
            validate_login(bad)


def test_password_rules():
    validate_password("12345678")
    with pytest.raises(ValidationError):
        validate_password("1234567")
    with pytest.raises(ValidationError):
        validate_password("maria.silva", "maria.silva")


def test_lock_after_max_attempts():
    attempts, locked = 0, None
    for _ in range(MAX_FAILED_ATTEMPTS - 1):
        attempts, locked = after_failed_attempt(attempts, NOW)
        assert locked is None
    attempts, locked = after_failed_attempt(attempts, NOW)
    assert attempts == 0
    assert locked == NOW + LOCK_DURATION


def test_project_code():
    assert normalize_code(" pd-2026-01 ") == "PD-2026-01"
    validate_code("PD-2026-01")
    with pytest.raises(ValidationError):
        validate_code("COM ESPAÇO")


def test_password_hash_roundtrip():
    stored = hash_password("minha senha segura")
    assert "minha senha" not in stored
    assert verify_password("minha senha segura", stored)
    assert not verify_password("outra", stored)
    assert not verify_password("x", "lixo")
    assert hash_password("igual") != hash_password("igual")  # sal diferente


def test_tokens():
    token = new_token()
    assert token_hash(token) != token
    assert csrf_matches(token, csrf_for(token))
    assert not csrf_matches(token, csrf_for(new_token()))


def test_changes_only_diff():
    assert changes({"a": 1, "b": 2}, {"a": 1, "b": 3}) == {"b": [2, 3]}
