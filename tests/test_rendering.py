import re
import shutil
from datetime import date
from pathlib import Path

import pytest

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.analysis import build_brief
from sunday_radar.domain import EditorialDraft
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
    assert "OFFICIAL DESK" not in html
    assert "첫 번째 장면" in html
    assert "함께 읽을 자료" in html
    assert "연결 영역" not in html
    assert "이렇게 연결됩니다" not in html
    assert "다음 가능성" not in html
    assert "<details" not in html
    if len(brief.issues) > 1:
        assert "story-transition" in html
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


def test_render_site_uses_validated_editorial_copy(tmp_path: Path) -> None:
    brief = build_brief([load_day(FIXTURE, date(2026, 9, 28))], date(2026, 9, 28))
    editorial = EditorialDraft.model_validate(
        {
            "headline": "LLM이 다듬은 이번 주의 새로운 제목",
            "overview": (
                "선택된 기사와 근거 범위 안에서 이번 주의 흐름을 자연스러운 이야기로 "
                "다시 구성했습니다."
            ),
            "sections": [
                {
                    "issue_id": issue.issue_id,
                    "heading": f"새롭게 다듬은 장면 {index}",
                    "paragraphs": [
                        {
                            "kind": "fact",
                            "text": (
                                "근거 기사에서 확인할 수 있는 이번 주의 핵심 사실을 먼저 "
                                "설명합니다."
                            ),
                            "source_ids": [f"{issue.issue_id}-source-1"],
                        },
                        {
                            "kind": "interpretation",
                            "text": (
                                "이 사실이 시장과 생활에 어떤 질문을 남기는지 이어서 살펴봅니다."
                            ),
                            "source_ids": [],
                        },
                    ],
                }
                for index, issue in enumerate(brief.issues, start=1)
            ],
            "transitions": [
                "이제 같은 흐름의 다음 장면으로 자연스럽게 이동합니다."
                for _ in range(max(0, len(brief.issues) - 1))
            ],
            "conclusion": (
                "다음 주에는 후속 보도와 실제 지표를 함께 확인하며 이 흐름이 이어지는지 "
                "살펴봐야 합니다."
            ),
        }
    )

    issue_path = render_site(brief, tmp_path, ROOT / "templates", editorial)
    html = issue_path.read_text(encoding="utf-8")

    assert editorial.headline in html
    assert editorial.sections[0].heading in html
    assert editorial.conclusion in html
    assert content_hash(brief, editorial) != content_hash(brief)


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
