from datetime import date
from pathlib import Path

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.analysis import build_brief

FIXTURE = Path(__file__).parent / "fixtures" / "morningnews"


def test_build_brief_separates_evidence_and_extracts_domains() -> None:
    day = load_day(FIXTURE, date(2026, 9, 28))
    brief = build_brief([day], date(2026, 9, 28))
    assert brief.issues
    rates = next(issue for issue in brief.issues if issue.title.startswith("국채 금리"))
    assert {block.kind.value for block in rates.blocks} == {"fact", "interpretation", "scenario"}
    assert {"rates", "fx"}.issubset(rates.entities.market_domains)
    assert rates.active_days == 1
    assert len(brief.issues) <= 3
    assert all(issue.entities.market_domains for issue in brief.issues)
    assert brief.headline != brief.issues[0].title
    assert brief.issues[0].title in brief.overview
    assert brief.issues[0].category == "경제/거시"


def test_single_token_title_uses_reason_for_context() -> None:
    day = load_day(FIXTURE, date(2026, 9, 28))
    brief = build_brief([day], date(2026, 9, 28))
    assert all(issue.title != "국채" for issue in brief.issues)
