"""Regras puras do apontamento (portadas do VBA da planilha antiga) e da jornada."""

from datetime import date

import pytest

from apontarhoras.domain.errors import ValidationError
from apontarhoras.domain.time_entry import (
    LunchChoice,
    compute_minutes,
    format_clock,
    overlaps,
    parse_clock,
    parse_lunch,
    parse_month,
    parse_work_date,
    shift_month,
    spans_lunch,
    validate_description,
)
from apontarhoras.domain.workday import DayStatus, day_status, expected_minutes


@pytest.mark.parametrize(
    ("text", "minutes"),
    [("7", 420), ("07", 420), ("730", 450), ("0730", 450), ("7:30", 450), ("07:30", 450), ("7:", 420),
     ("7h30", 450), (" 16:30 ", 990), ("0", 0), ("23:59", 1439)],
)
def test_parse_clock_accepts_spreadsheet_formats(text, minutes):
    assert parse_clock(text) == minutes


@pytest.mark.parametrize("text", ["", "24", "7:60", "12345", "7:300", "a", "7:30:00", "-1", "7.30"])
def test_parse_clock_rejects(text):
    with pytest.raises(ValidationError):
        parse_clock(text)


def test_format_clock():
    assert format_clock(450) == "07:30"
    assert format_clock(0) == "00:00"


def test_spans_lunch_only_when_covers_12_to_13():
    assert spans_lunch(parse_clock("7"), parse_clock("16:30"))
    assert spans_lunch(parse_clock("10:40"), parse_clock("13:25"))
    assert not spans_lunch(parse_clock("7"), parse_clock("12"))  # termina no almoço
    assert not spans_lunch(parse_clock("13"), parse_clock("17"))
    assert not spans_lunch(parse_clock("11"), parse_clock("13"))  # termina exatamente às 13:00


def test_compute_minutes_with_lunch_choices():
    start, end = parse_clock("7"), parse_clock("16:30")
    assert compute_minutes(start, end, LunchChoice.DEDUCT) == (60, 510)  # 8h30, como na planilha
    assert compute_minutes(start, end, LunchChoice.NO_BREAK) == (0, 570)
    with pytest.raises(ValidationError, match="almoço"):
        compute_minutes(start, end, LunchChoice.NOT_ASKED)
    # fora do almoço a escolha é ignorada
    assert compute_minutes(parse_clock("7"), parse_clock("12"), LunchChoice.DEDUCT) == (0, 300)


def test_compute_minutes_requires_end_after_start():
    with pytest.raises(ValidationError, match="término"):
        compute_minutes(600, 600, LunchChoice.NOT_ASKED)
    with pytest.raises(ValidationError):
        compute_minutes(600, 500, LunchChoice.NOT_ASKED)


def test_parse_lunch():
    assert parse_lunch("") is LunchChoice.NOT_ASKED
    assert parse_lunch("descontar") is LunchChoice.DEDUCT
    with pytest.raises(ValidationError):
        parse_lunch("talvez")


def test_parse_work_date_rejects_future_and_garbage():
    today = date(2026, 11, 24)
    assert parse_work_date("2026-11-24", today) == today
    with pytest.raises(ValidationError, match="futura"):
        parse_work_date("2026-11-25", today)
    with pytest.raises(ValidationError, match="inválida"):
        parse_work_date("24/11/2026", today)


def test_description_required_only_for_lei_do_bem():
    validate_description("", rd_eligible=False)
    validate_description("Ajuste do PID", rd_eligible=True)
    with pytest.raises(ValidationError, match="Lei do Bem"):
        validate_description("", rd_eligible=True)
    with pytest.raises(ValidationError, match="1000"):
        validate_description("x" * 1001, rd_eligible=False)


def test_overlaps():
    assert overlaps(420, 720, 600, 660)
    assert not overlaps(420, 720, 720, 780)  # encostado não sobrepõe
    assert not overlaps(780, 900, 420, 720)


def test_month_helpers():
    today = date(2026, 11, 24)
    assert parse_month("2026-02", today) == (2026, 2)
    assert parse_month("2026-13", today) == (2026, 11)
    assert parse_month(None, today) == (2026, 11)
    assert shift_month(2026, 1, -1) == (2025, 12)
    assert shift_month(2026, 12, 1) == (2027, 1)


def test_workday_expected_and_status():
    assert expected_minutes(date(2026, 11, 23)) == 507  # segunda: 8h27
    assert expected_minutes(date(2026, 11, 27)) == 462  # sexta: 7h42
    assert expected_minutes(date(2026, 11, 28)) == 0  # sábado
    assert day_status(507, 507) is DayStatus.OK
    assert day_status(0, 507) is DayStatus.MISSING
    assert day_status(600, 507) is DayStatus.EXCESS
    assert day_status(120, 0) is DayStatus.NOT_WORKDAY
