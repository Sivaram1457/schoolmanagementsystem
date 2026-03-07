"""Phase 2 — File Upload, Certificates, Announcements, Notifications

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-07 12:00:00.000000

Changes
-------
users
  + photo_url  VARCHAR(500)  nullable

New tables
  certificates
  announcement_target_role_enum  (PostgreSQL enum type)
  announcements
  notifications
"""

from alembic import op
from sqlalchemy import text

# ── Revision identifiers ───────────────────────────────────────────────────────
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


# ── Upgrade ───────────────────────────────────────────────────────────────────

def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add photo_url to users (idempotent)
    conn.execute(text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_url VARCHAR(500);"
    ))

    # 2. announcement_target_role enum (idempotent via DO block)
    conn.execute(text(
        "DO $$ BEGIN "
        "  CREATE TYPE announcement_target_role_enum AS ENUM "
        "    ('admin','teacher','student','parent','all'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    ))

    # 3. certificates table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS certificates (
            id          SERIAL PRIMARY KEY,
            student_id  INTEGER NOT NULL REFERENCES users(id),
            event_id    INTEGER NOT NULL REFERENCES events(id),
            file_url    VARCHAR(500) NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_certificate_student_event UNIQUE (student_id, event_id)
        );
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_certificate_event ON certificates (event_id);"
    ))

    # 4. announcements table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS announcements (
            id          SERIAL PRIMARY KEY,
            title       VARCHAR(200) NOT NULL,
            message     TEXT NOT NULL,
            target_role announcement_target_role_enum NOT NULL,
            created_by  INTEGER NOT NULL REFERENCES users(id),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_announcement_target     ON announcements (target_role);"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_announcement_created_at ON announcements (created_at);"
    ))

    # 5. notifications table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS notifications (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            title      VARCHAR(200) NOT NULL,
            message    TEXT NOT NULL,
            is_read    BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_notification_user_read ON notifications (user_id, is_read);"
    ))


# ── Downgrade ─────────────────────────────────────────────────────────────────

def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS idx_notification_user_read;"))
    conn.execute(text("DROP TABLE IF EXISTS notifications;"))
    conn.execute(text("DROP INDEX IF EXISTS idx_announcement_created_at;"))
    conn.execute(text("DROP INDEX IF EXISTS idx_announcement_target;"))
    conn.execute(text("DROP TABLE IF EXISTS announcements;"))
    conn.execute(text("DROP TYPE IF EXISTS announcement_target_role_enum;"))
    conn.execute(text("DROP INDEX IF EXISTS idx_certificate_event;"))
    conn.execute(text("DROP TABLE IF EXISTS certificates;"))
    conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS photo_url;"))
