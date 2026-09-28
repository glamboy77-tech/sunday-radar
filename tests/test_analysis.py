from datetime import date
from pathlib import Path

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.analysis import build_brief
from sunday_radar.domain import Article, SourceDay, TrendSignal

FIXTURE = Path(__file__).parent / "fixtures" / "morningnews"


def _source_day(
    source_kind: str,
    report_date: date,
    keyword: str,
    article_id: str,
    *,
    title: str | None = None,
    reason: str = "관련 자료가 발표됐습니다.",
) -> SourceDay:
    source_name = "한국은행" if source_kind == "bank_of_korea" else "테스트경제"
    article = Article(
        stable_id=article_id,
        title=title or keyword,
        url=f"https://example.com/{article_id}",
        source=source_name,
        report_date=report_date,
        source_kind=source_kind,
    )
    return SourceDay(
        source_kind=source_kind,
        report_date=report_date,
        files=[Path(f"{article_id}.json")],
        articles=[article],
        trends=[
            TrendSignal(
                keyword=keyword,
                reason=reason,
                score=30 if source_kind == "morningnews" else 20,
                categories=["경제/거시"],
                report_date=report_date,
                article_ids=[article_id],
                source_kind=source_kind,
            )
        ],
    )


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


def test_brief_accepts_official_source_and_counts_unique_dates() -> None:
    report_date = date(2026, 9, 28)
    article = Article(
        stable_id="bok-1",
        title="기준금리 관련 공식 자료",
        url="https://www.bok.or.kr/rates",
        source="한국은행",
        report_date=report_date,
        source_kind="bank_of_korea",
    )
    official = SourceDay(
        source_kind="bank_of_korea",
        report_date=report_date,
        files=[Path("bok.json")],
        articles=[article],
        trends=[
            TrendSignal(
                keyword="기준금리 전망",
                reason="한국은행이 기준금리 관련 공식 자료를 발표했습니다.",
                score=20,
                categories=["경제/거시"],
                report_date=report_date,
                article_ids=[article.stable_id],
                source_kind="bank_of_korea",
            )
        ],
    )
    morning = load_day(FIXTURE, report_date)
    brief = build_brief([morning, official], report_date)
    assert brief.input_days == [report_date]
    assert brief.source_kinds == ["bank_of_korea", "morningnews"]
    official_issue = next(
        issue for issue in brief.official_updates if issue.title.startswith("기준금리")
    )
    assert "official_claim" in {block.kind.value for block in official_issue.blocks}
    assert "한국은행 공식 자료" in brief.methodology_note


def test_exact_official_topic_enriches_one_editorial_issue_without_changing_rank() -> None:
    report_date = date(2026, 9, 28)
    morning = _source_day(
        "morningnews",
        report_date,
        "기준금리 결정",
        "morning-rate",
        reason="금융통화위원회의 기준금리 결정이 주목받았습니다.",
    )
    official = _source_day(
        "bank_of_korea",
        report_date,
        "통화정책방향 기준금리 결정",
        "bok-rate",
        reason="한국은행은 기준금리를 동결했습니다.",
    )

    baseline = build_brief([morning], report_date).issues[0]
    enriched_brief = build_brief([official, morning], report_date)
    enriched = enriched_brief.issues[0]

    assert enriched.title == baseline.title
    assert enriched.issue_id == baseline.issue_id
    assert enriched.score == baseline.score
    assert enriched.active_days == baseline.active_days
    assert {source.source_kind for source in enriched.sources} == {
        "bank_of_korea",
        "morningnews",
    }
    assert "official_claim" in {block.kind.value for block in enriched.blocks}
    assert enriched_brief.official_updates == []


