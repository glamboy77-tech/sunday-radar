from datetime import date
from pathlib import Path

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.analysis import build_brief
from sunday_radar.domain import Article, EditorialLens, SourceDay, TrendSignal

FIXTURE = Path(__file__).parent / "fixtures" / "morningnews"


def _source_day(
    source_kind: str,
    report_date: date,
    keyword: str,
    article_id: str,
    *,
    title: str | None = None,
    reason: str = "관련 자료가 발표됐습니다.",
    description: str = "",
    categories: list[str] | None = None,
    score: float | None = None,
    people: dict[str, str] | None = None,
) -> SourceDay:
    source_name = "한국은행" if source_kind == "bank_of_korea" else "테스트경제"
    article = Article(
        stable_id=article_id,
        title=title or keyword,
        url=f"https://example.com/{article_id}",
        source=source_name,
        description=description,
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
                score=score if score is not None else (30 if source_kind == "morningnews" else 20),
                categories=categories or ["경제/거시"],
                report_date=report_date,
                article_ids=[article_id],
                source_kind=source_kind,
            )
        ],
        people=people or {},
    )


def test_editorial_lenses_prioritize_real_world_risk_and_game_changer() -> None:
    report_date = date(2026, 9, 28)
    oil = _source_day(
        "morningnews",
        report_date,
        "중동 전쟁과 국제 유가",
        "oil-shock",
        reason="전쟁 격화로 국제 유가와 운송비 상승 압력이 커졌습니다.",
        title="전쟁 격화에 국제 유가 급등, 물가 압력 확대",
        categories=["국제", "경제/거시"],
    )
    permit = _source_day(
        "morningnews",
        report_date,
        "재개발 인허가 소송",
        "permit-lawsuit",
        reason="재개발 허가 취소 소송으로 착공 일정이 멈췄습니다.",
        title="재개발 허가 소송, 내년 착공 일정 변수",
        categories=["정치", "부동산"],
    )
    treatment = _source_day(
        "morningnews",
        report_date,
        "치매 신약 임상 성공",
        "dementia-treatment",
        reason="치매 신약이 임상 3상에서 치료 효과를 확인했습니다.",
        title="치매 신약 임상 3상 성공, 치료제 승인 절차 돌입",
        categories=["기업/산업"],
        score=8,
    )
    promotion = _source_day(
        "morningnews",
        report_date,
        "AI 업무협약",
        "ai-mou",
        reason="기업들이 AI 업무협약을 맺고 공동 캠페인을 시작했습니다.",
        title="AI 업무협약 체결 기념행사",
        categories=["기업/산업"],
        score=50,
    )

    brief = build_brief([promotion, oil, permit, treatment], report_date)

    issues_by_lens = {issue.editorial_lens: issue for issue in brief.issues}
    assert set(issues_by_lens) == {
        EditorialLens.GAME_CHANGER,
        EditorialLens.REAL_WORLD_CHAIN,
        EditorialLens.OPERATIONAL_RISK,
    }
    assert (
        "주유비·공공요금·장바구니 물가"
        in issues_by_lens[EditorialLens.REAL_WORLD_CHAIN].impact_chain
    )
    assert issues_by_lens[EditorialLens.OPERATIONAL_RISK].operational_risks
    assert "내년" in issues_by_lens[EditorialLens.OPERATIONAL_RISK].timeline
    assert treatment.trends[0].keyword == issues_by_lens[EditorialLens.GAME_CHANGER].title
    assert all(issue.title != "AI 업무협약" for issue in brief.issues)


def test_decision_maker_action_becomes_power_move_without_name_hardcoding() -> None:
    report_date = date(2026, 9, 29)
    power_move = _source_day(
        "morningnews",
        report_date,
        "수출 통제 전면 전환",
        "leader-export-ban",
        reason="아르카디아 대통령 김가람이 핵심 연료 수출금지 행정명령에 서명했습니다.",
        title="김가람 대통령, 핵심 연료 수출금지 행정명령",
        categories=["국제", "경제/거시"],
        people={"김가람": "아르카디아 대통령"},
    )

    issue = build_brief([power_move], report_date).issues[0]

    assert issue.editorial_lens == EditorialLens.POWER_MOVE
    assert issue.decision_makers == ["김가람 (아르카디아 대통령)"]
    assert {"수출금지", "행정명령"}.issubset(issue.consequential_actions)
    assert issue.power_impact_chain == [
        "시장 접근과 교역 조건 변화",
        "수입 원가·수출 물량·공급망",
        "제품 가격·고용·기업 투자",
    ]


