"""Booking API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models import Booking
from app.schemas import BookingRequest
from app.services.notifications import send_booking_notification
from pydantic import BaseModel


class BookingResponse(BaseModel):
    success: bool
    message: str
    calendly_url: str = ""


router = APIRouter(prefix="/api/v1/bookings", tags=["Bookings"])


@router.post("/consultation", response_model=BookingResponse, status_code=201)
async def book_consultation(
    req: BookingRequest,
    db: AsyncSession = Depends(get_db),
):
    """Book a free 20-minute consultation."""
    booking = Booking(
        name=req.name,
        email=req.email,
        phone=req.phone or "",
        report_id=req.report_id or "",
        message=req.message or "",
    )
    db.add(booking)
    await db.flush()

    send_booking_notification(req.name, req.email, req.phone, req.message)

    return BookingResponse(
        success=True,
        message="Your consultation request has been received. We'll be in touch shortly.",
        calendly_url="https://calendly.com/YOUR_CALENDLY_LINK",  # Replace with your Calendly link
    )
