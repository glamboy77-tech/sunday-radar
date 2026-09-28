from datetime import date
from pathlib import Path

import pytest

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.analysis import build_brief
from sunday_radar.db import Publication, create_db
from sunday_radar.settings import Settings
from sunday_radar.telegram import preview_text, send_preview

FIXTURE = Path(__file__).parent / "fixtures" / "morningnews"


def test_preview_contains_fixed_url() -> None:
    brief = build_brief([load_day(FIXTURE, date(2026, 9, 28))], date(2026, 9, 28))
    text = preview_text(brief, "https://example.test/radar")
    assert "https://example.test/radar/issues/2026-09-28/" in text
    assert "Sunday Radar" in text


def test_send_requires_credentials_and_blocks_duplicates(tmp_path: Path) -> None:
    brief = build_brief([load_day(FIXTURE, date(2026, 9, 28))], date(2026, 9, 28))
    _, session = create_db(tmp_path / "test.db")
    session.add(
        Publication(
            week_ending=brief.week_ending,
            content_hash="abc",
            status="generated",
            generated_at=brief.generated_at,
        )
    )
    session.commit()
    settings = Settings(
        project_root=tmp_path,
        morningnews_root=FIXTURE,
        database_path=tmp_path / "test.db",
        output_dir=tmp_path / "docs",
        public_base_url="https://example.test/radar",
        telegram_bot_token=None,
        telegram_chat_id=None,
    )
    with pytest.raises(RuntimeError, match="required"):
        send_preview(session, settings, brief)
    publication = session.get(Publication, brief.week_ending)
    assert publication is not None
    publication.telegram_sent_at = brief.generated_at
    session.commit()
    with pytest.raises(RuntimeError, match="already sent"):
        send_preview(session, settings, brief)
