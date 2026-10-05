from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta

from sunday_radar.domain import (
    Article,
    Certainty,
    EditorialLens,
    EntitySet,
    EvidenceBlock,
    EvidenceType,
    Issue,
    SourceDay,
    SourceLink,
    TrendSignal,
    WeeklyBrief,
)
from sunday_radar.normalization import clean_summary_text, normalize_text, stable_hash

STOPWORDS = {"관련", "확대", "상승", "하락", "추진", "발표", "논란", "정부", "이번주"}
REJECTED_KEYWORDS = {
    "등에",
    "등의",
    "등은",
    "같은",
    "투자",
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


def _usable_keyword(value: str) -> bool:
    normalized = normalize_text(value)
    tokens = normalized.split()
    return bool(
        normalized
        and normalized not in REJECTED_KEYWORDS
        and not any(len(token) == 1 and re.fullmatch(r"[가-힣]", token) for token in tokens)
    )


DOMAIN_TERMS = {
    "stocks": ("주가", "증시", "코스피", "코스닥", "실적", "반도체", "엔터주", "상장"),
    "fx": ("환율", "원화", "달러", "엔화", "위안"),
    "rates": ("금리", "국채", "채권", "기준금리"),
    "crypto": ("비트코인", "가상자산", "암호화폐", "코인"),
    "real_estate": ("부동산", "재건축", "아파트", "주택", "임대", "토지"),
    "prices": ("물가", "가격", "유가", "관세", "원유"),
    "jobs": ("고용", "취업", "채용", "임금", "실업"),
    "daily_life": ("교통", "교육", "의료", "안전", "대출", "서비스", "시장"),
    "technology": (
        "ai",
        "인공지능",
        "로봇",
        "양자",
        "핵융합",
        "자율주행",
        "우주",
        "반도체",
    ),
    "health": ("치매", "알츠하이머", "신약", "치료제", "백신", "임상", "유전자", "의료"),
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
        "기업 실적에 대한 기대와 투자자의 위험 선호가 달라지면서 주가의 움직임도 커질 수 있습니다.",
        "실적 발표와 수급 변화",
    ),
    "fx": (
        "나라별 금리 차이와 안전자산 선호는 원화 가치와 환전 비용에까지 이어집니다.",
        "주요국 금리와 원·달러 환율",
    ),
    "rates": (
        "국채시장의 변화는 채권 금리를 거쳐 가계와 기업이 마주하는 대출 금리에 전달됩니다.",
        "국채 입찰과 중앙은행 발언",
    ),
    "crypto": (
        "시중 유동성과 위험 선호가 바뀌면 가상자산 가격도 더 크게 흔들릴 수 있습니다.",
        "달러 유동성과 규제 발표",
    ),
    "real_estate": (
        "대출 여건과 새 주택 공급에 대한 기대가 달라지면 거래량과 주거 비용도 함께 움직입니다.",
        "거래량·대출금리·후속 시행규칙",
    ),
    "prices": (
        "수입 비용과 운송비의 변화는 시차를 두고 소비자가 지불하는 가격에 반영될 수 있습니다.",
        "원자재·운임·소비자물가",
    ),
    "jobs": (
        "기업의 비용 부담과 투자 계획은 채용 규모와 임금 협상에 영향을 줍니다.",
        "채용 공고와 고용 지표",
    ),
    "daily_life": (
        "제도가 언제 어떤 범위로 시행되는지에 따라 가계 부담과 이용할 수 있는 서비스가 달라집니다.",
        "시행일과 현장 적용 범위",
    ),
    "technology": (
        "기술의 성능과 비용 구조가 바뀌면 기존 제품과 일자리, 산업의 경쟁 기준도 다시 짜입니다.",
        "실제 성능·가격·도입 속도",
    ),
    "health": (
        "치료 선택지가 달라지면 환자와 가족의 돌봄 시간, 의료비, 삶의 질이 함께 바뀝니다.",
        "승인 범위·치료 효과·접근 비용",
    ),
}

