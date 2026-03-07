"""Phase 1 — Optimise: add composite indexes for timetable and event reads

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-07 01:00:00.000000

Adds:
  timetable_slots:
    idx_class_day_period   (class_id, day_of_week, period_id)
    idx_teacher_day_period (teacher_id, day_of_week, period_id)

  event_registrations:
    idx_event_student      (event_id, student_id)
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Timetable: covering index for class weekly page load
    op.create_index(
        "idx_class_day_period",
        "timetable_slots",
        ["class_id", "day_of_week", "period_id"],
    )

    # Timetable: covering index for teacher schedule lookup
    op.create_index(
        "idx_teacher_day_period",
        "timetable_slots",
        ["teacher_id", "day_of_week", "period_id"],
    )

    # Event registrations: composite covering index for duplicate-check queries
    op.create_index(
        "idx_event_student",
        "event_registrations",
        ["event_id", "student_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_event_student", table_name="event_registrations")
    op.drop_index("idx_teacher_day_period", table_name="timetable_slots")
    op.drop_index("idx_class_day_period", table_name="timetable_slots")
