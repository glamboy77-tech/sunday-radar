from datetime import date
from pathlib import Path

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.analysis import build_brief
from sunday_radar.rendering import check_html, content_hash, render_site

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "morningnews"


def test_render_site_and_html_checks(tmp_path: Path) -> None:
    brief = build_brief([load_day(FIXTURE, date(2026, 9, 28))], date(2026, 9, 28))
    issue = render_site(brief, tmp_path, ROOT / "templates")
    assert issue.exists()
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "archive.html").exists()
    assert check_html(tmp_path) == []
    assert "javascript:" not in issue.read_text(encoding="utf-8")
    assert content_hash(brief) == content_hash(brief.model_copy())


def test_html_checker_rejects_unsafe_links(tmp_path: Path) -> None:
    path = tmp_path / "bad.html"
    path.write_text(
        '<html lang="ko"><head><meta name="viewport" content="width=device-width">'
        '</head><body><h1>Bad</h1><a href="javascript:alert(1)">bad</a></body></html>',
        encoding="utf-8",
    )
    assert any("unsafe link" in error for error in check_html(tmp_path))
