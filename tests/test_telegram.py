from datetime import date
from pathlib import Path

import httpx
import pytest

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.analysis import build_brief
from sunday_radar.db import Publication, create_db
from sunday_radar.settings import Settings
from sunday_radar.telegram import preview_text, send_preview

FIXTURE = Path(__file__).parent / "fixtures" / "morningnews"


def _settings(tmp_path: Path, *, credentials: bool) -> Settings:
    return Settings(
        project_root=tmp_path,
        morningnews_root=FIXTURE,
        bank_of_korea_cache_dir=tmp_path / "bok",
        database_path=tmp_path / "test.db",
        output_dir=tmp_path / "docs",
        public_base_url="https://example.test/radar",
        telegram_bot_token="token" if credentials else None,
        telegram_chat_id="chat" if credentials else None,
    )


def _publication_session(tmp_path: Path) -> tuple[object, object]:
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
    return brief, session


def test_preview_contains_fixed_url() -> None:
    brief = build_brief([load_day(FIXTURE, date(2026, 9, 28))], date(2026, 9, 28))
    text = preview_text(brief, "https://example.test/radar")
    assert "https://example.test/radar/issues/2026-09-28/" in text
    assert "Sunday Radar" in text


def test_send_requires_credentials_and_blocks_duplicates(tmp_path: Path) -> None:
    brief, session = _publication_session(tmp_path)
    settings = _settings(tmp_path, credentials=False)
    with pytest.raises(RuntimeError, match="required"):
        send_preview(session, settings, brief)
    publication = session.get(Publication, brief.week_ending)
    assert publication is not None
    publication.telegram_sent_at = brief.generated_at
    session.commit()
    with pytest.raises(RuntimeError, match="already sent"):
        send_preview(session, settings, brief)


def test_send_requires_built_publication(tmp_path: Path) -> None:
    brief = build_brief([load_day(FIXTURE, date(2026, 9, 28))], date(2026, 9, 28))
    _, session = create_db(tmp_path / "test.db")

    with pytest.raises(RuntimeError, match="Build the publication"):
        send_preview(session, _settings(tmp_path, credentials=True), brief)


def test_send_posts_preview_and_records_success(tmp_path: Path) -> None:
    brief, session = _publication_session(tmp_path)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        send_preview(
            session,
            _settings(tmp_path, credentials=True),
            brief,
            client=client,
        )

    assert len(requests) == 1
    assert requests[0].url.path == "/bottoken/sendMessage"
    payload = requests[0].read().decode()
    assert '"chat_id":"chat"' in payload
    assert "Sunday Radar" in payload
    publication = session.get(Publication, brief.week_ending)
    assert publication is not None
    assert publication.telegram_sent_at is not None


def test_send_failure_does_not_mark_publication_sent(tmp_path: Path) -> None:
    brief, session = _publication_session(tmp_path)
    transport = httpx.MockTransport(lambda request: httpx.Response(500, request=request))

    with httpx.Client(transport=transport) as client, pytest.raises(httpx.HTTPStatusError):
        send_preview(
            session,
            _settings(tmp_path, credentials=True),
            brief,
            client=client,
        )

    publication = session.get(Publication, brief.week_ending)
    assert publication is not None
    assert publication.telegram_sent_at is None


def test_force_allows_correction_notification(tmp_path: Path) -> None:
    brief, session = _publication_session(tmp_path)
    publication = session.get(Publication, brief.week_ending)
    assert publication is not None
    publication.telegram_sent_at = brief.generated_at
    session.commit()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, request=request))

    with httpx.Client(transport=transport) as client:
        send_preview(
            session,
            _settings(tmp_path, credentials=True),
            brief,
            force=True,
            client=client,
        )

    session.refresh(publication)
    assert publication.telegram_sent_at is not None
    assert publication.telegram_sent_at >= brief.generated_at
