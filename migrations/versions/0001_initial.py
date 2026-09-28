"""Initial Sunday Radar schema.

Revision ID: 0001
Revises:
Create Date: 2026-09-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "articles",
        sa.Column("stable_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("stable_id"),
    )
    op.create_table(
        "publications",
        sa.Column("week_ending", sa.Date(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("telegram_sent_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("week_ending"),
    )
    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_files", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_kind", "report_date"),
    )
    op.create_table(
        "article_occurrences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.String(length=64), nullable=False),
        sa.Column("section", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.stable_id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["source_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "article_id", "section"),
    )
    op.create_table(
        "trend_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("keyword", sa.String(length=300), nullable=False),
        sa.Column("normalized_keyword", sa.String(length=300), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("categories_json", sa.Text(), nullable=False),
        sa.Column("article_ids_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["source_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "normalized_keyword"),
    )


def downgrade() -> None:
    op.drop_table("trend_signals")
    op.drop_table("article_occurrences")
    op.drop_table("source_snapshots")
    op.drop_table("publications")
    op.drop_table("articles")
