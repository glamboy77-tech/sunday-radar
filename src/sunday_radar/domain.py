from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EvidenceType(StrEnum):
    FACT = "fact"
    OFFICIAL_CLAIM = "official_claim"
    INTERPRETATION = "interpretation"
    SCENARIO = "scenario"


class Certainty(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Article(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stable_id: str
    title: str
    url: str
    source: str
    published_at: datetime | None = None
    description: str = ""
    section: str = "기타"
    report_date: date
    source_kind: str = "unknown"


class TrendSignal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keyword: str
    reason: str = ""
    score: float = 0.0
    categories: list[str] = Field(default_factory=list)
    report_date: date
    article_ids: list[str] = Field(default_factory=list)
    source_kind: str = "unknown"


class SourceDay(BaseModel):
    source_kind: str
    report_date: date
    files: list[Path]
    articles: list[Article]
    trends: list[TrendSignal]
    people: dict[str, str] = Field(default_factory=dict)
    section_summaries: dict[str, str] = Field(default_factory=dict)


class EntitySet(BaseModel):
    people: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    market_domains: list[str] = Field(default_factory=list)


class EvidenceBlock(BaseModel):
    kind: EvidenceType
    label: str
    text: str
    certainty: Certainty


class SourceLink(BaseModel):
    title: str
    source: str
    url: HttpUrl
    source_kind: str = "unknown"
    description: str = ""
    report_date: date | None = None


class Issue(BaseModel):
    issue_id: str
    title: str
    category: str
    score: float
    first_seen: date
    last_seen: date
    active_days: int
    entities: EntitySet
    blocks: list[EvidenceBlock]
    watch_variables: list[str]
    sources: list[SourceLink]


class WeeklyBrief(BaseModel):
    week_ending: date
    window_start: date
    window_end: date
    generated_at: datetime
    input_days: list[date]
    missing_days: list[date]
    source_kinds: list[str]
    headline: str
    overview: str
    issues: list[Issue]
    official_updates: list[Issue]
    currents: list[Issue]
    reading_minutes: int
    methodology_note: str


class EditorialParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EvidenceType
    text: str = Field(min_length=20, max_length=900)
    source_ids: list[str] = Field(max_length=4)


class EditorialSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    heading: str = Field(min_length=4, max_length=100)
    paragraphs: list[EditorialParagraph] = Field(min_length=2, max_length=4)


class EditorialDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=8, max_length=100)
    overview: str = Field(min_length=30, max_length=500)
    sections: list[EditorialSection] = Field(min_length=1, max_length=3)
    transitions: list[str] = Field(max_length=2)
    conclusion: str = Field(min_length=30, max_length=500)
