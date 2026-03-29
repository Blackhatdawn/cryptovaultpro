"""Public contact form endpoint."""

from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import get_db
from email_service import email_service
from config import settings

router = APIRouter(prefix="/contact", tags=["contact"])


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    company: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    subject: str = Field(..., min_length=3, max_length=160)
    message: str = Field(..., min_length=10, max_length=4000)


@router.post("")
async def submit_contact_form(payload: ContactRequest, request: Request, db=Depends(get_db)):
    # basic anti-abuse guard
    if len(payload.message.strip()) < 10:
        raise HTTPException(status_code=400, detail="Message is too short")

    contact_collection = db.get_collection("contact_submissions")
    doc = {
        "name": payload.name.strip(),
        "email": payload.email.lower(),
        "company": (payload.company or "").strip() or None,
        "phone": (payload.phone or "").strip() or None,
        "subject": payload.subject.strip(),
        "message": payload.message.strip(),
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "created_at": datetime.now(timezone.utc),
        "status": "new",
    }

    await contact_collection.insert_one(doc)

    support_email = settings.public_support_email or settings.email_from or "support@cryptovaultpro.finance"
    try:
        from email_templates import contact_submission_internal

        parts = contact_submission_internal(
            name=doc["name"],
            email=doc["email"],
            company=doc["company"],
            phone=doc["phone"],
            subject=doc["subject"],
            message=doc["message"],
            ip_address=doc["ip_address"],
            user_agent=doc["user_agent"],
        )
        await email_service.send_email(
            to_email=support_email,
            subject=parts.subject,
            html_content=parts.html,
            text_content=parts.text,
        )
    except Exception:
        # Non-blocking for end-user flow
        pass

    return {"success": True, "message": "Thanks for contacting us. Our team will get back to you soon."}
