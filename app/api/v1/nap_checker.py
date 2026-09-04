"""NAP Consistency Checker API routes.

Endpoint:
  POST /api/v1/nap-check

Accepts a business name, address, postcode and phone, scans major
directories, and returns a NAP inconsistency report.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
from app.services.nap_checker import run_nap_check

router = APIRouter(prefix="/api/v1/nap-check", tags=["NAP Consistency"])


class NAPCheckRequest(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = Field(default="", max_length=512)
    postcode: Optional[str] = Field(default="", max_length=20)
    phone: Optional[str] = Field(default="", max_length=40)
    country: Optional[str] = Field(default="UK", max_length=100)


class NAPCheckResponse(BaseModel):
    business_name: str
    reference: dict
    directories: list
    summary: dict
    generated_at: str

    class Config:
        arbitrary_types_allowed = True


@router.post("", response_model=NAPCheckResponse)
async def check_nap(req: NAPCheckRequest):
    """Scan directories and return NAP inconsistency report."""
    return await run_nap_check(
        business_name=req.business_name,
        address=req.address or "",
        postcode=req.postcode or "",
        phone=req.phone or "",
        country=req.country or "UK",
    )