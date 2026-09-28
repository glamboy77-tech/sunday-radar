from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.db import ArticleRow, SourceSnapshot, create_db, import_day, import_days
from sunday_radar.domain import SourceDay, TrendSignal

FIXTURE = Path(__file__).parent / "fixtures" / "morningnews"


def test_import_is_idempotent(tmp_path: Path) -> None:
    day = load_day(FIXTURE, date(2026, 9, 28))
    _, session = create_db(tmp_path / "test.db")
    assert import_day(session, day) is True
    session.commit()
    assert import_day(session, day) is False
    assert session.scalar(select(func.count()).select_from(SourceSnapshot)) == 1
    assert session.scalar(select(func.count()).select_from(ArticleRow)) == 2


def test_import_keeps_separate_source_snapshots_for_same_date(tmp_path: Path) -> None:
    morning = load_day(FIXTURE, date(2026, 9, 28))
    official = SourceDay(
        source_kind="bank_of_korea",
        report_date=morning.report_date,
        files=morning.files,
        articles=morning.articles,
        trends=morning.trends,
    )
    _, session = create_db(tmp_path / "test.db")
    assert import_day(session, morning) is True
    assert import_day(session, official) is True
    session.commit()
    kinds = session.scalars(select(SourceSnapshot.source_kind).order_by(SourceSnapshot.source_kind))
    assert list(kinds) == ["bank_of_korea", "morningnews"]


def test_import_days_rolls_back_the_whole_window_on_failure(tmp_path: Path) -> None:
    valid = load_day(FIXTURE, date(2026, 9, 28))
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{}", encoding="utf-8")
    invalid = SourceDay(
        source_kind="bank_of_korea",
        report_date=date(2026, 9, 27),
        files=[invalid_file],
        articles=[],
        trends=[
            TrendSignal(keyword="기준금리", report_date=date(2026, 9, 27)),
            TrendSignal(keyword="기준금리", report_date=date(2026, 9, 27)),
        ],
    )
    _, session = create_db(tmp_path / "test.db")

    with pytest.raises(IntegrityError):
        import_days(session, [valid, invalid])

    assert session.scalar(select(func.count()).select_from(SourceSnapshot)) == 0
    assert session.scalar(select(func.count()).select_from(ArticleRow)) == 0
