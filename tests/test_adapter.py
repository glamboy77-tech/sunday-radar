from datetime import date
from pathlib import Path

import httpx

from sunday_radar.adapters.bank_of_korea import collect_window, parse_feed
from sunday_radar.adapters.bank_of_korea import load_day as load_bok_day
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
    assert day.person_article_ids == {}
    assert day.source_kind == "morningnews"
    assert {article.source_kind for article in day.articles} == {"morningnews"}


def test_load_day_preserves_key_person_articles_as_evidence(tmp_path: Path) -> None:
    cache_dir = tmp_path / "data_cache"
    cache_dir.mkdir()
    (cache_dir / "key_persons_20260929.json").write_text(
        """{
  "data": {
    "김가람": {
      "role": "아르카디아 대통령",
      "articles": [{
        "title": "김가람 대통령, 핵심 연료 수출금지 명령",
        "link": "https://example.com/power-move",
        "source": "테스트통신",
        "description": "김가람 대통령이 수출금지 행정명령에 서명했다."
      }]
    }
  }
} """,
        encoding="utf-8",
    )

    day = load_day(tmp_path, date(2026, 9, 29))

    assert day.people == {"김가람": "아르카디아 대통령"}
    assert len(day.articles) == 1
    assert day.person_article_ids == {"김가람": [day.articles[0].stable_id]}


BOK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>한국은행</title>
<item><title>[보도자료] 2026년 9월 소비자동향조사 결과</title>
<link>https://www.bok.or.kr/example?nttId=1&amp;menuNo=200690</link>
<description>&lt;p&gt;□ 소비자들 의 경제상황을 나타내는 소비자심리지수는
106.6으 로 전월 대비 2.1 p 상승
※ 자세한 내용은 첨부파일을 참조하시기 바랍니다.&lt;/p&gt;</description>
<pubDate>Mon, 28 Sep 2026 06:00:00 +0900</pubDate></item>
<item><title>[보도참고자료] 기준금리 관련 자료</title>
<link>https://www.bok.or.kr/rates?nttId=2</link>
<description>&lt;p&gt;기준금리 관련 공식 자료입니다.&lt;/p&gt;</description>
<pubDate>Sun, 27 Sep 2026 12:00:00 +0900</pubDate></item>
</channel></rss>"""


def test_bank_of_korea_feed_is_cached_and_loaded(tmp_path: Path) -> None:
    releases = parse_feed(BOK_RSS)
    assert [item.title for item in releases] == [
        "기준금리 관련 자료",
        "2026년 9월 소비자동향조사 결과",
    ]
    assert releases[1].description == (
        "소비자들의 경제상황을 나타내는 소비자심리지수는 106.6으로 전월 대비 2.1p 상승"
    )

    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=BOK_RSS))
    with httpx.Client(transport=transport) as client:
        paths = collect_window(tmp_path, date(2026, 9, 28), client=client)

    assert [path.name for path in paths] == ["releases_20260927.json", "releases_20260928.json"]
    day = load_bok_day(tmp_path, date(2026, 9, 28))
    assert day.source_kind == "bank_of_korea"
    assert len(day.articles) == 1
    assert day.articles[0].source == "한국은행"
    assert day.trends[0].source_kind == "bank_of_korea"


def test_bank_of_korea_load_cleans_existing_cached_descriptions(tmp_path: Path) -> None:
    path = tmp_path / "releases_20260928.json"
    path.write_text(
        """{
  "data": [{
    "title": "산업연관표 작성 결과",
    "link": "https://www.bok.or.kr/example?nttId=3",
    "description": "□ 자세한 내용은 붙임 참조",
    "published_at": "2026-09-28T12:00:00+09:00"
  }]
}
""",
        encoding="utf-8",
    )

    day = load_bok_day(tmp_path, date(2026, 9, 28))

    assert day.articles[0].description == ""
    assert day.trends[0].reason == "한국은행이 「산업연관표 작성 결과」 자료를 발표했습니다."
