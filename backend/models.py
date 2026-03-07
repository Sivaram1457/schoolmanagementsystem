"""
models.py — SQLAlchemy ORM models for the School Management System.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Table, Date, UniqueConstraint, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class UserRole(str, enum.Enum):
    """Allowed user roles."""
    admin = "admin"
    teacher = "teacher"
    student = "student"
    parent = "parent"


class AttendanceStatus(str, enum.Enum):
    """Attendance status types."""
    present = "present"
    absent = "absent"


# Association table must be defined before User to be referenced
student_parents = Table(
    "student_parents",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("parent_id", Integer, ForeignKey("users.id"), primary_key=True),
    extend_existing=True
)


class Class(Base):
    """Class model (e.g. 10A)."""
    
    __tablename__ = "classes"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)  # e.g. "10A"
    class_level = Column(String(10), nullable=False)  # e.g. "10"
    section = Column(String(5), nullable=False)       # e.g. "A"
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    students = relationship("User", back_populates="student_class")

    def __repr__(self) -> str:
        return f"<Class {self.name}>"


class User(Base):
    """User account model."""

    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole, name="user_role_enum"), nullable=False, default=UserRole.student)
    
    # Class Linkage (Students only)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    
    # Legacy field (keep for compatibility/migration ease if needed, but logic uses association table now)
    linked_student_id = Column(Integer, nullable=True) # DEPRECATED: Use students/parents relationship
    
    class_level = Column(String(50), nullable=True)

    is_email_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, server_default="true", index=True)

    # Phase 2: file upload
    photo_url = Column(String(500), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    student_class = relationship("Class", back_populates="students")

    # M2M: Parent <-> Student
    # If this user is a PARENT, 'children' returns their students.
    # If this user is a STUDENT, 'parents' returns their parents.
    children = relationship(
        "User",
        secondary=student_parents,
        primaryjoin=(id == student_parents.c.parent_id),
        secondaryjoin=(id == student_parents.c.student_id),
        backref="parents",
        lazy="selectin" # Eager load for API
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"


class Attendance(Base):
    """Attendance record model."""

    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    status = Column(Enum(AttendanceStatus, name="attendance_status_enum"), nullable=False)
    marked_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    last_updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # Constraints & Indexes
    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_attendance_student_date"),
        Index("idx_attendance_class_date", "class_id", "date"),
        {"extend_existing": True},
    )

    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    teacher = relationship("User", foreign_keys=[marked_by])
    attendance_class = relationship("Class")

    def __repr__(self) -> str:
        return f"<Attendance student={self.student_id} date={self.date} status={self.status.value}>"


class Subject(Base):
    """Subject model (e.g. Mathematics, Science)."""

    __tablename__ = "subjects"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(20), unique=True, nullable=True)  # e.g. "MATH101"

    def __repr__(self) -> str:
        return f"<Subject {self.name}>"


class AcademicMapping(Base):
    """Teacher-Subject-Class mapping model."""

    __tablename__ = "academic_mappings"
    __table_args__ = (
        UniqueConstraint("teacher_id", "subject_id", "class_id", name="uq_teacher_subject_class"),
        {"extend_existing": True}
    )

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)

    # Relationships
    teacher = relationship("User")
    subject = relationship("Subject")
    mapping_class = relationship("Class")

    def __repr__(self) -> str:
        return f"<Mapping Teacher={self.teacher_id} Subject={self.subject_id} Class={self.class_id}>"


class Homework(Base):
    """Homework model."""

    __tablename__ = "homework"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    description = Column(String, nullable=False)  # Using String for Text
    due_date = Column(Date, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    # Indexes
    __table_args__ = (
        Index("idx_homework_class_due", "class_id", "due_date"),
        {"extend_existing": True},
    )

    # Relationships
    homework_class = relationship("Class")
    teacher = relationship("User")

    def __repr__(self) -> str:
        return f"<Homework id={self.id} title={self.title!r}>"


class RefreshToken(Base):
    """Refresh token record used for rotating refresh tokens."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
        Index("ix_refresh_tokens_user_id", "user_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_revoked = Column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<RefreshToken user={self.user_id} revoked={self.is_revoked} expires={self.expires_at}>"


class PasswordResetToken(Base):
    """Single-use token for resetting passwords."""

    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_password_reset_hash"),
        Index("ix_password_reset_user_id", "user_id"),
        Index("ix_password_reset_expires", "expires_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_used = Column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<PasswordResetToken user={self.user_id} used={self.is_used} expires={self.expires_at}>"


class EmailVerificationToken(Base):
    """Token supporting email verification process."""

    __tablename__ = "email_verification_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_email_verification_hash"),
        Index("ix_email_verification_user_id", "user_id"),
        Index("ix_email_verification_expires", "expires_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_used = Column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<EmailVerificationToken user={self.user_id} used={self.is_used} expires={self.expires_at}>"


class HomeworkSubmission(Base):
    """Homework submission/completion record by a student."""

    __tablename__ = "homework_submissions"
    __table_args__ = (
        UniqueConstraint("homework_id", "student_id", name="uq_homework_student"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(Integer, ForeignKey("homework.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    is_completed = Column(Boolean, default=True, nullable=False)
    completed_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    student = relationship("User")
    homework = relationship("Homework", backref="submissions")

    def __repr__(self) -> str:
        return f"<HomeworkSubmission hw={self.homework_id} student={self.student_id} completed={self.is_completed}>"


# ── Phase 1: Timetable Engine ─────────────────────────────────────────────────

class Period(Base):
    """A named school period with a fixed start and end time (e.g. Period 1: 08:00–08:45)."""

    __tablename__ = "periods"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    period_number = Column(Integer, nullable=False, unique=True)
    start_time = Column(String(5), nullable=False)   # "HH:MM" stored as string for portability
    end_time = Column(String(5), nullable=False)

    # Relationships
    timetable_slots = relationship("TimetableSlot", back_populates="period")

    def __repr__(self) -> str:
        return f"<Period {self.period_number} {self.start_time}-{self.end_time}>"


class Room(Base):
    """A physical classroom or lab that can host one class per period at a time."""

    __tablename__ = "rooms"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    room_name = Column(String(100), nullable=False, unique=True, index=True)
    capacity = Column(Integer, nullable=True)

    # Relationships
    timetable_slots = relationship("TimetableSlot", back_populates="room")

    def __repr__(self) -> str:
        return f"<Room {self.room_name} cap={self.capacity}>"


class TimetableSlot(Base):
    """
    A single timetable entry: a specific class is taught by a teacher
    in a room during a period on a given day of the week.

    0 = Monday … 6 = Sunday (ISO convention).
    """

    __tablename__ = "timetable_slots"
    __table_args__ = (
        # A teacher cannot teach two classes in the same period on the same day
        UniqueConstraint("teacher_id", "day_of_week", "period_id", name="uq_teacher_day_period"),
        # A room cannot host two classes in the same period on the same day
        UniqueConstraint("room_id", "day_of_week", "period_id", name="uq_room_day_period"),
        # Composite index for class weekly timetable queries (most used read path)
        Index("idx_timetable_class_day", "class_id", "day_of_week"),
        # Covers full class+day+period lookups — used on every timetable page load
        Index("idx_class_day_period", "class_id", "day_of_week", "period_id"),
        # Covers teacher schedule lookups — used on teacher dashboard
        Index("idx_teacher_day_period", "teacher_id", "day_of_week", "period_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)   # 0=Mon … 6=Sun
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=False, index=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    slot_class = relationship("Class")
    subject = relationship("Subject")
    teacher = relationship("User")
    room = relationship("Room", back_populates="timetable_slots")
    period = relationship("Period", back_populates="timetable_slots")

    def __repr__(self) -> str:
        return (
            f"<TimetableSlot class={self.class_id} day={self.day_of_week} "
            f"period={self.period_id} teacher={self.teacher_id}>"
        )


# ── Phase 1: Event Management System ─────────────────────────────────────────

class EventRegistrationStatus(str, enum.Enum):
    """Allowed event participation statuses."""
    registered = "registered"
    attended = "attended"
    winner = "winner"


class Event(Base):
    """A school event: competition, activity, ceremony, etc."""

    __tablename__ = "events"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(String, nullable=True)
    event_date = Column(Date, nullable=False, index=True)
    # Optional — if NULL the event is open to the whole school
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    event_class = relationship("Class")
    registrations = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Event id={self.id} title={self.title!r} date={self.event_date}>"


class EventRegistration(Base):
    """A student's registration / participation record for an event."""

    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "student_id", name="uq_event_student"),
        # Dedicated read index for participant listing — faster than relying on UNIQUE alone
        Index("idx_event_registrations_event", "event_id"),
        # Composite covering index for duplicate-registration check
        Index("idx_event_student", "event_id", "student_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(
        Enum(EventRegistrationStatus, name="event_registration_status_enum"),
        nullable=False,
        default=EventRegistrationStatus.registered,
    )
    registered_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    event = relationship("Event", back_populates="registrations")
    student = relationship("User", foreign_keys=[student_id])

    def __repr__(self) -> str:
        return f"<EventRegistration event={self.event_id} student={self.student_id} status={self.status.value}>"


# ── Phase 2: Certificate Generator ───────────────────────────────────────────

class Certificate(Base):
    """PDF certificate issued to an event participant."""

    __tablename__ = "certificates"
    __table_args__ = (
        UniqueConstraint("student_id", "event_id", name="uq_certificate_student_event"),
        Index("idx_certificate_event", "event_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    file_url = Column(String(500), nullable=False)
    generated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    event = relationship("Event")

    def __repr__(self) -> str:
        return f"<Certificate student={self.student_id} event={self.event_id}>"


# ── Phase 2: Announcement System ─────────────────────────────────────────────

class AnnouncementTargetRole(str, enum.Enum):
    """Who can see an announcement."""
    admin = "admin"
    teacher = "teacher"
    student = "student"
    parent = "parent"
    all = "all"


class Announcement(Base):
    """School-wide or role-targeted announcement."""

    __tablename__ = "announcements"
    __table_args__ = (
        Index("idx_announcement_target", "target_role"),
        Index("idx_announcement_created_at", "created_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    message = Column(String, nullable=False)
    target_role = Column(
        Enum(AnnouncementTargetRole, name="announcement_target_role_enum"),
        nullable=False,
        default=AnnouncementTargetRole.all,
        index=True,
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    author = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<Announcement id={self.id} title={self.title!r} target={self.target_role.value}>"


# ── Phase 2: Notification Storage ────────────────────────────────────────────

class Notification(Base):
    """Per-user notification record."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notification_user_read", "user_id", "is_read"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user={self.user_id} read={self.is_read}>"


# ── Phase 3: Academic Calendar ────────────────────────────────────────────────

class CalendarEntryType(str, enum.Enum):
    """Type of a calendar entry."""
    holiday = "holiday"
    exam = "exam"
    event = "event"
    non_working = "non_working"


class AcademicCalendar(Base):
    """
    A date-based academic calendar entry.

    Holidays / non-working days are used by the analytics engine to exclude
    those dates from attendance-rate denominators.
    """

    __tablename__ = "academic_calendar"
    __table_args__ = (
        UniqueConstraint("date", "type", name="uq_calendar_date_type"),
        Index("idx_calendar_date", "date"),
        Index("idx_calendar_type", "type"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    type = Column(
        Enum(CalendarEntryType, name="calendar_entry_type_enum"),
        nullable=False,
        index=True,
    )
    description = Column(String(300), nullable=False, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    author = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<AcademicCalendar {self.date} type={self.type.value}>"
