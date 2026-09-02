"""WordPress Connector - Deploys schema markup, content, and SEO fixes to WordPress sites using the REST API."""
import logging
import httpx
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.workflow_db import Project, Task, TaskStatus

logger = logging.getLogger("ai_recommendable.wordpress")


class WordPressClient:
    """Client for the WordPress REST API."""

    def __init__(self, site_url: str, username: str, password: str):
        self.base_url = site_url.rstrip("/")
        self.auth = (username, password)
        self.api_url = f"{self.base_url}/wp-json/wp/v2"

    async def test_connection(self) -> bool:
        """Test if the WordPress site is reachable and credentials work."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.api_url}/posts?per_page=1", auth=self.auth)
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"WordPress connection failed: {e}")
            return False

    async def deploy_schema_markup(self, schema_json: str) -> dict:
        """Deploy schema markup by updating the site header via a custom endpoint.
        
        For simple schema deployment, we recommend using a plugin like 
        Yoast SEO or RankMath which has its own API. Alternatively, this
        deploys via a custom plugin endpoint if installed.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/wp-json/ai-recommendable/v1/schema",
                    json={"schema": schema_json},
                    auth=self.auth,
                )
                return {
                    "success": resp.status_code == 200,
                    "status_code": resp.status_code,
                    "message": resp.json().get("message", "Schema deployed") if resp.status_code == 200 else resp.text[:200],
                }
        except httpx.RequestError as e:
            return {"success": False, "error": f"Connection failed: {str(e)[:100]}"}

    async def deploy_content(self, title: str, content_html: str, status: str = "draft") -> dict:
        """Create or update a WordPress page with generated content."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Check if a page with this title already exists
                search_resp = await client.get(
                    f"{self.api_url}/pages",
                    params={"search": title, "per_page": 1},
                    auth=self.auth,
                )
                existing = search_resp.json() if search_resp.status_code == 200 else []

                if existing:
                    # Update existing page
                    page_id = existing[0]["id"]
                    resp = await client.post(
                        f"{self.api_url}/pages/{page_id}",
                        json={
                            "title": title,
                            "content": content_html,
                            "status": status,
                        },
                        auth=self.auth,
                    )
                else:
                    # Create new page
                    resp = await client.post(
                        f"{self.api_url}/pages",
                        json={
                            "title": title,
                            "content": content_html,
                            "status": status,
                        },
                        auth=self.auth,
                    )

                data = resp.json()
                return {
                    "success": resp.status_code in (200, 201),
                    "page_id": data.get("id"),
                    "page_url": data.get("link"),
                    "status": status,
                    "message": f"Page {'updated' if existing else 'created'}: {data.get('link', '')}",
                }
        except httpx.RequestError as e:
            return {"success": False, "error": f"Connection failed: {str(e)[:100]}"}

    async def deploy_meta_description(self, description: str) -> dict:
        """Update the site meta description (requires Yoast or similar)."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Yoast SEO REST API
                resp = await client.post(
                    f"{self.base_url}/wp-json/wordpress-seo/v1/settings",
                    json={"description": description},
                    auth=self.auth,
                )
                return {
                    "success": resp.status_code == 200,
                    "message": "Meta description updated" if resp.status_code == 200 else resp.text[:200],
                }
        except httpx.RequestError as e:
            return {"success": False, "error": f"Yoast API not available: {str(e)[:100]}"}


async def deploy_project_to_wordpress(
    project_id: str,
    site_url: str,
    username: str,
    password: str,
) -> dict:
    """Deploy all completed task deliverables to a WordPress site."""
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return {"success": False, "error": "Project not found"}

        tasks_result = await db.execute(
            select(Task).where(Task.project_id == project_id)
        )
        tasks = tasks_result.scalars().all()

    wp = WordPressClient(site_url, username, password)

    # Test connection first
    connected = await wp.test_connection()
    if not connected:
        return {"success": False, "error": "Cannot connect to WordPress. Check URL and credentials."}

    results = {}
    task_map = {}
    for t in tasks:
        task_type = t.type.value if hasattr(t.type, "value") else t.type
        task_map[task_type] = t

    # Deploy schema markup
    schema_task = task_map.get("schema_markup")
    if schema_task and schema_task.status in (TaskStatus.completed, TaskStatus.approved):
        output = schema_task.output or {}
        if output.get("status") == "needs_implementation":
            # Build schema JSON
            schema_json = {
                "@context": "https://schema.org",
                "@type": "LocalBusiness",
                "name": project.business_name,
                "url": project.website,
            }
            results["schema_markup"] = await wp.deploy_schema_markup(str(schema_json))

    # Deploy content
    content_task = task_map.get("content_generation")
    if content_task and content_task.status in (TaskStatus.completed, TaskStatus.approved):
        output = content_task.output or {}
        content_html = output.get("content", "")
        if content_html:
            results["content"] = await wp.deploy_content(
                title=f"About {project.business_name}",
                content_html=content_html,
                status="draft",
            )

    return {
        "success": True,
        "project_id": project_id,
        "wordpress_url": site_url,
        "deployments": results,
    }