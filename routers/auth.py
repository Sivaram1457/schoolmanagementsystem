"""
routers/auth.py — Authentication endpoints: register, login, and me.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, hash_password, require_role, verify_password
from database import get_db
from models import User
from schemas import LoginRequest, Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── POST /auth/register  (Admin only) ─────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (admin only)",
)
def register(
    payload: UserCreate,
    current_admin: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Create a new user account. Only administrators can access this endpoint."""

    # Check for duplicate email
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    new_user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        linked_student_id=payload.linked_student_id,
        class_level=payload.class_level,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive a JWT access token",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Validate credentials and return a JWT access token."""

    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return Token(access_token=access_token)


# ── GET /auth/me ───────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserOut,
    summary="Get the currently authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return current_user
