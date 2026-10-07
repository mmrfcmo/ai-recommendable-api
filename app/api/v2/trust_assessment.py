"""RbAI Trust Signal assessment API. Shared engine for the customer-facing Trust Signals Scanner and Trust Signals Deep Scanner."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.services.trust_signal_engine import assess

router=APIRouter(prefix="/api/v2/trust-assessment",tags=["RbAI Trust Signal Assessment"])

class AssessmentRequest(BaseModel):
    website:str=Field(...,min_length=3,max_length=512)
    business_name:Optional[str]=Field(default=None,max_length=255)
    mode:str=Field(default="basic",pattern="^(basic|deep)$")

@router.post("/scan")
async def run_scan(req:AssessmentRequest):
    result=await assess(req.website,req.business_name,req.mode)
    if not result.get("success"): raise HTTPException(status_code=422,detail=result.get("error","Assessment failed"))
    return result
