import re
import shutil
from datetime import date
from pathlib import Path

import pytest

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.analysis import build_brief
from sunday_radar.rendering import RenderValidationError, check_html, content_hash, render_site

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
    html = issue.read_text(encoding="utf-8")
    assert "이번 주의 이야기" in html
    assert brief.headline in html
    assert "EDITOR'S NOTE" in html
    assert "OFFICIAL DESK" not in html
    assert "첫 번째 장면" in html
    assert "이야기 시작하기" in html
    if len(brief.issues) > 1:
        assert "story-bridge" in html
    assert re.search(r"RADAR\s+\d", html) is None
    assert "#rates" not in html
    assert content_hash(brief) == content_hash(brief.model_copy())


def test_html_checker_rejects_unsafe_links(tmp_path: Path) -> None:
    path = tmp_path / "bad.html"
    path.write_text(
        '<html lang="ko"><head><meta name="viewport" content="width=device-width">'
        '</head><body><h1>Bad</h1><a href="javascript:alert(1)">bad</a></body></html>',
        encoding="utf-8",
    )
    assert any("unsafe link" in error for error in check_html(tmp_path))


def test_html_checker_rejects_missing_title_targets_and_fragments(tmp_path: Path) -> None:
    path = tmp_path / "index.html"
    path.write_text(
        '<html lang="ko"><head><meta name="viewport" content="width=device-width">'
        '</head><body><h1>Bad</h1><a href="missing.html">missing</a>'
        '<a href="#missing">fragment</a><link rel="stylesheet" href="missing.css">'
        "</body></html>",
        encoding="utf-8",
    )

    errors = check_html(tmp_path)

    assert any("missing title" in error for error in errors)
    assert any("missing local target missing.html" in error for error in errors)
    assert any("missing fragment target #missing" in error for error in errors)
    assert any("missing local target missing.css" in error for error in errors)


def test_render_site_preserves_existing_output_when_validation_fails(tmp_path: Path) -> None:
    output_dir = tmp_path / "docs"
    output_dir.mkdir()
    marker = output_dir / "existing.txt"
    marker.write_text("published", encoding="utf-8")
    template_dir = tmp_path / "templates"
    shutil.copytree(ROOT / "templates", template_dir)
    template = template_dir / "issue.html.j2"
    template.write_text(
        template.read_text(encoding="utf-8").replace(
            "<title>Sunday Radar — {{ brief.week_ending }}</title>", ""
        ),
        encoding="utf-8",
    )
    brief = build_brief([load_day(FIXTURE, date(2026, 9, 28))], date(2026, 9, 28))

    with pytest.raises(RenderValidationError, match="missing title"):
        render_site(brief, output_dir, template_dir)

    assert marker.read_text(encoding="utf-8") == "published"
    assert not (output_dir / "index.html").exists()
