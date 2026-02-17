"""
models.py — SQLAlchemy ORM models for the School Management System.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class UserRole(str, enum.Enum):
    """Allowed user roles."""
    admin = "admin"
    teacher = "teacher"
    student = "student"
    parent = "parent"


# Association table must be defined before User to be referenced
student_parents = Table(
    "student_parents",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("parent_id", Integer, ForeignKey("users.id"), primary_key=True),
)


class Class(Base):
    """Class model (e.g. 10A)."""
    
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(20), unique=True, nullable=False, index=True)  # e.g. "10A"
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

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.student)
    
    # Class Linkage (Students only)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    
    # Legacy field (keep for compatibility/migration ease if needed, but logic uses association table now)
    linked_student_id = Column(Integer, nullable=True) # DEPRECATED: Use students/parents relationship
    
    class_level = Column(String(50), nullable=True)
    
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
