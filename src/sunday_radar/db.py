from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from sunday_radar.adapters.morningnews import DailyInput


class Base(DeclarativeBase):
    pass


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"
    __table_args__ = (UniqueConstraint("source_kind", "report_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_kind: Mapped[str] = mapped_column(String(40))
    report_date: Mapped[date] = mapped_column(Date)
    content_hash: Mapped[str] = mapped_column(String(64))
    source_files: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime)
    occurrences: Mapped[list[ArticleOccurrence]] = relationship(cascade="all, delete-orphan")
    trends: Mapped[list[TrendRow]] = relationship(cascade="all, delete-orphan")


class ArticleRow(Base):
    __tablename__ = "articles"

    stable_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    description: Mapped[str] = mapped_column(Text)


class ArticleOccurrence(Base):
    __tablename__ = "article_occurrences"
    __table_args__ = (UniqueConstraint("snapshot_id", "article_id", "section"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("source_snapshots.id"))
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.stable_id"))
    section: Mapped[str] = mapped_column(String(100))


class TrendRow(Base):
    __tablename__ = "trend_signals"
    __table_args__ = (UniqueConstraint("snapshot_id", "normalized_keyword"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("source_snapshots.id"))
    keyword: Mapped[str] = mapped_column(String(300))
    normalized_keyword: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    categories_json: Mapped[str] = mapped_column(Text)
    article_ids_json: Mapped[str] = mapped_column(Text)


class Publication(Base):
    __tablename__ = "publications"

    week_ending: Mapped[date] = mapped_column(Date, primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30))
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    telegram_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


def create_db(path: Path) -> tuple[object, Session]:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def _daily_hash(day: DailyInput) -> str:
    digest = hashlib.sha256()
    for path in day.files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def import_day(session: Session, day: DailyInput) -> bool:
    content_hash = _daily_hash(day)
    existing = session.scalar(
        select(SourceSnapshot).where(
            SourceSnapshot.source_kind == "morningnews",
            SourceSnapshot.report_date == day.report_date,
        )
    )
    if existing and existing.content_hash == content_hash:
        return False
    if existing:
        session.delete(existing)
        session.flush()

    snapshot = SourceSnapshot(
        source_kind="morningnews",
        report_date=day.report_date,
        content_hash=content_hash,
        source_files=json.dumps([str(path) for path in day.files], ensure_ascii=False),
        imported_at=datetime.now(),
    )
    session.add(snapshot)
    session.flush()
    for article in day.articles:
        row = session.get(ArticleRow, article.stable_id)
        if row is None:
            row = ArticleRow(
                stable_id=article.stable_id,
                title=article.title,
                url=article.url,
                source=article.source,
                published_at=article.published_at,
                description=article.description,
            )
            session.add(row)
        session.add(
            ArticleOccurrence(
                snapshot_id=snapshot.id, article_id=article.stable_id, section=article.section
            )
        )
    from sunday_radar.normalization import normalize_text

    for trend in day.trends:
        session.add(
            TrendRow(
                snapshot_id=snapshot.id,
                keyword=trend.keyword,
                normalized_keyword=normalize_text(trend.keyword),
                reason=trend.reason,
                score=trend.score,
                categories_json=json.dumps(trend.categories, ensure_ascii=False),
                article_ids_json=json.dumps(trend.article_ids),
            )
        )
    session.commit()
    return True


def remove_orphan_articles(session: Session) -> None:
    used = select(ArticleOccurrence.article_id)
    session.execute(delete(ArticleRow).where(~ArticleRow.stable_id.in_(used)))
    session.commit()