GAME_CHANGER_DOMAIN_TERMS = (
    "ai",
    "인공지능",
    "로봇",
    "양자",
    "핵융합",
    "자율주행",
    "우주",
    "치매",
    "알츠하이머",
    "신약",
    "치료제",
    "백신",
    "임상",
    "유전자",
)
GAME_CHANGER_BREAKTHROUGH_TERMS = (
    "세계 최초",
    "국내 최초",
    "최초 승인",
    "규제기관 승인",
    "치료제 승인",
    "신약 승인",
    "fda 허가",
    "품목허가",
    "허가 획득",
    "임상 3상",
    "임상 성공",
    "치료 효과",
    "상용화",
    "성능 돌파",
    "신기록",
    "새 모델 공개",
    "정식 출시",
    "완치",
    "혁신 치료",
)
OPERATIONAL_TERMS = (
    "재판",
    "판결",
    "소송",
    "수사",
    "기소",
    "규제",
    "법안",
    "시행령",
    "허가",
    "인가",
    "고시",
    "입찰",
    "유찰",
    "착공",
    "정비계획",
    "사업시행",
    "심의",
)
LOW_SIGNAL_TERMS = (
    "업무협약",
    "mou",
    "파트너 선정",
    "캠페인",
    "기념행사",
    "수상",
    "홍보대사",
    "팝업스토어",
    "법카",
    "작품 논란",
    "연예계 논란",
    "전문가 전망",
    "만장일치",
    "가격 전망",
)

DECISION_MAKER_ROLE_TERMS = (
    "대통령",
    "국가주석",
    "총리",
    "국왕",
    "장관",
    "부총리",
    "중앙은행 총재",
    "연준 의장",
    "당대표",
    "대표",
    "위원장",
    "법원장",
    "검찰총장",
    "참모총장",
    "군사령관",
    "최고경영자",
    "ceo",
)
POWER_ACTIONS = {
    "military": (
        "공격",
        "폭격",
        "침공",
        "파병",
        "철군",
        "철수",
        "휴전",
        "동원령",
        "미사일 발사",
        "핵실험",
    ),
    "trade": (
        "무역 휴전",
        "관세 부과",
        "관세 인상",
        "수출금지",
        "수입금지",
        "금수조치",
        "경제제재",
        "제재 해제",
        "무역협정 체결",
        "협정 탈퇴",
    ),
    "policy": (
        "행정명령",
        "거부권",
        "법안 서명",
        "정책 철회",
        "규제 철회",
        "해임",
        "사면",
        "국유화",
        "민영화",
    ),
    "diplomacy": (
        "합의 타결",
        "협상 결렬",
        "국교 단절",
        "승인 철회",
        "독립 승인",
        "영토 인정",
        "동맹 탈퇴",
    ),
    "fiscal": (
        "증세",
        "감세",
        "예산 삭감",
        "보조금 중단",
        "재정지원 중단",
        "채무불이행",
    ),
}
POWER_MODERATE_ACTIONS = {
    "policy": ("사임", "임명", "재가"),
    "diplomacy": (
        "돌발 발표",
        "돌발발표",
        "전격 공개",
        "비공개 합의를 어기고 공개",
        "회담 취소",
        "방문 취소",
    ),
}
POWER_UNREALIZED_TERMS = (
    "검토",
    "예상",
    "전망",
    "가능성",
    "압박",
    "제안",
    "보류",
    "거부",
    "경고",
    "입장",
    "할 듯",
    "할 수도",
    "계획",
    "요구",
)
POWER_IMPACT_CHAINS = {
    "military": ["군사·안보 조건 변화", "에너지·물류·위험 회피", "유가·환율·공급망·생활비"],
    "trade": [
        "시장 접근과 교역 조건 변화",
        "수입 원가·수출 물량·공급망",
        "제품 가격·고용·기업 투자",
    ],
    "policy": ["법과 행정의 전제 변화", "허가·세금·사업 계획 재조정", "현장 일정·비용·이용자 권리"],
    "diplomacy": [
        "국가 간 약속과 신뢰 변화",
        "동맹·투자·교역 판단 변화",
        "안보 비용·환율·기업 전략",
    ],
    "fiscal": ["정부의 세입·지출 방향 변화", "가계·기업 지원과 부담 변화", "소득·고용·소비 여력"],
}

