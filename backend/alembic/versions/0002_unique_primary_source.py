"""Enforce one primary source mapping per canonical series.

Revision ID: 0002_unique_primary_source
Revises: 0001_initial
Create Date: 2026-08-13
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_unique_primary_source"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_series",
        sa.Column("verification_job_id", sa.UUID(), nullable=True),
        schema="source",
    )
    op.add_column(
        "source_series",
        sa.Column("verification_fingerprint", sa.String(length=64), nullable=True),
        schema="source",
    )
    op.create_foreign_key(
        "source_series_verification_job_fk",
        "source_series",
        "job",
        ["verification_job_id"],
        ["id"],
        source_schema="source",
        referent_schema="app",
    )
    op.create_unique_constraint(
        "source_series_verification_job_key",
        "source_series",
        ["verification_job_id"],
        schema="source",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX one_primary_source_per_series
        ON source.source_series(series_id)
        WHERE is_primary
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS source.one_primary_source_per_series")
    op.drop_constraint(
        "source_series_verification_job_key",
        "source_series",
        schema="source",
        type_="unique",
    )
    op.drop_constraint(
        "source_series_verification_job_fk",
        "source_series",
        schema="source",
        type_="foreignkey",
    )
    op.drop_column("source_series", "verification_fingerprint", schema="source")
    op.drop_column("source_series", "verification_job_id", schema="source")
