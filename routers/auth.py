"""routers/auth.py — Authentication endpoints: register, login, and related flows."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import (
    ENFORCE_EMAIL_VERIFICATION,
    PASSWORD_RESET_TOKEN_MINUTES,
    create_access_token,
    create_email_verification_token,
    create_refresh_token,
    create_timed_token,
    get_current_user,
    hash_password,
    hash_token,
    invalidate_user_refresh_tokens,
    require_role,
    validate_password_strength,
    verify_password,
)
from database import get_db
from models import EmailVerificationToken, PasswordResetToken, RefreshToken, User
from rate_limit import limiter
from schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserOut,
    VerifyEmailRequest,
)

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
        is_email_verified=False,
    )
    db.add(new_user)
    db.flush()

    verification_token, expires_at = create_email_verification_token()
    verification_hash = hash_token(verification_token)
    db.add(
        EmailVerificationToken(
            user_id=new_user.id,
            token_hash=verification_hash,
            expires_at=expires_at,
        )
    )
    db.commit()

    print(f"[EMAIL] Verify account: http://localhost:8000/auth/verify-email?token={verification_token}")
    return new_user


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive a JWT access token",
)
@limiter.limit("5/minute")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Validate credentials and return a JWT access token."""

    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if ENFORCE_EMAIL_VERIFICATION and not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in",
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    refresh_token, expires_at = create_refresh_token()
    token_hash = hash_token(refresh_token)

    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token)


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=Token,
    summary="Rotate tokens using a valid refresh token",
)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    now = datetime.now(timezone.utc)
    new_access_token: str | None = None
    new_refresh_token: str | None = None

    with db.begin():
        stored = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == token_hash,
            )
            .with_for_update()
            .first()
        )

        if not stored or stored.is_revoked or stored.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        stored.is_revoked = True

        user = db.query(User).filter(User.id == stored.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        new_access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role.value}
        )
        new_refresh_token, expires_at = create_refresh_token()
        new_hash = hash_token(new_refresh_token)

        db.add(
            RefreshToken(
                user_id=user.id,
                token_hash=new_hash,
                expires_at=expires_at,
            )
        )

    return Token(access_token=new_access_token, refresh_token=new_refresh_token)


# ── POST /auth/logout ─────────────────────────────────────────────────────────

@router.post(
    "/logout",
    summary="Revoke an existing refresh token",
)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    now = datetime.now(timezone.utc)
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not stored or stored.is_revoked or stored.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    stored.is_revoked = True
    db.commit()
    return {"detail": "Logged out successfully"}


# ── POST /auth/forgot-password ───────────────────────────────────────────────

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset link",
)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        token, expires_at = create_timed_token(PASSWORD_RESET_TOKEN_MINUTES)
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=expires_at,
            )
        )
        db.commit()
        print(f"[EMAIL] Password reset link: http://localhost:8000/auth/reset-password?token={token}")

    return MessageResponse(detail="If the email exists, a reset link has been sent.")


# ── POST /auth/reset-password ─────────────────────────────────────────────────

@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a reset token",
)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.token)
    now = datetime.now(timezone.utc)
    record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > now,
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    validate_password_strength(payload.new_password)

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

    user.password_hash = hash_password(payload.new_password)
    user.is_email_verified = True
    record.is_used = True
    invalidate_user_refresh_tokens(user.id, db)
    db.commit()

    return MessageResponse(detail="Password reset successful")


# ── POST /auth/verify-email ──────────────────────────────────────────────────

@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify an email address using a token",
)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.token)
    now = datetime.now(timezone.utc)
    record = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token_hash == token_hash,
        EmailVerificationToken.is_used == False,
        EmailVerificationToken.expires_at > now,
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

    user.is_email_verified = True
    record.is_used = True
    db.commit()

    return MessageResponse(detail="Email verified successfully")


# ── GET /auth/me ───────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserOut,
    summary="Get the currently authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return current_user
