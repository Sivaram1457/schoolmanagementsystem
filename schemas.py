"""
schemas.py — Pydantic models for request/response validation.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict

from models import UserRole


# ── Linkages ───────────────────────────────────────────────────────────────────

class ClassBase(BaseModel):
    name: str
    class_level: str
    section: str


class ClassCreate(ClassBase):
    pass


class ClassOut(ClassBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ── Auth Requests ──────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    full_name: str
    email: EmailStr


class UserCreate(UserBase):
    """Generic payload - used by admin or initial registration."""
    password: str
    role: UserRole = UserRole.student
    linked_student_id: Optional[int] = None
    class_id: Optional[int] = None


class StudentCreate(UserBase):
    """Specific payload for creating a Student."""
    password: str
    class_id: int  # Required for students
    role: UserRole = UserRole.student


class TeacherCreate(UserBase):
    """Specific payload for creating a Teacher."""
    password: str
    role: UserRole = UserRole.teacher


class ParentCreate(UserBase):
    """Specific payload for creating a Parent."""
    password: str
    student_ids: List[int]  # Required for parents: list of student IDs
    role: UserRole = UserRole.parent


class LoginRequest(BaseModel):
    """Payload for the login endpoint."""
    email: EmailStr
    password: str


# ── Auth Responses ─────────────────────────────────────────────────────────────

class UserSummary(BaseModel):
    """Minimal user info to prevent recursion."""
    id: int
    full_name: str
    class_id: Optional[int] = None
    role: UserRole
    
    model_config = ConfigDict(from_attributes=True)


class UserOut(UserBase):
    """Public representation of a user (no password hash)."""
    id: int
    role: UserRole
    
    # Relationships
    class_id: Optional[int] = None
    student_class: Optional[ClassOut] = None  # Nested class info
    
    # M2M Relationships
    children: List[UserSummary] = []  # For parents
    parents: List[UserSummary] = []   # For students
    
    # Legacy field
    linked_student_id: Optional[int] = None
    
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data encoded inside the JWT."""
    user_id: int
    role: str
