"""
models.py — SQLAlchemy ORM models for the School Management System.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Table, Date, UniqueConstraint, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


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
