from datetime import date, datetime
from pathlib import Path

from sunday_radar.cli import _editorial_dates, _parse_date, _publication_is_current, _target_date
from sunday_radar.db import Publication
from sunday_radar.domain import SourceDay


def test_explicit_target_date_is_preserved() -> None:
    assert _target_date("2026-09-27") == date(2026, 9, 27)
    assert _parse_date("2026-09-27") == date(2026, 9, 27)


def test_editorial_dates_exclude_official_only_dates() -> None:
    days = [
        SourceDay(
            source_kind="bank_of_korea",
            report_date=date(2026, 9, 22),
            files=[Path("bok.json")],
            articles=[],
            trends=[],
        ),
        SourceDay(
            source_kind="morningnews",
            report_date=date(2026, 9, 23),
            files=[Path("morning.json")],
            articles=[],
            trends=[],
        ),
    ]

    assert _editorial_dates(days) == {date(2026, 9, 23)}


def test_publication_is_current_only_for_valid_existing_output(tmp_path: Path) -> None:
    target = date(2026, 9, 27)
    publication = Publication(
        week_ending=target,
        content_hash="digest",
        status="generated",
        generated_at=datetime(2026, 9, 27),
    )
    output_dir = tmp_path / "docs"
    issue_dir = output_dir / "issues" / target.isoformat()
    issue_dir.mkdir(parents=True)
    html = (
        '<html lang="ko"><head><title>Sunday Radar</title>'
        '<meta name="viewport" content="width=device-width"></head>'
        "<body><h1>Sunday Radar</h1></body></html>"
    )
    (issue_dir / "index.html").write_text(html, encoding="utf-8")
    (output_dir / "index.html").write_text(html, encoding="utf-8")

    assert _publication_is_current(publication, "digest", output_dir, target)
    assert not _publication_is_current(publication, "changed", output_dir, target)
    (output_dir / "index.html").write_text("broken", encoding="utf-8")
    assert not _publication_is_current(publication, "digest", output_dir, target)
