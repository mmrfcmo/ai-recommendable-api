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


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.app_version}


@app.get("/sitemap.xml", response_class=Response, include_in_schema=False)
async def sitemap():
    """Serve sitemap.xml."""
    sitemap_path = os.path.join(os.path.dirname(__file__), "..", "sitemap.xml")
    sitemap_path = os.path.abspath(sitemap_path)
    if os.path.exists(sitemap_path):
        with open(sitemap_path, "r") as f:
            return Response(content=f.read(), media_type="application/xml")
    return Response(content="<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'></urlset>", media_type="application/xml")


@app.get("/wordpress-plugin/download", include_in_schema=False)
async def download_wordpress_plugin():
    """Download the AI-Recommendable Connector WordPress plugin."""
    plugin_path = os.path.join(os.path.dirname(__file__), "..", "wordpress-plugin", "ai-recommendable-connector.php")
    plugin_path = os.path.abspath(plugin_path)
    if os.path.exists(plugin_path):
        return FileResponse(
            plugin_path,
            media_type="application/octet-stream",
            filename="ai-recommendable-connector.php",
        )
    return {"error": "Plugin file not found on server", "download_url": "https://raw.githubusercontent.com/mmrfcmo/ai-recommendable-api/main/wordpress-plugin/ai-recommendable-connector.php"}


@app.get("/wordpress-plugin", response_class=HTMLResponse, include_in_schema=False)
async def wordpress_plugin_page():
    """Plugin information and download page."""
    plugin_page = os.path.join(os.path.dirname(__file__), "..", "wordpress-plugin", "wordpress-plugin.html")
    plugin_page = os.path.abspath(plugin_page)
    if os.path.exists(plugin_page):
        with open(plugin_page, "r") as f:
            return f.read()
    return "<h1>WordPress Plugin</h1><p>Download: <a href='/wordpress-plugin/download'>ai-recommendable-connector.php</a></p>"