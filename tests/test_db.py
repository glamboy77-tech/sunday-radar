from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.db import ArticleRow, SourceSnapshot, create_db, import_day

FIXTURE = Path(__file__).parent / "fixtures" / "morningnews"


def test_import_is_idempotent(tmp_path: Path) -> None:
    day = load_day(FIXTURE, date(2026, 9, 28))
    _, session = create_db(tmp_path / "test.db")
    assert import_day(session, day) is True
    assert import_day(session, day) is False
    assert session.scalar(select(func.count()).select_from(SourceSnapshot)) == 1
    assert session.scalar(select(func.count()).select_from(ArticleRow)) == 2