def test_famous_person_name_without_consequential_action_is_not_power_move() -> None:
    report_date = date(2026, 9, 29)
    ceremony = _source_day(
        "morningnews",
        report_date,
        "정상 기념행사",
        "leader-ceremony",
        reason="아르카디아 대통령 김가람이 기념행사에서 축사를 했습니다.",
        title="김가람 대통령 기념행사 참석",
        categories=["정치"],
        people={"김가람": "아르카디아 대통령"},
    )

    brief = build_brief([ceremony], report_date)

    issue = next(issue for issue in brief.issues + brief.currents if issue.title == "정상 기념행사")
    assert issue.editorial_lens != EditorialLens.POWER_MOVE
    assert issue.decision_makers == ["김가람 (아르카디아 대통령)"]
    assert issue.consequential_actions == []
    assert issue.power_impact_chain == []


def test_key_person_article_can_enter_candidates_when_action_changes_conditions() -> None:
    report_date = date(2026, 9, 29)
    article = Article(
        stable_id="person-action",
        title="김가람 대통령, 핵심 연료 수출금지 명령",
        url="https://example.com/person-action",
        source="테스트통신",
        description="아르카디아가 핵심 연료 수출금지 행정명령을 발효했습니다.",
        section="국제",
        report_date=report_date,
        source_kind="morningnews",
    )
    day = SourceDay(
        source_kind="morningnews",
        report_date=report_date,
        files=[Path("people.json")],
        articles=[article],
        trends=[],
        people={"김가람": "아르카디아 대통령"},
        person_article_ids={"김가람": [article.stable_id]},
    )

    issue = build_brief([day], report_date).issues[0]

    assert issue.editorial_lens == EditorialLens.POWER_MOVE
    assert issue.sources[0].title == article.title
    assert issue.decision_makers == ["김가람 (아르카디아 대통령)"]


def test_action_is_not_attributed_to_person_from_a_different_sentence() -> None:
    report_date = date(2026, 9, 29)
    article = Article(
        stable_id="separate-action",
        title="김가람 대통령, 포로 송환 경과 설명",
        url="https://example.com/separate-action",
        source="테스트통신",
        description=(
            "김가람 대통령은 포로 송환 과정을 설명했습니다. "
            "앞서 동맹국 군 지휘부는 별도 지역에 파병을 결정했습니다."
        ),
        section="국제",
        report_date=report_date,
        source_kind="morningnews",
    )
    day = SourceDay(
        source_kind="morningnews",
        report_date=report_date,
        files=[Path("people.json")],
        articles=[article],
        trends=[],
        people={"김가람": "아르카디아 대통령"},
        person_article_ids={"김가람": [article.stable_id]},
    )

    brief = build_brief([day], report_date)

    assert brief.issues == []
    assert brief.currents == []


def test_trade_truce_uses_trade_impact_chain_not_military_chain() -> None:
    report_date = date(2026, 9, 29)
    day = _source_day(
        "morningnews",
        report_date,
        "양국 무역 휴전 연장",
        "trade-truce",
        reason="아르카디아 대통령 김가람이 무역 휴전 연장에 합의했습니다.",
        categories=["국제", "경제/거시"],
        people={"김가람": "아르카디아 대통령"},
    )

    issue = build_brief([day], report_date).issues[0]

    assert issue.editorial_lens == EditorialLens.POWER_MOVE
    assert issue.consequential_actions == ["무역 휴전"]
    assert issue.power_impact_chain[0] == "시장 접근과 교역 조건 변화"


def test_proposed_or_rejected_action_does_not_create_power_move_candidate() -> None:
    report_date = date(2026, 9, 29)
    for title in (
        "김가람 대통령, 연료 수출금지 입장…실현가능성 검토",
        "김가람 대통령, 공격 계획 보류",
        "김가람 대통령, 휴전 제안 거부",
        "김가람 대통령, 관세 부과 압박할 듯",
    ):
        article = Article(
            stable_id=title,
            title=title,
            url="https://example.com/unrealized",
            source="테스트통신",
            section="국제",
            report_date=report_date,
            source_kind="morningnews",
        )
        day = SourceDay(
            source_kind="morningnews",
            report_date=report_date,
            files=[Path("people.json")],
            articles=[article],
            trends=[],
            people={"김가람": "아르카디아 대통령"},
            person_article_ids={"김가람": [article.stable_id]},
        )

        brief = build_brief([day], report_date)

        assert brief.issues == [], title
        assert brief.currents == [], title


