"""Phase 1 — Core Academic Engine: timetable and events

Revision ID: a1b2c3d4e5f6
Revises: 8c9d1ef4b5a4
Create Date: 2026-03-07 00:00:00.000000

Adds:
  - periods            (school period definitions)
  - rooms              (classrooms / labs)
  - timetable_slots    (weekly schedule entries)
  - events             (school activities / competitions)
  - event_registrations (student sign-ups)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "8c9d1ef4b5a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ────────────────────────────────────────────
    # 1.  periods
    # ────────────────────────────────────────────
    op.create_table(
        "periods",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.UniqueConstraint("period_number", name="uq_periods_number"),
    )
    op.create_index("ix_periods_id", "periods", ["id"])

    # ────────────────────────────────────────────
    # 2.  rooms
    # ────────────────────────────────────────────
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("room_name", sa.String(length=100), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.UniqueConstraint("room_name", name="uq_rooms_name"),
    )
    op.create_index("ix_rooms_id", "rooms", ["id"])
    op.create_index("ix_rooms_room_name", "rooms", ["room_name"])

    # ────────────────────────────────────────────
    # 3.  timetable_slots
    # ────────────────────────────────────────────
    op.create_table(
        "timetable_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("periods.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        # No two classes taught by same teacher at the same time
        sa.UniqueConstraint(
            "teacher_id", "day_of_week", "period_id",
            name="uq_teacher_day_period",
        ),
        # No two classes in the same room at the same time
        sa.UniqueConstraint(
            "room_id", "day_of_week", "period_id",
            name="uq_room_day_period",
        ),
    )
    op.create_index("ix_timetable_slots_id", "timetable_slots", ["id"])
    op.create_index("ix_timetable_slots_class_id", "timetable_slots", ["class_id"])
    op.create_index("ix_timetable_slots_subject_id", "timetable_slots", ["subject_id"])
    op.create_index("ix_timetable_slots_teacher_id", "timetable_slots", ["teacher_id"])
    op.create_index("ix_timetable_slots_room_id", "timetable_slots", ["room_id"])
    op.create_index("ix_timetable_slots_period_id", "timetable_slots", ["period_id"])
    op.create_index(
        "idx_timetable_class_day",
        "timetable_slots",
        ["class_id", "day_of_week"],
    )

    # ────────────────────────────────────────────
    # 4.  events
    # ────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_events_id", "events", ["id"])
    op.create_index("ix_events_title", "events", ["title"])
    op.create_index("ix_events_event_date", "events", ["event_date"])
    op.create_index("ix_events_class_id", "events", ["class_id"])
    op.create_index("ix_events_created_by", "events", ["created_by"])
    op.create_index("ix_events_is_deleted", "events", ["is_deleted"])

    # ────────────────────────────────────────────
    # 5.  event_registration_status_enum
    #     (PostgreSQL needs explicit enum creation)
    # ────────────────────────────────────────────
    reg_status_enum = sa.Enum(
        "registered", "attended", "winner",
        name="event_registration_status_enum",
    )
    reg_status_enum.create(op.get_bind(), checkfirst=True)

    # ────────────────────────────────────────────
    # 6.  event_registrations
    # ────────────────────────────────────────────
    op.create_table(
        "event_registrations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("registered", "attended", "winner", name="event_registration_status_enum"),
            nullable=False,
            server_default="registered",
        ),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "event_id", "student_id",
            name="uq_event_student",
        ),
    )
    op.create_index("ix_event_registrations_id", "event_registrations", ["id"])
    op.create_index("ix_event_registrations_event_id", "event_registrations", ["event_id"])
    op.create_index("ix_event_registrations_student_id", "event_registrations", ["student_id"])
    op.create_index(
        "idx_event_registrations_event",
        "event_registrations",
        ["event_id"],
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("idx_event_registrations_event", table_name="event_registrations")
    op.drop_index("ix_event_registrations_student_id", table_name="event_registrations")
    op.drop_index("ix_event_registrations_event_id", table_name="event_registrations")
    op.drop_index("ix_event_registrations_id", table_name="event_registrations")
    op.drop_table("event_registrations")

    sa.Enum(name="event_registration_status_enum").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_events_is_deleted", table_name="events")
    op.drop_index("ix_events_created_by", table_name="events")
    op.drop_index("ix_events_class_id", table_name="events")
    op.drop_index("ix_events_event_date", table_name="events")
    op.drop_index("ix_events_title", table_name="events")
    op.drop_index("ix_events_id", table_name="events")
    op.drop_table("events")

    op.drop_index("idx_timetable_class_day", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_period_id", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_room_id", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_teacher_id", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_subject_id", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_class_id", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_id", table_name="timetable_slots")
    op.drop_table("timetable_slots")

    op.drop_index("ix_rooms_room_name", table_name="rooms")
    op.drop_index("ix_rooms_id", table_name="rooms")
    op.drop_table("rooms")

    op.drop_index("ix_periods_id", table_name="periods")
    op.drop_table("periods")
