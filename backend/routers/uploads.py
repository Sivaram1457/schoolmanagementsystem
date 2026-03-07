"""
routers/uploads.py — Secure file upload system.

Rules:
  - Max file size : 5 MB
  - Allowed types : jpg, jpeg, png, pdf
  - Storage root  : uploads/
  - Student photo : POST /students/{id}/photo  (admin | teacher)
"""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.auth import require_role
from backend.database import get_db
from backend.models import User, UserRole
from backend.schemas import FileUploadResponse

# ── Constants ──────────────────────────────────────────────────────────────────

UPLOAD_DIR = Path("uploads")
# Ensure canonical subdirectories exist on startup
for _sub in ("students", "certificates", "events", "announcements", "general"):
    (UPLOAD_DIR / _sub).mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB in bytes

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/pdf",
}

router = APIRouter(tags=["Uploads"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _validate_and_save(upload: UploadFile, sub_dir: str = "") -> str:
    """
    Validate file size / extension, persist to disk, return the relative URL.

    Raises HTTPException on any validation failure.
    """
    # 1. Extension check
    original_filename = upload.filename or "unknown"
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. MIME type check (content_type supplied by the client — secondary guard)
    if upload.content_type and upload.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MIME type '{upload.content_type}' is not allowed.",
        )

    # 3. Read content & size check
    content = upload.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum allowed size is 5 MB.",
        )

    # 4. Persist with a collision-safe filename
    target_dir = UPLOAD_DIR / sub_dir if sub_dir else UPLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = target_dir / unique_name
    file_path.write_bytes(content)

    relative_url = f"/uploads/{sub_dir}/{unique_name}" if sub_dir else f"/uploads/general/{unique_name}"
    return relative_url


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file (admin | teacher)",
)
def upload_file(
    file: UploadFile = File(..., description="File to upload (jpg/jpeg/png/pdf, max 5 MB)"),
    current_user: User = Depends(require_role(["admin", "teacher"])),
):
    """
    Generic file upload endpoint.

    - Accepted formats: jpg, jpeg, png, pdf
    - Maximum size: 5 MB
    - Files stored under uploads/general/
    - Returns the relative URL of the saved file.
    """
    file_url = _validate_and_save(file, sub_dir="general")
    return FileUploadResponse(file_url=file_url)


@router.post(
    "/students/{student_id}/photo",
    response_model=FileUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Set student photo (admin | teacher)",
)
def upload_student_photo(
    student_id: int,
    file: UploadFile = File(..., description="Student photo (jpg/jpeg/png, max 5 MB)"),
    current_user: User = Depends(require_role(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    Upload and attach a photo to a student account.

    - Only jpg/jpeg/png are meaningful (pdf rejected via extension rule).
    - Saved under uploads/photos/.
    - Updates `users.photo_url`.
    - Intended for use by the face recognition system.
    """
    # 1. Resolve student
    student = db.query(User).filter(
        User.id == student_id,
        User.role == UserRole.student,
        User.is_active == True,
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active student with id={student_id} not found",
        )

    # 2. Validate & save (stored under uploads/students/)
    file_url = _validate_and_save(file, sub_dir="students")

    # 3. Persist URL on user record
    student.photo_url = file_url
    db.commit()

    return FileUploadResponse(file_url=file_url)