def test_action_in_another_article_is_not_attributed_to_leader() -> None:
    report_date = date(2026, 9, 29)
    day = _source_day(
        "morningnews",
        report_date,
        "지역 안보 현안",
        "unrelated-action",
        reason="김가람 대통령이 회담에 참석했습니다.",
        title="동맹국 지휘부, 별도 지역 파병 결정",
        categories=["국제"],
        people={"김가람": "아르카디아 대통령"},
    )

    brief = build_brief([day], report_date)
    issue = next(
        issue for issue in brief.issues + brief.currents if issue.title == "지역 안보 현안"
    )

    assert issue.editorial_lens != EditorialLens.POWER_MOVE
    assert issue.consequential_actions == []


def test_build_brief_separates_evidence_and_extracts_domains() -> None:
    day = load_day(FIXTURE, date(2026, 9, 28))
    brief = build_brief([day], date(2026, 9, 28))
    assert brief.issues
    rates = next(issue for issue in brief.issues if issue.title.startswith("국채 금리"))
    assert {block.kind.value for block in rates.blocks} == {"fact", "interpretation"}
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


def test_narrative_copy_avoids_fragmented_label_language() -> None:
    day = load_day(FIXTURE, date(2026, 9, 28))
    brief = build_brief([day], date(2026, 9, 28))

    for issue in brief.issues:
        copy = " ".join(block.text for block in issue.blocks)
        assert "와 관련된 보도" not in copy
        assert "라는 내용이 주목받았습니다" not in copy
        assert "관련 발표가 실제 시행" not in copy
        assert "일에 걸쳐 이어졌습니다" not in copy
        assert "단정할 수는 없습니다" not in copy
        assert sum(block.kind.value == "interpretation" for block in issue.blocks) <= 1


def test_article_descriptions_are_plain_text_before_editorial_use() -> None:
    report_date = date(2026, 9, 28)
    day = _source_day("morningnews", report_date, "주택 금리", "housing-rate")
    day.articles[0].description = "<table><tr><td>대출&nbsp;부담</td></tr></table>\n  확대"

    brief = build_brief([day], report_date)

    assert brief.issues[0].sources[0].description == "대출 부담 확대"
    assert "<table" not in brief.issues[0].sources[0].description


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


def test_unexplained_official_source_is_not_published_to_readers() -> None:
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
    assert brief.official_updates == []
    assert all(issue.title != "금융안정 상황" for issue in brief.issues)
    assert all(issue.title != "금융안정 상황" for issue in brief.currents)


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

    assert {issue.title for issue in brief.official_updates} == {"2026년 9월 소비자동향조사 결과"}
    assert all(issue.active_days == 1 for issue in brief.official_updates)


def test_official_update_has_plain_language_reader_copy() -> None:
    report_date = date(2026, 9, 28)
    official = _source_day(
        "bank_of_korea",
        report_date,
        "2026년 9월 소비자동향조사 결과",
        "bok-consumer-reader-copy",
        reason="소비자심리지수는 106.6으로 전월 대비 2.1p 상승했습니다.",
    )

    issue = build_brief([official], report_date).official_updates[0]

    assert issue.reader_heading == "소비자가 느끼는 경기가 전월보다 나아졌다"
    assert "실제 소비액이 아니라" in issue.reader_summary
    assert "106.6" in issue.reader_summary


def test_brief_coverage_uses_only_morning_news_dates() -> None:
    morning = _source_day("morningnews", date(2026, 9, 23), "기준금리 결정", "morning-rate")
    official = _source_day("bank_of_korea", date(2026, 9, 22), "금융안정 상황", "bok-stability")

    brief = build_brief([official, morning], date(2026, 9, 23))

    assert brief.input_days == [date(2026, 9, 23)]
    assert date(2026, 9, 22) in brief.missing_days
