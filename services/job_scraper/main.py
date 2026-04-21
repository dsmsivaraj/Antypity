from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from playwright.async_api import async_playwright

from shared.service_utils.base_service import _require_internal, create_base_app
from backend.container import build_container

_logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class JDExtractionRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None

class JDExtractionResponse(BaseModel):
    title: str
    company: str
    description: str
    source: str

class JobSearchRequest(BaseModel):
    keywords: List[str]
    locations: Optional[List[str]] = None

class JobSearchResult(BaseModel):
    id: str
    title: str
    company: str
    location: str
    url: str
    ats_score: Optional[float] = None


# ── Service logic ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container()
    app.state.container = container
    
    # Pre-launch playwright to warm up? Or launch on demand.
    _logger.info("Job Scraper service started with Playwright support.")
    yield
    _logger.info("Job Scraper service shutting down.")


app = create_base_app(
    title="Job Scraper Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


async def scrape_with_playwright(url: str) -> Dict[str, str]:
    """Robust scraping using a headless browser."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            title = await page.title()
            # Dynamic extraction logic (can be portal-specific)
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            description = soup.get_text()[:3000]
            await browser.close()
            return {"title": title, "description": description}
        except Exception as exc:
            await browser.close()
            raise exc


@app.post("/job/extract", response_model=JDExtractionResponse, tags=["job"])
async def extract_jd(request: Request, body: JDExtractionRequest):
    if body.text:
        return JDExtractionResponse(
            title="Extracted Job",
            company="Unknown",
            description=body.text,
            source="Manual Text"
        )
    
    if not body.url:
        raise HTTPException(status_code=400, detail="Either URL or Text must be provided.")

    # 1. Primary: Playwright (High fidelity)
    try:
        data = await scrape_with_playwright(body.url)
        return JDExtractionResponse(
            title=data["title"],
            company="Extracted (Playwright)",
            description=data["description"],
            source=body.url
        )
    except Exception as exc:
        _logger.warning("Playwright scrape failed, falling back to BeautifulSoup: %s", exc)

    # 2. Fallback: BeautifulSoup (Basic)
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(body.url)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            title = soup.title.string if soup.title else "Job from Link"
            description = soup.get_text()[:2000]
            
            return JDExtractionResponse(
                title=title,
                company="Extracted (BS4 Fallback)",
                description=description,
                source=body.url
            )
        except Exception as exc:
            _logger.error("All scraping attempts failed for URL %s: %s", body.url, exc)
            raise HTTPException(status_code=502, detail="Failed to scrape job description.")


@app.post("/job/search", response_model=List[JobSearchResult], tags=["job"])
async def search_jobs(request: Request, body: JobSearchRequest):
    # Simulated search results
    return [
        JobSearchResult(
            id="1",
            title="Senior Python Engineer",
            company="Tech Corp",
            location="Remote",
            url="https://linkedin.com/jobs/1"
        ),
        JobSearchResult(
            id="2",
            title="FastAPI Developer",
            company="Startup Inc",
            location="New York",
            url="https://indeed.com/jobs/2"
        )
    ]
