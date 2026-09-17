"""AI-Recommendable API — FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1.discoverability import router as discoverability_router
from app.api.v1.readiness import router as readiness_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.fulfilment_routes import router as fulfilment_router
from app.api.v1.nap_checker import router as nap_checker_router
from app.api.v1.growth_gap_v1 import router as growth_gap_router
import app.models  # noqa — ensure models are loaded
import app.models.workflow_db  # noqa
import os
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

app.include_router(discoverability_router)
app.include_router(readiness_router)
app.include_router(bookings_router)
app.include_router(fulfilment_router)
app.include_router(nap_checker_router)
app.include_router(growth_gap_router)

@app.get("/")
async def root():
    return {"app": settings.app_name, "version": settings.app_version}

@app.get("/channels", include_in_schema=False)
async def get_channels():
    import json
    p = os.path.join(os.path.dirname(__file__), "channels.json")
    if os.path.exists(p):
        with open(p) as f:
            channels = json.load(f)
        html = "<html><head><meta charset='utf-8'><title>Channels</title></head><body>"
        html += "<h1>Channels</h1><ul>"
        for c in channels:
            html += f"<li>{c.get('name', 'Unnamed')} — {c.get('whatsapp', 'N/A')}</li>"
        html += "</ul></body></html>"
        return HTMLResponse(html)
    return HTMLResponse("<h1>No channels found</h1>")

@app.get("/app-report", include_in_schema=False)
async def serve_report():
    p = os.path.join(os.path.dirname(__file__), "app-report.html")
    if os.path.exists(p):
        with open(p) as f:
            return f.read()
    return "<h1>app-report.html not found</h1>"

@app.get("/scanner-static", include_in_schema=False)
async def serve_scanner_b():
    p = os.path.join(os.path.dirname(__file__), "trust-scanner-b.html")
    if os.path.exists(p):
        with open(p) as f:
            return f.read()
    return "<h1>Scanner B not found</h1>"

@app.get("/trust-scanner-a", response_class=HTMLResponse, include_in_schema=False)
async def serve_scanner():
    p = os.path.join(os.path.dirname(__file__), "trust-scanner-a.html")
    if os.path.exists(p):
        with open(p) as f:
            return f.read()
    return "<h1>Scanner not found</h1>"
