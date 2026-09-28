from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta

from sunday_radar.domain import (
    Article,
    Certainty,
    EntitySet,
    EvidenceBlock,
    EvidenceType,
    Issue,
    SourceDay,
    SourceLink,
    TrendSignal,
    WeeklyBrief,
)
from sunday_radar.normalization import normalize_text, stable_hash

STOPWORDS = {"관련", "확대", "상승", "하락", "추진", "발표", "논란", "정부", "이번주"}
REJECTED_KEYWORDS = {
    "앞두고",
    "하는",
    "함께",
    "대해",
    "통해",
    "위해",
    "추석",
    "설날",
    "co",
    "kr",
}
DOMAIN_TERMS = {
    "stocks": ("주가", "증시", "코스피", "코스닥", "실적", "반도체", "엔터주", "상장"),
    "fx": ("환율", "원화", "달러", "엔화", "위안"),
    "rates": ("금리", "국채", "채권", "기준금리"),
    "crypto": ("비트코인", "가상자산", "암호화폐", "코인"),
    "real_estate": ("부동산", "재건축", "아파트", "주택", "임대", "토지"),
    "prices": ("물가", "가격", "유가", "관세", "원유"),
    "jobs": ("고용", "취업", "채용", "임금", "실업"),
    "daily_life": ("교통", "교육", "의료", "안전", "대출", "서비스", "시장"),
}
PLACE_TERMS = (
    "서울",
    "용산",
    "미국",
    "중국",
    "일본",
    "북한",
    "우크라이나",
    "중동",
    "멕시코",
    "DMZ",
)
POLICY_TERMS = ("법", "정책", "규제", "관세", "제재", "협의체", "임명", "허가제", "금리")
COMPANY_SUFFIXES = ("전자", "그룹", "은행", "에어로", "하이닉스", "자동차", "전기")
IMPACT_COPY = {
    "stocks": (
        "기업 실적 기대와 위험 선호를 통해 주가 변동성으로 연결될 수 있습니다.",
        "실적 발표와 수급 변화",
    ),
    "fx": (
        "금리 차이와 안전자산 선호를 거쳐 원화 환율에 영향을 줄 수 있습니다.",
        "주요국 금리와 원·달러 환율",
    ),
    "rates": (
        "물가 기대와 국채 수급을 통해 대출·채권 금리에 전달될 수 있습니다.",
        "국채 입찰과 중앙은행 발언",
    ),
    "crypto": (
        "유동성과 위험 선호 변화가 가상자산 변동성에 반영될 수 있습니다.",
        "달러 유동성과 규제 발표",
    ),
    "real_estate": (
        "대출 여건과 공급 기대를 통해 거래량과 주거 비용에 영향을 줄 수 있습니다.",
        "거래량·대출금리·후속 시행규칙",
    ),
    "prices": (
        "수입 비용과 공급망을 거쳐 소비자 가격으로 전가될 가능성이 있습니다.",
        "원자재·운임·소비자물가",
    ),
    "jobs": (
        "기업 비용과 투자 계획을 통해 채용과 임금에 영향을 줄 수 있습니다.",
        "채용 공고와 고용 지표",
    ),
    "daily_life": (
        "제도 시행 방식에 따라 가계 비용과 이용 가능한 서비스가 달라질 수 있습니다.",
        "시행일과 현장 적용 범위",
    ),
}