CHAIN_DOMAINS = {"prices", "rates", "fx", "real_estate", "jobs", "daily_life"}
CHAIN_STEPS = {
    "prices": ["원유·원자재·운송비 압력", "기업의 원가와 배송비", "주유비·공공요금·장바구니 물가"],
    "rates": ["국채금리와 시중금리", "은행의 조달비용과 대출금리", "이자 부담과 소비·주거 여력"],
    "fx": ["달러 수요와 원화 가치", "수입 원가와 해외 결제 비용", "식품·에너지·여행 지출"],
    "real_estate": ["금융·공급 정책 변화", "대출 한도와 사업비", "거래·분양·주거비 선택지"],
    "jobs": ["기업의 비용과 투자 계획", "채용·임금·근무 조건", "가계 소득과 소비 여력"],
    "daily_life": ["정책과 서비스 조건 변화", "현장 적용 범위와 이용 가격", "가계 부담과 선택지"],
}
OPERATIONAL_RISK_COPY = {
    "재판": "재판 결과와 불복 절차가 의사결정 시점을 늦출 수 있음",
    "판결": "판결 내용과 후속 절차가 사업의 법적 전제를 바꿀 수 있음",
    "소송": "소송 기간과 가처분 여부가 계약·착공 일정을 묶을 수 있음",
    "수사": "수사 범위가 넓어지면 승인과 경영 판단이 보수적으로 바뀔 수 있음",
    "기소": "기소 이후 재판 일정이 책임자와 사업 의사결정의 변수로 남음",
    "규제": "규제의 적용 대상과 시행 시점이 비용과 사업 가능 범위를 바꿈",
    "법안": "법안의 통과 여부와 하위 규정이 실제 시행 시점을 좌우함",
    "시행령": "시행령의 세부 기준이 현장 비용과 준비 기간을 결정함",
    "허가": "허가 조건과 처리 기간이 착공·영업 시작의 병목이 됨",
    "인가": "인가 범위와 조건이 자금 집행과 사업 개시 시점을 좌우함",
    "고시": "고시 확정 전후로 적용 범위와 준비 일정이 갈릴 수 있음",
    "입찰": "입찰 조건과 경쟁 구도가 사업자 선정과 원가를 결정함",
    "유찰": "유찰이 반복되면 사업자 선정과 전체 일정이 뒤로 밀림",
    "착공": "착공 전 인허가와 자금 조달이 실제 일정의 마지막 관문임",
    "정비계획": "정비계획 확정 속도가 분담금 산정과 후속 인허가를 좌우함",
    "사업시행": "사업시행 절차가 지연되면 이주·착공·분양 일정이 함께 밀림",
    "심의": "심의 통과 여부와 보완 요구가 설계·비용·일정을 바꿈",
}

