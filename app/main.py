"""AI-Recommendable API — FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base, async_session_factory
from app.api.v1.visibility import router as visibility_router
from app.api.v1.readiness import router as readiness_router
from app.api.v1.bookings import router as bookings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(visibility_router)
app.include_router(readiness_router)
app.include_router(bookings_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.app_version}
