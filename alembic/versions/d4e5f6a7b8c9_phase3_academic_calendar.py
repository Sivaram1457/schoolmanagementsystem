"""Phase 3 — Academic Calendar table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-07 15:00:00.000000

Changes
-------
New table: academic_calendar
  id, date, type (calendar_entry_type_enum), description, created_by, created_at

Indexes
  idx_calendar_date   (date)
  idx_calendar_type   (type)
"""

from alembic import op
from sqlalchemy import text

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create enum type (idempotent)
    conn.execute(text(
        "DO $$ BEGIN "
        "  CREATE TYPE calendar_entry_type_enum AS ENUM "
        "    ('holiday','exam','event','non_working'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    ))

    # 2. Create table (idempotent)
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS academic_calendar (
            id          SERIAL PRIMARY KEY,
            date        DATE NOT NULL,
            type        calendar_entry_type_enum NOT NULL,
            description VARCHAR(300) NOT NULL DEFAULT '',
            created_by  INTEGER NOT NULL REFERENCES users(id),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_calendar_date_type UNIQUE (date, type)
        );
    """))

    # 3. Indexes (idempotent)
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_calendar_date ON academic_calendar (date);"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_calendar_type ON academic_calendar (type);"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS idx_calendar_type;"))
    conn.execute(text("DROP INDEX IF EXISTS idx_calendar_date;"))
    conn.execute(text("DROP TABLE IF EXISTS academic_calendar;"))
    conn.execute(text("DROP TYPE IF EXISTS calendar_entry_type_enum;"))