DOMAIN_NARRATIVE = {
    "health": ("치료의 기준을 바꿀 뉴스가 일상으로 들어오는 주", "치료 선택지와 돌봄 비용"),
    "technology": ("기술의 도약이 산업의 규칙을 다시 쓰는 주", "기술과 일상의 변화"),
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
    "health",
    "technology",
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
PUBLIC_OFFICIAL_TOPICS = {
    "base_rate",
    "balance_of_payments",
    "business_sentiment",
    "consumer_sentiment",
    "foreign_reserves",
    "household_credit",
    "producer_prices",
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
    compact_left = normalize_text(left).replace(" ", "")
    compact_right = normalize_text(right).replace(" ", "")
    if compact_left == compact_right:
        return True
    # A generic shared word such as 'investment' is not an issue identity.
    if min(len(a), len(b)) == 1:
        return False
    return len(a & b) >= 2


def _relevant_article(signal: TrendSignal, article: Article) -> bool:
    """Do not treat an upstream related-article ID as proof of topical relevance."""
    if signal.source_kind != "morningnews":
        return True
    keyword = normalize_text(signal.keyword)
    title = normalize_text(article.title)
    if not title:
        return False
    if keyword in title or keyword.replace(" ", "") in title.replace(" ", ""):
        return True
    tokens = [token for token in _tokens(keyword) if len(token) >= 3]
    # A short or generic token is not enough to attach an unrelated article.
    return bool(tokens and all(token in title.split() for token in tokens))


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


def _power_profile(
    text: str, people: dict[str, str]
) -> tuple[list[str], list[str], list[str], float]:
    normalized = normalize_text(text)
    eligible_people = {
        name: role
        for name, role in people.items()
        if normalize_text(name) in normalized
        and any(normalize_text(term) in normalize_text(role) for term in DECISION_MAKER_ROLE_TERMS)
    }
    decision_makers = sorted(f"{name} ({role})" for name, role in eligible_people.items())
    if not decision_makers:
        return [], [], [], 0.0

    segments = [
        normalize_text(segment)
        for segment in re.split(r"(?<=[.!?。])\s+|[\n\r]+", text)
        if segment.strip()
    ]
    actor_segments = [
        segment
        for segment in segments
        if any(normalize_text(name) in segment for name in eligible_people)
    ]
    if not actor_segments:
        return decision_makers, [], [], 0.0

    matched: list[tuple[str, str]] = []
    moderate: list[tuple[str, str]] = []
    for segment in actor_segments:
        if any(normalize_text(term) in segment for term in POWER_UNREALIZED_TERMS):
            continue
        for action_type, terms in POWER_ACTIONS.items():
            matched.extend(
                (action_type, term)
                for term in terms
                if normalize_text(term) in segment
                and not (
                    action_type == "military"
                    and term == "휴전"
                    and normalize_text("무역 휴전") in segment
                )
                and not (
                    action_type == "military"
                    and term == "폭격"
                    and normalize_text("폭격기") in segment
                )
            )
        for action_type, terms in POWER_MODERATE_ACTIONS.items():
            moderate.extend(
                (action_type, term) for term in terms if normalize_text(term) in segment
            )
    if not matched and not moderate:
        return decision_makers, [], [], 0.0

    actions = [term for _action_type, term in matched[:3]]
    actions.extend(term for _action_type, term in moderate[:2])
    action_types = [action_type for action_type, _term in matched + moderate]
    impact_chain = POWER_IMPACT_CHAINS[action_types[0]]
    bonus = 32.0 if matched else 18.0
    return decision_makers, actions, impact_chain, bonus


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
                description=clean_summary_text(article.description)[:1200],
                report_date=article.report_date,
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


def _person_action_signals(
    days: list[SourceDay], articles: dict[str, Article]
) -> list[TrendSignal]:
    signals: list[TrendSignal] = []
    seen: set[tuple[date, str, str]] = set()
    for day in days:
        for name, article_ids in sorted(day.person_article_ids.items()):
            role = day.people.get(name, "")
            for article_id in article_ids:
                article = articles.get(article_id)
                if article is None:
                    continue
                _makers, actions, _chain, bonus = _power_profile(article.title, {name: role})
                if not bonus:
                    _makers, actions, _chain, bonus = _power_profile(
                        clean_summary_text(article.description)[:320], {name: role}
                    )
                if not bonus or not actions:
                    continue
                key = (day.report_date, name, article_id)
                if key in seen:
                    continue
                seen.add(key)
                signals.append(
                    TrendSignal(
                        keyword=f"{name}: {article.title}",
                        reason=clean_summary_text(article.description) or article.title,
                        score=12.0,
                        categories=[article.section] if article.section else ["기타"],
                        report_date=day.report_date,
                        article_ids=[article_id],
                        source_kind="morningnews",
                    )
                )
    return signals


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


def _official_reader_copy(signal: TrendSignal) -> tuple[str, str]:
    topics = _official_topics(f"{signal.keyword} {signal.reason}")
    reason = signal.reason.strip().rstrip(".")
    if "consumer_sentiment" in topics:
        direction = (
            "나아졌다" if "상승" in reason else "약해졌다" if "하락" in reason else "움직였다"
        )
        return (
            f"소비자가 느끼는 경기가 전월보다 {direction}",
            f"{reason}. 소비심리는 실제 소비액이 아니라, 가계가 소비와 큰 지출을 얼마나 "
            "조심스럽게 보는지 보여주는 신호입니다.",
        )
    if "base_rate" in topics:
        return (
            "대출과 예금금리의 출발점이 확인됐다",
            f"{reason}. 기준금리는 은행의 대출·예금금리와 가계의 이자 부담이 움직이는 "
            "출발점입니다.",
        )
    if "producer_prices" in topics:
        return (
            "기업이 먼저 마주한 원가 압력이 확인됐다",
            f"{reason}. 생산자물가는 기업이 재료와 상품을 들여오는 가격이라, 이후 소비자 "
            "가격의 압력을 읽는 데 쓰입니다.",
        )
    if "household_credit" in topics:
        return (
            "가계 빚이 늘고 줄어든 방향이 확인됐다",
            f"{reason}. 가계신용은 주택과 소비에 쓰인 빚의 규모를 보여줘 이자 부담과 소비 "
            "여력을 함께 가늠하게 합니다.",
        )
    if "business_sentiment" in topics:
        return (
            "기업이 체감하는 경기 온도가 확인됐다",
            f"{reason}. 기업심리는 채용과 설비투자를 늘릴지 미룰지 판단하는 분위기를 "
            "보여주는 선행 신호입니다.",
        )
    if "balance_of_payments" in topics:
        return (
            "한국이 해외에서 번 돈과 쓴 돈의 차이가 나왔다",
            f"{reason}. 국제수지는 수출입과 해외 투자에서 들어오고 나간 돈을 합쳐 원화와 "
            "대외 건전성을 읽는 자료입니다.",
        )
    if "foreign_reserves" in topics:
        return (
            "외환시장 충격에 대응할 여력이 확인됐다",
            f"{reason}. 외환보유액은 환율이 급하게 흔들릴 때 나라가 동원할 수 있는 외화 "
            "완충 장치의 규모를 보여줍니다.",
        )
    return "", ""


def _editorial_profile(
    text: str,
    category: str,
    domains: list[str],
    base_score: float,
    power_bonus: float,
) -> tuple[EditorialLens, list[str], list[str], list[str], list[str], float]:
    normalized = normalize_text(text)
    technology_terms = [term for term in GAME_CHANGER_DOMAIN_TERMS if term in normalized]
    breakthrough_terms = [term for term in GAME_CHANGER_BREAKTHROUGH_TERMS if term in normalized]
    operational_terms = [term for term in OPERATIONAL_TERMS if term in normalized]
    low_signal_count = sum(term in normalized for term in LOW_SIGNAL_TERMS)

    game_changer_signals: list[str] = []
    if technology_terms and breakthrough_terms:
        game_changer_signals = [
            f"{technology_terms[0]} 분야의 {breakthrough_terms[0]} 신호",
            "기존 성능·비용·치료 선택지를 바꿀 가능성",
        ]

    operational_risks = [OPERATIONAL_RISK_COPY[term] for term in operational_terms[:2]]
    timeline = sorted(
        set(
            re.findall(
                r"(?:20\d{2}년(?:\s*\d{1,2}월)?|\d{1,2}월|다음 달|내년|오늘|내일|이번 주)",
                text,
            )
        )
    )

    chain_domain = max(
        (domain for domain in CHAIN_STEPS if domain in domains),
        key=lambda domain: (
            sum(normalized.count(term) for term in DOMAIN_TERMS[domain]),
            -list(CHAIN_STEPS).index(domain),
        ),
        default=None,
    )
    impact_chain = CHAIN_STEPS[chain_domain] if chain_domain else []
    chain_candidate = bool(chain_domain and category in {"국제", "경제/거시", "정치", "부동산"})

    if power_bonus:
        lens = EditorialLens.POWER_MOVE
    elif game_changer_signals:
        lens = EditorialLens.GAME_CHANGER
    elif operational_risks:
        lens = EditorialLens.OPERATIONAL_RISK
    elif chain_candidate:
        lens = EditorialLens.REAL_WORLD_CHAIN
    else:
        lens = EditorialLens.STANDARD

    lens_bonus = {
        EditorialLens.POWER_MOVE: power_bonus,
        EditorialLens.GAME_CHANGER: 38,
        EditorialLens.OPERATIONAL_RISK: 28,
        EditorialLens.REAL_WORLD_CHAIN: 24,
        EditorialLens.STANDARD: 0,
    }[lens]
    priority_score = max(0.0, min(150.0, base_score + lens_bonus - low_signal_count * 28))
    return (
        lens,
        impact_chain,
        operational_risks,
        timeline,
        game_changer_signals,
        round(priority_score, 2),
    )


def _make_issue(
    signals: list[TrendSignal], articles: dict[str, Article], people: dict[str, str]
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
    combined = ". ".join(
        [representative.keyword, representative.reason]
        + [
            f"{articles[item].title}. {clean_summary_text(articles[item].description)}"
            for item in sorted(ranking_article_ids)
            if item in articles
        ]
    )
    entities = _entities(combined, set(people))
    decision_makers, consequential_actions, power_impact_chain, power_bonus = _power_profile(
        combined, people
    )
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
    (
        editorial_lens,
        impact_chain,
        operational_risks,
        timeline,
        game_changer_signals,
        priority_score,
    ) = _editorial_profile(combined, category, entities.market_domains, base_score, power_bonus)
    signal_kinds = sorted({signal.source_kind for signal in ranking_signals})
    reader_heading = ""
    reader_summary = ""
    if not editorial_signals and signal_kinds == ["bank_of_korea"]:
        reader_heading, reader_summary = _official_reader_copy(representative)
        default_announcement = f"한국은행이 「{representative.keyword}」 자료를 발표했습니다."
        detail = "" if representative.reason == default_announcement else representative.reason
        fact_text = (
            f"한국은행은 {representative.report_date.isoformat()}에 "
            f"「{representative.keyword}」 자료를 발표했습니다. "
            f"{detail}"
        ).strip()
    else:
        recent_summary = representative.reason or representative.keyword
        if normalize_text(recent_summary) == normalize_text(representative.keyword) and sources:
            recent_summary = sources[0].description or sources[0].title
        fact_text = recent_summary.strip()
        if fact_text and fact_text[-1] not in ".!?。":
            fact_text += "."
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
                text=(
                    "같은 주제의 한국은행 자료도 확인됩니다. "
                    f"{official_signal.reason or official_signal.keyword}"
                ),
                certainty=Certainty.HIGH,
            )
        )
    watches: list[str] = []
    explanations: list[str] = []
    for domain in entities.market_domains[:3]:
        explanation, watch = IMPACT_COPY[domain]
        explanations.append(explanation)
        watches.append(watch)
    if explanations:
        blocks.append(
            EvidenceBlock(
                kind=EvidenceType.INTERPRETATION,
                label="시장·생활 연결",
                text=" ".join(explanations),
                certainty=Certainty.MEDIUM,
            )
        )
    if not entities.market_domains:
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
        editorial_lens=editorial_lens,
        impact_chain=impact_chain,
        operational_risks=operational_risks,
        timeline=timeline,
        game_changer_signals=game_changer_signals,
        priority_score=priority_score,
        reader_heading=reader_heading,
        reader_summary=reader_summary,
        decision_makers=decision_makers,
        consequential_actions=consequential_actions,
        power_impact_chain=power_impact_chain,
    )


