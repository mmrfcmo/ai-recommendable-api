"""API v1 routes."""
from fastapi import APIRouter
router = APIRouter()

from .discoverability import router as discoverability_router
router.include_router(discoverability_router)

from .bookings import router as bookings_router
router.include_router(bookings_router)

from .growth_gap_v1 import router as growth_gap_router
router.include_router(growth_gap_router)
