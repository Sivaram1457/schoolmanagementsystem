"""
schemas.py — Pydantic models for request/response validation.
"""

from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, EmailStr, ConfigDict
from pydantic.generics import GenericModel

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


T = TypeVar("T")


class PaginatedResponse(GenericModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int


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


class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    class_id: Optional[int] = None


class TeacherUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class ParentUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    student_ids: Optional[List[int]] = None


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
    is_active: bool
    
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
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data encoded inside the JWT."""
    user_id: int
    role: str


class RefreshRequest(BaseModel):
    """Payload for refresh and logout endpoints."""
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class MessageResponse(BaseModel):
    detail: str


class BulkUploadError(BaseModel):
    row: int
    error: str


class StudentBulkUploadResponse(BaseModel):
    created: int
    failed: int
    errors: List[BulkUploadError]


# ── Attendance ─────────────────────────────────────────────────────────────────

from models import AttendanceStatus
from datetime import date


class AttendanceBase(BaseModel):
    student_id: int
    class_id: int
    date: date
    status: AttendanceStatus


class AttendanceCreate(AttendanceBase):
    marked_by: int


class AttendanceStudentItem(BaseModel):
    """Used in bulk request."""
    student_id: int
    status: AttendanceStatus


class AttendanceBulkRequest(BaseModel):
    """Request payload for /attendance/bulk."""
    class_id: int
    date: date
    students: List[AttendanceStudentItem]


class AttendanceResponse(AttendanceBase):
    id: int
    marked_by: int
    last_updated_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AttendanceHistoryResponse(BaseModel):
    """Response for student/parent attendance history."""
    history: List[AttendanceResponse]
    attendance_percentage: float
    total_days: int
    days_present: int


# ── Subjects & Mappings ────────────────────────────────────────────────────────

class SubjectBase(BaseModel):
    name: str
    code: Optional[str] = None


class SubjectCreate(SubjectBase):
    pass


class SubjectOut(SubjectBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AcademicMappingBase(BaseModel):
    teacher_id: int
    subject_id: int
    class_id: int


class AcademicMappingCreate(AcademicMappingBase):
    pass


class AcademicMappingOut(AcademicMappingBase):
    id: int
    teacher: UserSummary
    subject: SubjectOut
    mapping_class: ClassOut

    model_config = ConfigDict(from_attributes=True)


    total_records: int
    attendance_percentage: float


# ── Homework ──────────────────────────────────────────────────────────────────

class HomeworkBase(BaseModel):
    title: str
    description: str
    due_date: date


class HomeworkCreate(HomeworkBase):
    class_id: int


class HomeworkUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None


class HomeworkResponse(HomeworkBase):
    id: int
    class_id: int
    teacher_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_deleted: bool

    model_config = ConfigDict(from_attributes=True)


class HomeworkResponseWithCompletion(HomeworkResponse):
    """Homework response with per-student completion flag."""
    completed: bool = False

    model_config = ConfigDict(from_attributes=True)


class HomeworkCompletionOut(BaseModel):
    homework_id: int
    student_id: int
    is_completed: bool
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionOut(BaseModel):
    id: int
    homework_id: int
    student: UserSummary
    is_completed: bool
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)
