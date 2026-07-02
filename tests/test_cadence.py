import pytest

from scripts.cadence import is_due


def test_hourly_always_due():
    assert all(is_due("hourly", h) for h in range(24))


def test_every_2h_even_hours_only():
    assert is_due("every_2h", 0) and is_due("every_2h", 14)
    assert not is_due("every_2h", 13)


def test_every_4h_hours():
    assert is_due("every_4h", 0) and is_due("every_4h", 16)
    assert not is_due("every_4h", 3) and not is_due("every_4h", 22 + 1)


def test_daily_midnight_only():
    assert is_due("daily", 0)
    assert not any(is_due("daily", h) for h in range(1, 24))


def test_unknown_cadence_raises():
    with pytest.raises(ValueError):
        is_due("weekly", 0)
