from datetime import date
from pathlib import Path

from sunday_radar.adapters.morningnews import load_day

FIXTURE = Path(__file__).parent / "fixtures" / "morningnews"


def test_load_day_normalizes_and_deduplicates_articles() -> None:
    day = load_day(FIXTURE, date(2026, 9, 28))
    assert len(day.trends) == 2
    assert len(day.articles) == 2
    assert {article.url for article in day.articles} == {
        "https://example.com/rates",
        "https://example.com/home",
    }
    assert day.people == {"홍길동": "정부 관계자"}
