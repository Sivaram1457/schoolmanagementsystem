"""
routers/certificates.py — PDF Certificate Generator.

Endpoints
---------
POST  /certificates/generate/{event_id}   admin only
GET   /certificates/event/{event_id}      admin | teacher
GET   /certificates/download/{event_id}   admin | teacher  → ZIP download
"""

import io
import os
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.auth import require_role
from backend.database import get_db
from backend.models import (
    Certificate,
    Event,
    EventRegistration,
    User,
)
from backend.schemas import CertificateGenerateResponse, CertificateOut

# ── Constants ──────────────────────────────────────────────────────────────────

CERT_DIR = Path("uploads") / "certificates"
CERT_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/certificates", tags=["Certificates"])


# ── Helper: PDF generation ─────────────────────────────────────────────────────

def _generate_pdf(student_name: str, event_title: str, event_date: str) -> bytes:
    """
    Render a simple certificate PDF using fpdf2.

    Falls back to a plain-text placeholder if fpdf2 is not installed,
    so the endpoint remains functional without the optional dependency.
    """
    try:
        from fpdf import FPDF  # type: ignore

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.add_page()

        # ── Border ───────────────────────────────────────────────────────
        pdf.set_line_width(1.5)
        pdf.set_draw_color(30, 80, 162)
        pdf.rect(10, 10, 277, 190)
        pdf.set_line_width(0.5)
        pdf.rect(13, 13, 271, 184)

        # ── Header ───────────────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 36)
        pdf.set_text_color(30, 80, 162)
        pdf.set_y(30)
        pdf.cell(0, 15, "Certificate of Participation", align="C", ln=True)

        # ── Divider ──────────────────────────────────────────────────────
        pdf.set_draw_color(200, 160, 0)
        pdf.set_line_width(1)
        pdf.line(40, pdf.get_y() + 2, 257, pdf.get_y() + 2)
        pdf.ln(8)

        # ── Body ─────────────────────────────────────────────────────────
        pdf.set_font("Helvetica", "", 16)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(0, 10, "This is to certify that", align="C", ln=True)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 28)
        pdf.set_text_color(30, 80, 162)
        pdf.cell(0, 14, student_name, align="C", ln=True)
        pdf.ln(4)

        pdf.set_font("Helvetica", "", 16)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(0, 10, "has successfully participated in", align="C", ln=True)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(180, 60, 0)
        pdf.cell(0, 12, event_title, align="C", ln=True)
        pdf.ln(4)

        pdf.set_font("Helvetica", "I", 14)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 10, f"held on {event_date}", align="C", ln=True)

        # ── Footer ───────────────────────────────────────────────────────
        pdf.set_y(175)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, "School Management System", align="C", ln=True)

        return pdf.output()  # returns bytes in fpdf2 ≥ 2.5

    except ImportError:
        # Graceful fallback: plain ASCII "certificate"
        text = (
            f"CERTIFICATE OF PARTICIPATION\n"
            f"==============================\n\n"
            f"This certifies that {student_name}\n"
            f"participated in {event_title}\n"
            f"held on {event_date}.\n"
        )
        return text.encode("utf-8")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/generate/{event_id}",
    response_model=CertificateGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate PDF certificates for all event participants (admin)",
)
def generate_certificates(
    event_id: int,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Generate one PDF certificate per registered participant of *event_id*.

    - Skips students who already have a certificate for this event.
    - Saves files under ``uploads/certificates/``.
    - Returns counts of generated / skipped plus full certificate list.
    """
    # 1. Validate event
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.is_deleted == False,  # noqa: E712
    ).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id={event_id} not found",
        )

    event_date_str = event.event_date.strftime("%B %d, %Y") if event.event_date else "TBD"

    # 2. Fetch participants
    registrations: list[EventRegistration] = (
        db.query(EventRegistration)
        .filter(EventRegistration.event_id == event_id)
        .all()
    )
    if not registrations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No participants registered for this event.",
        )

    # 3. Existing certificates (to skip duplicates)
    existing = {
        c.student_id
        for c in db.query(Certificate).filter(Certificate.event_id == event_id).all()
    }

    generated_certs: list[Certificate] = []
    skipped = 0

    for reg in registrations:
        if reg.student_id in existing:
            skipped += 1
            continue

        # Fetch student name
        student = db.query(User).filter(User.id == reg.student_id).first()
        if not student:
            skipped += 1
            continue

        # Generate PDF
        pdf_bytes = _generate_pdf(student.full_name, event.title, event_date_str)

        # Save to disk
        filename = f"cert_event{event_id}_student{student.id}.pdf"
        file_path = CERT_DIR / filename
        file_path.write_bytes(pdf_bytes)

        file_url = f"/uploads/certificates/{filename}"

        # Persist record
        cert = Certificate(
            student_id=student.id,
            event_id=event_id,
            file_url=file_url,
        )
        db.add(cert)
        db.flush()  # get cert.id before commit
        generated_certs.append(cert)

    db.commit()
    for c in generated_certs:
        db.refresh(c)

    return CertificateGenerateResponse(
        event_id=event_id,
        generated=len(generated_certs),
        skipped=skipped,
        certificates=[CertificateOut.model_validate(c) for c in generated_certs],
    )


@router.get(
    "/event/{event_id}",
    response_model=list[CertificateOut],
    summary="List all certificates for an event (admin | teacher)",
)
def list_event_certificates(
    event_id: int,
    current_user: User = Depends(require_role(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """Return all Certificate records for *event_id*."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id={event_id} not found",
        )
    certs = (
        db.query(Certificate)
        .filter(Certificate.event_id == event_id)
        .order_by(Certificate.generated_at)
        .all()
    )
    return certs


@router.get(
    "/download/{event_id}",
    summary="Download a ZIP archive of all certificates for an event (admin | teacher)",
)
def download_certificates_zip(
    event_id: int,
    current_user: User = Depends(require_role(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    Stream a ZIP archive containing every PDF certificate for *event_id*.

    - Returns 404 if the event doesn't exist.
    - Returns 422 if there are no certificates yet (generate them first).
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id={event_id} not found",
        )

    certs = db.query(Certificate).filter(Certificate.event_id == event_id).all()
    if not certs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No certificates found for this event. Run /certificates/generate first.",
        )

    # Build ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for cert in certs:
            # Resolve local disk path from the stored URL
            # file_url is like "/uploads/certificates/cert_event1_student3.pdf"
            local_path = Path(cert.file_url.lstrip("/"))
            if local_path.exists():
                zf.write(local_path, arcname=local_path.name)
            else:
                # File missing on disk — include a placeholder
                zf.writestr(
                    local_path.name,
                    f"Certificate file missing for student_id={cert.student_id}",
                )

    zip_buffer.seek(0)
    safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in event.title)
    filename = f"certificates_event_{event_id}_{safe_title}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
