from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict

from sunday_radar.domain import Article, SourceDay, TrendSignal
from sunday_radar.normalization import canonical_url, normalize_text, stable_hash

SOURCE_KIND = "bank_of_korea"
SOURCE_NAME = "한국은행"
DEFAULT_FEED_URL = "https://www.bok.or.kr/portal/bbs/B0000552/news.rss?menuNo=200690"


class CachedRelease(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    link: str
    description: str = ""
    published_at: datetime


def _clean_title(value: str) -> str:
    return re.sub(r"^\[(?:보도자료|보도참고자료)\]\s*", "", value).strip()


def _clean_description(value: str) -> str:
    text = BeautifulSoup(unescape(value), "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[□■※*·\-]+\s*", "", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*으\s+로", r"\1으로", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s+p\b", r"\1p", text, flags=re.IGNORECASE)
    text = re.sub(r"([가-힣])\s+(의|은|는|이|가|을|를|와|과)\b", r"\1\2", text)
    text = re.sub(r"\s+(?:※|\*)\s*자세한 내용은.*$", "", text)
    if re.fullmatch(r"(?:자세한 내용은\s*)?.*(?:붙임|첨부파일).*(?:참조|참고).*", text):
        return ""
    return text.strip()


def parse_feed(xml: str) -> list[CachedRelease]:
    root = ET.fromstring(xml)
    releases: list[CachedRelease] = []
    for item in root.findall("./channel/item"):
        title = _clean_title(item.findtext("title", default=""))
        link = canonical_url(item.findtext("link", default=""))
        published = item.findtext("pubDate", default="").strip()
        if not title or not link or not published:
            continue
        releases.append(
            CachedRelease(
                title=title,
                link=link,
                description=_clean_description(item.findtext("description", default="")),
                published_at=parsedate_to_datetime(published),
            )
        )
    return sorted(releases, key=lambda item: (item.published_at, item.title))


def collect_window(
    cache_dir: Path,
    as_of: date,
    *,
    feed_url: str = DEFAULT_FEED_URL,
    client: httpx.Client | None = None,
) -> list[Path]:
    owns_client = client is None
    active_client = client or httpx.Client(timeout=30, follow_redirects=True)
    try:
        response = active_client.get(feed_url)
        response.raise_for_status()
        releases = parse_feed(response.text)
    finally:
        if owns_client:
            active_client.close()

    window_start = as_of - timedelta(days=6)
    grouped: dict[date, list[CachedRelease]] = {}
    for release in releases:
        report_date = release.published_at.date()
        if window_start <= report_date <= as_of:
            grouped.setdefault(report_date, []).append(release)

    cache_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for report_date, items in sorted(grouped.items()):
        path = cache_dir / f"releases_{report_date:%Y%m%d}.json"
        payload = {
            "source_kind": SOURCE_KIND,
            "report_date": report_date.isoformat(),
            "feed_url": feed_url,
            "data": [item.model_dump(mode="json") for item in items],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def load_day(cache_dir: Path, report_date: date) -> SourceDay:
    path = cache_dir / f"releases_{report_date:%Y%m%d}.json"
    if not path.exists():
        return SourceDay(
            source_kind=SOURCE_KIND, report_date=report_date, files=[], articles=[], trends=[]
        )

    payload = _read_json(path)
    raw_items = payload.get("data", [])
    if not isinstance(raw_items, list):
        raise ValueError(f"release data must be a list: {path}")

    articles: list[Article] = []
    trends: list[TrendSignal] = []
    for raw_item in raw_items:
        release = CachedRelease.model_validate(raw_item)
        description = _clean_description(release.description)
        article_id = stable_hash(release.link, SOURCE_NAME, release.published_at.isoformat())
        article = Article(
            stable_id=article_id,
            title=release.title,
            url=release.link,
            source=SOURCE_NAME,
            published_at=release.published_at,
            description=description,
            section="경제/거시",
            report_date=report_date,
            source_kind=SOURCE_KIND,
        )
        articles.append(article)
        trends.append(
            TrendSignal(
                keyword=release.title,
                reason=description or f"한국은행이 「{release.title}」 자료를 발표했습니다.",
                score=20.0,
                categories=["경제/거시"],
                report_date=report_date,
                article_ids=[article_id],
                source_kind=SOURCE_KIND,
            )
        )
    return SourceDay(
        source_kind=SOURCE_KIND,
        report_date=report_date,
        files=[path],
        articles=sorted(articles, key=lambda item: item.stable_id),
        trends=sorted(trends, key=lambda item: (normalize_text(item.keyword), item.keyword)),
    )


def load_window(cache_dir: Path, as_of: date) -> list[SourceDay]:
    days = [load_day(cache_dir, as_of - timedelta(days=offset)) for offset in range(6, -1, -1)]
    return [day for day in days if day.files]
