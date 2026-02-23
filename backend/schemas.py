"""
schemas.py — Pydantic models for request/response validation.
"""

from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, EmailStr, ConfigDict, Field
from pydantic.generics import GenericModel

from backend.models import UserRole


# ── Linkages ───────────────────────────────────────────────────────────────────

class ClassBase(BaseModel):
    """Base schema for Class information."""
    name: str = Field(..., description="The name of the class, e.g., '10A'")
    class_level: str = Field(..., description="The academic level, e.g., '10'")
    section: str = Field(..., description="The section identifier, e.g., 'A'")


class ClassCreate(ClassBase):
    """Schema for creating a new Class."""
    pass


class ClassOut(ClassBase):
    """Response schema for Class information."""
    id: int = Field(..., description="Unique identifier for the class")
    created_at: datetime = Field(..., description="Timestamp when the class was created")
    
    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class PaginatedResponse(GenericModel, Generic[T]):
    """Standard paginated response wrapper."""
    items: list[T] = Field(..., description="List of items for the current page")
    total: int = Field(..., description="Total number of items available")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of items per page")


# ── Auth Requests ──────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    """Base schema for User profile information."""
    full_name: str = Field(..., description="Full name of the user")
    email: EmailStr = Field(..., description="Unique email address for the user")


class UserCreate(UserBase):
    """Generic payload - used by admin or initial registration."""
    password: str = Field(..., description="Cleartext password for the user")
    role: UserRole = Field(UserRole.student, description="Assigned role for the user")
    linked_student_id: Optional[int] = Field(None, description="Optional ID of a linked student (for parents)")
    class_id: Optional[int] = Field(None, description="Optional ID of the assigned class")


class StudentUpdate(BaseModel):
    """Schema for updating Student specific information."""
    full_name: Optional[str] = Field(None, description="Updated full name")
    email: Optional[EmailStr] = Field(None, description="Updated email address")
    class_id: Optional[int] = Field(None, description="Updated class assignment")


class TeacherUpdate(BaseModel):
    """Schema for updating Teacher specific information."""
    full_name: Optional[str] = Field(None, description="Updated full name")
    email: Optional[EmailStr] = Field(None, description="Updated email address")


class ParentUpdate(BaseModel):
    """Schema for updating Parent specific information."""
    full_name: Optional[str] = Field(None, description="Updated full name")
    email: Optional[EmailStr] = Field(None, description="Updated email address")
    student_ids: Optional[List[int]] = Field(None, description="Updated list of linked student IDs")


class StudentCreate(UserBase):
    """Specific payload for creating a Student."""
    password: str = Field(..., description="Cleartext password")
    class_id: int = Field(..., description="Required class ID for the student")
    role: UserRole = Field(UserRole.student, description="Role is fixed to student")


class TeacherCreate(UserBase):
    """Specific payload for creating a Teacher."""
    password: str = Field(..., description="Cleartext password")
    role: UserRole = Field(UserRole.teacher, description="Role is fixed to teacher")


class ParentCreate(UserBase):
    """Specific payload for creating a Parent."""
    password: str = Field(..., description="Cleartext password")
    student_ids: List[int] = Field(..., description="Required list of student IDs for the parent")
    role: UserRole = Field(UserRole.parent, description="Role is fixed to parent")


class LoginRequest(BaseModel):
    """Payload for the login endpoint."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's cleartext password")


# ── Auth Responses ─────────────────────────────────────────────────────────────

class UserSummary(BaseModel):
    """Minimal user info to prevent recursion."""
    id: int = Field(..., description="Unique identifier")
    full_name: str = Field(..., description="User's full name")
    class_id: Optional[int] = Field(None, description="Class ID if applicable")
    role: UserRole = Field(..., description="User's role")
    
    model_config = ConfigDict(from_attributes=True)


class UserOut(UserBase):
    """Public representation of a user (no password hash)."""
    id: int = Field(..., description="Unique identifier")
    role: UserRole = Field(..., description="Assigned role")
    is_active: bool = Field(..., description="Account activation status")
    
    # Relationships
    class_id: Optional[int] = Field(None, description="Assigned class ID")
    student_class: Optional[ClassOut] = Field(None, description="Nested class details")
    
    # M2M Relationships
    children: List[UserSummary] = Field([], description="List of children for parent users")
    parents: List[UserSummary] = Field([], description="List of parents for student users")
    
    # Legacy field
    linked_student_id: Optional[int] = Field(None, description="Legacy link field")
    
    created_at: datetime = Field(..., description="Time of registration")

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """JWT token response."""
    access_token: str = Field(..., description="Access token for authentication")
    refresh_token: str = Field(..., description="Token used to obtain a new access token")
    token_type: str = Field("bearer", description="Token category")


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

from backend.models import AttendanceStatus
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


class ClassAttendanceStats(BaseModel):
    """Aggregated attendance analytics for a class."""
    class_id: int
    class_name: str
    total_students: int
    total_records: int
    attendance_percentage: float

    model_config = ConfigDict(from_attributes=True)


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
