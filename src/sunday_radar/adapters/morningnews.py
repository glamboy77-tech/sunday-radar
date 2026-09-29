from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sunday_radar.domain import Article, SourceDay, TrendSignal
from sunday_radar.normalization import canonical_url, normalize_text, stable_hash


class RawArticle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    link: str = ""
    source: str = "알 수 없음"
    published_dt: str | None = None
    description: str = ""


class RawTrend(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keyword: str
    reason: str = ""
    score: float = 0.0
    categories: list[str] = Field(default_factory=list)
    representative_article: RawArticle | None = None
    related_articles: list[RawArticle] = Field(default_factory=list)


def date_window(as_of: date, days: int = 7) -> list[date]:
    return [as_of - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _article(raw: RawArticle, report_date: date, section: str) -> Article:
    url = canonical_url(raw.link)
    published = _parse_datetime(raw.published_dt)
    stable_id = stable_hash(
        url or normalize_text(raw.title), raw.source, published.isoformat() if published else ""
    )
    return Article(
        stable_id=stable_id,
        title=raw.title.strip(),
        url=url,
        source=raw.source.strip() or "알 수 없음",
        published_at=published,
        description=raw.description.strip(),
        section=section,
        report_date=report_date,
        source_kind="morningnews",
    )


def load_day(root: Path, report_date: date) -> SourceDay:
    stamp = report_date.strftime("%Y%m%d")
    cache_dir = root / "data_cache"
    sentiment_dir = root / "sentiment_cache"
    files: list[Path] = []
    articles: dict[str, Article] = {}
    trends: list[TrendSignal] = []
    people: dict[str, str] = {}
    person_article_ids: dict[str, list[str]] = {}
    summaries: dict[str, str] = {}

    ai_path = cache_dir / f"ai_analysis_{stamp}.json"
    if ai_path.exists():
        files.append(ai_path)
        payload = _read_json(ai_path).get("data", {})
        if not isinstance(payload, dict):
            raise ValueError(f"ai_analysis data must be an object: {ai_path}")
        for section, raw_items in sorted(payload.items()):
            if not isinstance(raw_items, list):
                continue
            for raw_item in raw_items:
                parsed = RawArticle.model_validate(raw_item)
                item = _article(parsed, report_date, str(section))
                if item.title:
                    articles[item.stable_id] = item

    trend_path = cache_dir / f"trending_keywords_{stamp}.json"
    if trend_path.exists():
        files.append(trend_path)
        raw_trends = _read_json(trend_path).get("data", [])
        if not isinstance(raw_trends, list):
            raise ValueError(f"trending_keywords data must be a list: {trend_path}")
        for raw_trend in raw_trends:
            parsed_trend = RawTrend.model_validate(raw_trend)
            related = list(parsed_trend.related_articles)
            if parsed_trend.representative_article:
                related.append(parsed_trend.representative_article)
            article_ids: list[str] = []
            for raw_article in related:
                item = _article(
                    raw_article,
                    report_date,
                    parsed_trend.categories[0] if parsed_trend.categories else "기타",
                )
                if item.title:
                    articles[item.stable_id] = item
                    article_ids.append(item.stable_id)
            trends.append(
                TrendSignal(
                    keyword=parsed_trend.keyword.strip(),
                    reason=parsed_trend.reason.strip(),
                    score=parsed_trend.score,
                    categories=sorted(set(parsed_trend.categories)),
                    report_date=report_date,
                    article_ids=sorted(set(article_ids)),
                    source_kind="morningnews",
                )
            )

    people_path = cache_dir / f"key_persons_{stamp}.json"
    if people_path.exists():
        files.append(people_path)
        raw_people = _read_json(people_path).get("data", {})
        if isinstance(raw_people, dict):
            for name, value in raw_people.items():
                if isinstance(value, dict):
                    person_name = str(name)
                    people[person_name] = str(value.get("role", ""))
                    related_ids: list[str] = []
                    raw_articles = value.get("articles", [])
                    if isinstance(raw_articles, list):
                        for raw_article in raw_articles:
                            parsed = RawArticle.model_validate(raw_article)
                            item = _article(parsed, report_date, "주요 인물")
                            if item.title:
                                articles[item.stable_id] = item
                                related_ids.append(item.stable_id)
                    if related_ids:
                        person_article_ids[person_name] = sorted(set(related_ids))

    sentiment_path = sentiment_dir / f"sentiment_{stamp}.json"
    if sentiment_path.exists():
        files.append(sentiment_path)
        raw_summaries = _read_json(sentiment_path).get("section_summaries", {})
        if isinstance(raw_summaries, dict):
            summaries = {str(key): str(value) for key, value in raw_summaries.items()}

    return SourceDay(
        source_kind="morningnews",
        report_date=report_date,
        files=sorted(files),
        articles=sorted(articles.values(), key=lambda item: item.stable_id),
        trends=sorted(trends, key=lambda item: (normalize_text(item.keyword), item.keyword)),
        people=people,
        person_article_ids=person_article_ids,
        section_summaries=summaries,
    )


def load_window(root: Path, as_of: date) -> list[SourceDay]:
    inputs = [load_day(root, day) for day in date_window(as_of)]
    return [daily_input for daily_input in inputs if daily_input.files]
