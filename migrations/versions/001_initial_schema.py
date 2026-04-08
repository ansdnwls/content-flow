"""Initial schema — baseline from infra/supabase/01_schema.sql.

Revision ID: 001
Revises: None
Create Date: 2025-01-01 00:00:00.000000
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

_SCHEMA_FILE = Path(__file__).resolve().parents[2] / "infra" / "supabase" / "01_schema.sql"
_RLS_FILE = Path(__file__).resolve().parents[2] / "infra" / "supabase" / "02_rls.sql"


def upgrade() -> None:
    if _SCHEMA_FILE.exists():
        for statement in _split_sql(_SCHEMA_FILE.read_text(encoding="utf-8")):
            op.execute(statement)
    if _RLS_FILE.exists():
        for statement in _split_sql(_RLS_FILE.read_text(encoding="utf-8")):
            op.execute(statement)


def downgrade() -> None:
    tables = [
        "trending_snapshots",
        "video_templates",
        "webhook_deliveries",
        "analytics_snapshots",
        "schedules",
        "comments",
        "bombs",
        "webhooks",
        "video_jobs",
        "post_deliveries",
        "posts",
        "social_accounts",
        "api_keys",
        "users",
    ]
    for table in tables:
        op.execute(f"drop table if exists public.{table} cascade")
    op.execute("drop function if exists public.set_updated_at() cascade")


def _split_sql(sql: str) -> list[str]:
    """Split SQL text into individual statements, skipping empty ones."""
    return [s.strip() for s in sql.split(";") if s.strip()]