DOMAIN_NARRATIVE = {
    "stocks": ("기업의 기대가 시장의 온도를 바꾸는 주", "기업과 투자 심리"),
    "fx": ("바깥의 변화가 원화와 생활비로 번지는 주", "환율과 생활비"),
    "rates": ("금리의 방향이 자산과 생활의 온도를 바꾸는 주", "금리와 가계의 선택"),
    "crypto": ("유동성의 변화가 위험자산을 흔드는 주", "유동성과 위험 선호"),
    "real_estate": ("집의 가격보다 시장의 방향을 읽어야 하는 주", "주거 시장과 가계"),
    "prices": ("시장의 숫자가 장바구니까지 내려오는 주", "물가와 일상의 비용"),
    "jobs": ("기업의 결정이 일자리의 풍경을 바꾸는 주", "고용과 가계 소득"),
    "daily_life": ("정책과 시장의 변화가 일상에 닿는 주", "시장과 일상의 변화"),
}
NARRATIVE_DOMAIN_PRIORITY = (
    "rates",
    "real_estate",
    "prices",
    "fx",
    "jobs",
    "stocks",
    "crypto",
    "daily_life",
)
SOURCE_KIND_LABELS = {
    "morningnews": "Morning News",
    "bank_of_korea": "한국은행 공식 자료",
}
OFFICIAL_TOPIC_ALIASES = {
    "base_rate": ("기준금리", "통화정책방향"),
    "balance_of_payments": ("국제수지", "경상수지"),
    "business_sentiment": ("기업경기조사", "기업심리지수", "bsi"),
    "consumer_sentiment": ("소비자동향조사", "소비자심리지수", "ccsi"),
    "foreign_reserves": ("외환보유액",),
    "household_credit": ("가계신용",),
    "producer_prices": ("생산자물가지수", "생산자물가"),
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in normalize_text(value).split()
        if len(token) >= 2 and token not in STOPWORDS
    }


def _similar(left: str, right: str) -> bool:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return normalize_text(left) == normalize_text(right)
    overlap = len(a & b) / min(len(a), len(b))
    return (
        overlap >= 0.5
        or normalize_text(left) in normalize_text(right)
        or normalize_text(right) in normalize_text(left)
    )


def _official_topics(value: str) -> set[str]:
    normalized = normalize_text(value)
    return {
        topic
        for topic, aliases in OFFICIAL_TOPIC_ALIASES.items()
        if any(normalize_text(alias) in normalized for alias in aliases)
    }


def _matches_official_topic(signal: TrendSignal, cluster: list[TrendSignal]) -> bool:
    official_topics = _official_topics(signal.keyword)
    editorial_topics = {
        topic
        for candidate in cluster
        if candidate.source_kind == "morningnews"
        for topic in _official_topics(candidate.keyword)
    }
    return bool(official_topics and official_topics & editorial_topics)


def _same_official_topic(signal: TrendSignal, cluster: list[TrendSignal]) -> bool:
    signal_topics = _official_topics(signal.keyword)
    cluster_topics = {
        topic for candidate in cluster for topic in _official_topics(candidate.keyword)
    }
    return bool(signal_topics and signal_topics & cluster_topics)


