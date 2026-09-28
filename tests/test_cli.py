from datetime import date

from sunday_radar.cli import _parse_date, _target_date


def test_explicit_target_date_is_preserved() -> None:
    assert _target_date("2026-09-27") == date(2026, 9, 27)
    assert _parse_date("2026-09-27") == date(2026, 9, 27)