def _select_primary(issues: list[Issue]) -> list[Issue]:
    candidates = [
        issue
        for issue in issues
        if issue.sources
        and (
            issue.editorial_lens != EditorialLens.STANDARD
            or bool(set(issue.entities.market_domains) & CHAIN_DOMAINS)
        )
    ]
    if not candidates:
        return []
    ordered = sorted(
        candidates,
        key=lambda issue: (-issue.priority_score, -issue.score, -issue.active_days, issue.title),
    )
    selected: list[Issue] = []
    while ordered and len(selected) < 3:
        selected_people = {person for issue in selected for person in issue.entities.people}
        next_issue = max(
            ordered,
            key=lambda issue: (
                issue.priority_score - (18 if selected_people & set(issue.entities.people) else 0),
                issue.score,
                issue.active_days,
                issue.title,
            ),
        )
        selected.append(next_issue)
        ordered.remove(next_issue)
    return selected[:3]


def build_brief(days: list[SourceDay], as_of: date) -> WeeklyBrief:
    article_map = {article.stable_id: article for day in days for article in day.articles}
    people = {
        name: role
        for day in sorted(days, key=lambda item: item.report_date)
        for name, role in sorted(day.people.items())
    }
    all_signals = sorted(
        (
            trend
            for trend in [
                *(trend for day in days for trend in day.trends),
                *_person_action_signals(days, article_map),
            ]
            if _usable_keyword(trend.keyword)
        ),
        key=lambda item: (
            item.source_kind,
            normalize_text(item.keyword),
            item.report_date,
            item.keyword,
        ),
    )
    all_signals = [
        signal.model_copy(
            update={
                "article_ids": [
                    article_id
                    for article_id in signal.article_ids
                    if article_id in article_map
                    and (
                        len(signal.article_ids) == 1
                        or _relevant_article(signal, article_map[article_id])
                    )
                ]
            }
        )
        for signal in all_signals
    ]
    all_signals = [signal for signal in all_signals if signal.article_ids]
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
        key=lambda item: (
            -item[0].priority_score,
            -item[0].score,
            -item[0].active_days,
            item[0].title,
        ),
    )
    editorial_issues = [
        issue for issue, source_kinds in issue_records if "morningnews" in source_kinds
    ]
    primary = _select_primary(editorial_issues)
    primary_ids = {issue.issue_id for issue in primary}
    official_updates = [
        issue
        for issue, source_kinds in issue_records
        if issue.issue_id not in primary_ids
        and "morningnews" not in source_kinds
        and "bank_of_korea" in source_kinds
        and bool(_official_topics(issue.title) & PUBLIC_OFFICIAL_TOPICS)
        and bool(issue.reader_heading and issue.reader_summary)
    ][:2]
    official_ids = {issue.issue_id for issue in official_updates}
    currents = [
        issue
        for issue, source_kinds in issue_records
        if issue.issue_id not in primary_ids
        and issue.issue_id not in official_ids
        and "morningnews" in source_kinds
        and issue.priority_score >= 75
        and issue.sources
        and not any(
            term
            in normalize_text(
                " ".join(
                    [issue.title]
                    + [f"{source.title} {source.description}" for source in issue.sources]
                )
            )
            for term in LOW_SIGNAL_TERMS
        )
    ][:6]
    available = sorted({day.report_date for day in days if day.source_kind == "morningnews"})
    expected = [as_of - timedelta(days=offset) for offset in range(6, -1, -1)]
    missing = [day for day in expected if day not in available]
    reading_minutes = max(3, min(5, round((len(primary) * 180 + len(currents) * 90 + 300) / 500)))
    primary_domains = {domain for issue in primary for domain in issue.entities.market_domains}
    source_kinds = sorted({day.source_kind for day in days})
    source_labels = ", ".join(
        "수집된 뉴스 자료" if kind == "morningnews" else SOURCE_KIND_LABELS.get(kind, kind)
        for kind in source_kinds
    )
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