def _domains(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [
        key
        for key, terms in DOMAIN_TERMS.items()
        if any(term.lower() in normalized for term in terms)
    ]


def _entities(text: str, people: set[str]) -> EntitySet:
    normalized = normalize_text(text)
    found_people = sorted(name for name in people if normalize_text(name) in normalized)
    places = sorted(term for term in PLACE_TERMS if term.lower() in normalized)
    policies = sorted(
        {
            match.group(0)
            for match in re.finditer(
                r"[0-9a-z가-힣·]+(?:정책|법|규제|관세|제재|협의체|허가제)", text
            )
        }
    )
    companies = sorted(
        {
            token
            for token in re.findall(r"[A-Za-z0-9가-힣+]+", text)
            if token.endswith(COMPANY_SUFFIXES) or token in {"AMD", "BOE", "엔비디아", "기아"}
        }
    )
    return EntitySet(
        people=found_people,
        places=places,
        policies=policies,
        companies=companies,
        market_domains=_domains(text),
    )


def _source_links(article_ids: set[str], articles: dict[str, Article]) -> list[SourceLink]:
    links: list[SourceLink] = []
    seen_urls: set[str] = set()
    for article_id in sorted(article_ids):
        article = articles.get(article_id)
        if not article or not article.url or article.url in seen_urls:
            continue
        seen_urls.add(article.url)
        links.append(
            SourceLink(
                title=article.title,
                source=article.source,
                url=article.url,
                source_kind=article.source_kind,
            )
        )
    if len(links) <= 4:
        return links
    selected: list[SourceLink] = []
    for source_kind in sorted({link.source_kind for link in links}):
        selected.append(next(link for link in links if link.source_kind == source_kind))
    selected_urls = {str(link.url) for link in selected}
    selected.extend(link for link in links if str(link.url) not in selected_urls)
    return selected[:4]


def _display_title(signal: TrendSignal, sources: list[SourceLink]) -> str:
    keyword = signal.keyword.strip()
    reason = signal.reason.strip()
    if len(_tokens(keyword)) <= 1:
        detail = reason
        if not detail and sources:
            detail = sources[0].title
        if detail and normalize_text(detail) != normalize_text(keyword):
            return f"{keyword}: {detail}"
    return keyword


def _make_issue(
    signals: list[TrendSignal], articles: dict[str, Article], people: set[str]
) -> Issue:
    signals = sorted(signals, key=lambda item: (item.report_date, -item.score, item.keyword))
    editorial_signals = [signal for signal in signals if signal.source_kind == "morningnews"]
    ranking_signals = editorial_signals or signals
    representative = max(
        ranking_signals,
        key=lambda item: (len(item.article_ids), item.score, item.report_date, item.keyword),
    )
    days = sorted({signal.report_date for signal in ranking_signals})
    article_ids = {article_id for signal in signals for article_id in signal.article_ids}
    sources = _source_links(article_ids, articles)
    ranking_article_ids = {
        article_id for signal in ranking_signals for article_id in signal.article_ids
    }
    combined = " ".join(
        [representative.keyword, representative.reason]
        + [articles[item].title for item in sorted(ranking_article_ids) if item in articles]
    )
    entities = _entities(combined, people)
    category_counts: dict[str, int] = defaultdict(int)
    for signal in ranking_signals:
        for category in signal.categories:
            category_counts[category] += 1
    category = (
        max(sorted(category_counts), key=lambda item: category_counts[item])
        if category_counts
        else "기타"
    )
    ranking_source_count = len(
        {
            (articles[article_id].source_kind, articles[article_id].source)
            for article_id in ranking_article_ids
            if article_id in articles
        }
    )
    base_score = min(
        100.0,
        32 + len(days) * 11 + ranking_source_count * 4 + min(representative.score, 30) * 0.4,
    )
    signal_kinds = sorted({signal.source_kind for signal in ranking_signals})
    source_labels = [SOURCE_KIND_LABELS.get(kind, kind) for kind in signal_kinds]
    if not editorial_signals and signal_kinds == ["bank_of_korea"]:
        default_announcement = f"한국은행이 「{representative.keyword}」 자료를 발표했습니다."
        detail = "" if representative.reason == default_announcement else representative.reason
        fact_text = (
            f"한국은행은 {representative.report_date.isoformat()}에 "
            f"「{representative.keyword}」 자료를 발표했습니다. "
            f"{detail}"
        ).strip()
    else:
        fact_text = (
            f"{'·'.join(source_labels)}에서 '{representative.keyword}' 이슈가 "
            f"{len(days)}일 동안 포착됐습니다. 최근 신호는 "
            f"“{representative.reason or representative.keyword}”입니다."
        )
    blocks = [
        EvidenceBlock(
            kind=EvidenceType.FACT, label="확인된 흐름", text=fact_text, certainty=Certainty.HIGH
        )
    ]
    official_signal = next(
        (signal for signal in reversed(signals) if signal.source_kind == "bank_of_korea"), None
    )
    if official_signal is not None:
        blocks.append(
            EvidenceBlock(
                kind=EvidenceType.OFFICIAL_CLAIM,
                label="공식 자료",
                text=official_signal.reason or official_signal.keyword,
                certainty=Certainty.HIGH,
            )
        )
    watches: list[str] = []
    for domain in entities.market_domains[:3]:
        explanation, watch = IMPACT_COPY[domain]
        blocks.append(
            EvidenceBlock(
                kind=EvidenceType.INTERPRETATION,
                label="시장·생활 연결",
                text=explanation,
                certainty=Certainty.MEDIUM,
            )
        )
        watches.append(watch)
    if entities.market_domains:
        blocks.append(
            EvidenceBlock(
                kind=EvidenceType.SCENARIO,
                label="가능 시나리오",
                text=(
                    "관련 발표가 실제 시행으로 이어지는 경우 영향 영역의 변동성이 "
                    "커질 수 있습니다. 반대로 후속 조치가 지연되면 단기 영향은 "
                    "제한될 수 있습니다."
                ),
                certainty=Certainty.LOW,
            )
        )
    else:
        watches.append("후속 공식 발표와 독립 출처의 추가 확인")
    return Issue(
        issue_id=stable_hash(normalize_text(representative.keyword))[:16],
        title=_display_title(representative, sources),
        category=category,
        score=round(base_score, 2),
        first_seen=days[0],
        last_seen=days[-1],
        active_days=len(days),
        entities=entities,
        blocks=blocks,
        watch_variables=sorted(set(watches)),
        sources=sources,
    )


def _select_primary(issues: list[Issue]) -> list[Issue]:
    candidates = [issue for issue in issues if issue.sources and issue.entities.market_domains]
    if not candidates:
        return []
    macro = next((issue for issue in candidates if issue.category == "경제/거시"), candidates[0])
    selected = [macro]
    narrative_candidates = [
        issue
        for issue in candidates
        if issue.issue_id != macro.issue_id and issue.category in {"경제/거시", "부동산"}
    ]
    remaining = (
        narrative_candidates
        if len(narrative_candidates) >= 2
        else [issue for issue in candidates if issue.issue_id != macro.issue_id]
    )
    while remaining and len(selected) < 3:
        known_domains = {
            domain
            for selected_issue in selected
            for domain in selected_issue.entities.market_domains
        }
        next_issue = max(
            remaining,
            key=lambda issue: (
                issue.score + 12 * len(known_domains & set(issue.entities.market_domains)),
                issue.active_days,
                issue.title,
            ),
        )
        selected.append(next_issue)
        remaining.remove(next_issue)
    return selected


def build_brief(days: list[SourceDay], as_of: date) -> WeeklyBrief:
    article_map = {article.stable_id: article for day in days for article in day.articles}
    people = {name for day in days for name in day.people}
    all_signals = sorted(
        (
            trend
            for day in days
            for trend in day.trends
            if normalize_text(trend.keyword) not in REJECTED_KEYWORDS
        ),
        key=lambda item: (
            item.source_kind,
            normalize_text(item.keyword),
            item.report_date,
            item.keyword,
        ),
    )
    editorial_signals = [signal for signal in all_signals if signal.source_kind == "morningnews"]
    official_signals = [signal for signal in all_signals if signal.source_kind == "bank_of_korea"]
    other_signals = [
        signal
        for signal in all_signals
        if signal.source_kind not in {"morningnews", "bank_of_korea"}
    ]
    clusters: list[list[TrendSignal]] = []
    for signal in editorial_signals + other_signals:
        target = next(
            (cluster for cluster in clusters if _similar(cluster[0].keyword, signal.keyword)), None
        )
        if target is None:
            clusters.append([signal])
        else:
            target.append(signal)
    for signal in official_signals:
        matching_editorial = [
            cluster for cluster in clusters if _matches_official_topic(signal, cluster)
        ]
        if len(matching_editorial) == 1:
            matching_editorial[0].append(signal)
            continue
        matching_official = next(
            (
                cluster
                for cluster in clusters
                if all(candidate.source_kind == "bank_of_korea" for candidate in cluster)
                and _same_official_topic(signal, cluster)
            ),
            None,
        )
        if matching_official is None:
            clusters.append([signal])
        else:
            matching_official.append(signal)
    issue_records = sorted(
        (
            (_make_issue(cluster, article_map, people), {signal.source_kind for signal in cluster})
            for cluster in clusters
        ),
        key=lambda item: (-item[0].score, -item[0].active_days, item[0].title),
    )
    issues = [issue for issue, _source_kinds in issue_records]
    editorial_issues = [
        issue for issue, source_kinds in issue_records if "morningnews" in source_kinds
    ]
    primary = _select_primary(editorial_issues)
    if len(primary) < 3:
        primary_ids = {issue.issue_id for issue in primary}
        primary.extend(
            issue
            for issue in editorial_issues
            if issue.sources
            and issue.category in {"정치", "국제", "경제/거시"}
            and issue.issue_id not in primary_ids
        )
        primary = primary[:3]
    primary_ids = {issue.issue_id for issue in primary}
    official_updates = [
        issue
        for issue, source_kinds in issue_records
        if issue.issue_id not in primary_ids
        and "morningnews" not in source_kinds
        and "bank_of_korea" in source_kinds
    ][:3]
    official_ids = {issue.issue_id for issue in official_updates}
    currents = [
        issue
        for issue in issues
        if issue.issue_id not in primary_ids
        and issue.issue_id not in official_ids
        and issue.category in {"부동산", "기업/산업", "생활/문화"}
    ][:5]
    available = sorted({day.report_date for day in days if day.source_kind == "morningnews"})
    expected = [as_of - timedelta(days=offset) for offset in range(6, -1, -1)]
    missing = [day for day in expected if day not in available]
    reading_minutes = max(3, min(5, round((len(primary) * 180 + len(currents) * 90 + 300) / 500)))
    primary_domains = {domain for issue in primary for domain in issue.entities.market_domains}
    source_kinds = sorted({day.source_kind for day in days})
    source_labels = ", ".join(SOURCE_KIND_LABELS.get(kind, kind) for kind in source_kinds)
    lead_domain = next(
        (domain for domain in NARRATIVE_DOMAIN_PRIORITY if domain in primary_domains), "daily_life"
    )
    headline, narrative_subject = DOMAIN_NARRATIVE[lead_domain]
    issue_titles = [issue.title for issue in primary]
    if len(issue_titles) >= 2:
        overview = (
            f"이번 주에는 「{issue_titles[0]}」에서 시작해 「{issue_titles[1]}」로 이어지는 "
            f"흐름을 따라갑니다. 서로 다른 뉴스처럼 보이지만, {narrative_subject}이라는 "
            "하나의 질문으로 묶어 보면 다음 장면이 선명해집니다."
        )
    elif issue_titles:
        overview = (
            f"이번 주에는 「{issue_titles[0]}」에서 출발해 {narrative_subject}에 닿는 "
            "변화를 천천히 살펴봅니다."
        )
    else:
        overview = "이번 주에는 하나의 흐름으로 엮을 수 있는 자료가 충분하지 않습니다."
    return WeeklyBrief(
        week_ending=as_of,
        window_start=expected[0],
        window_end=expected[-1],
        generated_at=datetime.combine(as_of, datetime.min.time()),
        input_days=available,
        missing_days=missing,
        source_kinds=source_kinds,
        headline=headline,
        overview=overview,
        issues=primary,
        official_updates=official_updates,
        currents=currents,
        reading_minutes=reading_minutes,
        methodology_note=(
            f"{source_labels}를 규칙 기반으로 재구성했습니다. 공식 자료는 좁게 정의한 동일 "
            "주제가 하나의 뉴스 흐름과 명확히 일치할 때만 근거로 연결하고, 나머지는 별도 "
            "구역에 표시합니다. 원문 전체를 "
            "독립적으로 사실 검증한 결과나 투자 조언이 아닙니다."
        ),
    )