def test_ambiguous_official_topic_stays_in_official_desk() -> None:
    report_date = date(2026, 9, 28)
    first = _source_day("morningnews", report_date, "기준금리 결정", "morning-rate")
    second = _source_day("morningnews", report_date, "통화정책방향 점검", "morning-policy")
    official = _source_day(
        "bank_of_korea",
        report_date,
        "기준금리 통화정책방향",
        "bok-rate",
    )

    brief = build_brief([first, official, second], report_date)

    assert [issue.title for issue in brief.official_updates] == ["기준금리 통화정책방향"]
    assert all(
        "bank_of_korea" not in {source.source_kind for source in issue.sources}
        for issue in brief.issues
    )


def test_official_enrichment_is_deterministic_across_input_order() -> None:
    report_date = date(2026, 9, 28)
    morning = _source_day("morningnews", report_date, "소비자심리지수", "morning-ccsi")
    official = _source_day("bank_of_korea", report_date, "소비자동향조사 결과", "bok-ccsi")

    first = build_brief([morning, official], report_date)
    second = build_brief([official, morning], report_date)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_source_limit_keeps_editorial_and_official_links() -> None:
    report_date = date(2026, 9, 28)
    morning = _source_day("morningnews", report_date, "가계신용 증가", "morning-main")
    for index in range(4):
        article_id = f"morning-extra-{index}"
        morning.articles.append(
            Article(
                stable_id=article_id,
                title=f"가계신용 기사 {index}",
                url=f"https://example.com/{article_id}",
                source="테스트경제",
                report_date=report_date,
                source_kind="morningnews",
            )
        )
        morning.trends[0].article_ids.append(article_id)
    official = _source_day("bank_of_korea", report_date, "가계신용 통계", "zz-official-credit")

    issue = build_brief([morning, official], report_date).issues[0]

    assert len(issue.sources) == 4
    assert {source.source_kind for source in issue.sources} == {
        "bank_of_korea",
        "morningnews",
    }


def test_unrelated_official_source_is_kept_in_official_desk() -> None:
    report_date = date(2026, 9, 28)
    article = Article(
        stable_id="bok-stability",
        title="금융안정 상황",
        url="https://www.bok.or.kr/stability",
        source="한국은행",
        report_date=report_date,
        source_kind="bank_of_korea",
    )
    official = SourceDay(
        source_kind="bank_of_korea",
        report_date=report_date,
        files=[Path("bok.json")],
        articles=[article],
        trends=[
            TrendSignal(
                keyword="금융안정 상황",
                reason="한국은행이 금융안정 상황을 발표했습니다.",
                score=20,
                categories=["경제/거시"],
                report_date=report_date,
                article_ids=[article.stable_id],
                source_kind="bank_of_korea",
            )
        ],
    )
    brief = build_brief([load_day(FIXTURE, report_date), official], report_date)
    assert [issue.title for issue in brief.official_updates] == ["금융안정 상황"]
    assert all(issue.title != "금융안정 상황" for issue in brief.issues)


def test_official_releases_do_not_merge_on_generic_date_words() -> None:
    first = _source_day(
        "bank_of_korea",
        date(2026, 9, 22),
        "2026년 9월 금융안정 상황",
        "bok-stability",
    )
    second = _source_day(
        "bank_of_korea",
        date(2026, 9, 23),
        "2026년 9월 소비자동향조사 결과",
        "bok-consumer",
    )

    brief = build_brief([first, second], date(2026, 9, 23))

    assert {issue.title for issue in brief.official_updates} == {
        "2026년 9월 금융안정 상황",
        "2026년 9월 소비자동향조사 결과",
    }
    assert all(issue.active_days == 1 for issue in brief.official_updates)


def test_brief_coverage_uses_only_morning_news_dates() -> None:
    morning = _source_day("morningnews", date(2026, 9, 23), "기준금리 결정", "morning-rate")
    official = _source_day("bank_of_korea", date(2026, 9, 22), "금융안정 상황", "bok-stability")

    brief = build_brief([official, morning], date(2026, 9, 23))

    assert brief.input_days == [date(2026, 9, 23)]
    assert date(2026, 9, 22) in brief.missing_days
