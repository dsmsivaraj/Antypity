from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from playwright.async_api import async_playwright

from shared.service_utils.base_service import create_base_app
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
    _logger.info("Job Scraper Service starting up.")
    try:
        container = build_container()
        app.state.container = container
        _logger.info("Job Scraper Service started successfully with Playwright support.")
    except Exception:
        _logger.critical("Job Scraper Service failed to start.", exc_info=True)
        raise
    yield
    _logger.info("Job Scraper Service shutting down.")


app = create_base_app(
    title="Job Scraper Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


async def scrape_with_playwright(url: str) -> Dict[str, str]:
    _logger.info("Playwright scrape starting: url=%s", url)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            title = await page.title()
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            description = soup.get_text()[:3000]
            _logger.info("Playwright scrape success: url=%s title=%s chars=%d", url, title, len(description))
            return {"title": title, "description": description}
        except Exception as exc:
            _logger.warning("Playwright scrape failed: url=%s error=%s", url, exc)
            raise
        finally:
            await browser.close()


@app.post("/job/extract", response_model=JDExtractionResponse, tags=["job"])
async def extract_jd(request: Request, body: JDExtractionRequest):
    _logger.info(
        "JD extract request: has_url=%s has_text=%s",
        bool(body.url), bool(body.text),
    )

    if body.text:
        _logger.debug("JD extract: using manual text input, len=%d", len(body.text))
        return JDExtractionResponse(
            title="Extracted Job",
            company="Unknown",
            description=body.text,
            source="Manual Text",
        )

    if not body.url:
        _logger.warning("JD extract rejected: neither url nor text provided.")
        raise HTTPException(status_code=400, detail="Either URL or Text must be provided.")

    # Primary: Playwright
    try:
        data = await scrape_with_playwright(body.url)
        return JDExtractionResponse(
            title=data["title"],
            company="Extracted (Playwright)",
            description=data["description"],
            source=body.url,
        )
    except Exception as exc:
        _logger.warning("Playwright scrape failed, falling back to BeautifulSoup: %s", exc)

    # Fallback: BeautifulSoup
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(body.url, timeout=15.0)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            title = soup.title.string if soup.title else "Job from Link"
            description = soup.get_text()[:2000]
            _logger.info("BeautifulSoup scrape success: url=%s title=%s", body.url, title)
            return JDExtractionResponse(
                title=title,
                company="Extracted (BS4 Fallback)",
                description=description,
                source=body.url,
            )
        except Exception:
            _logger.error("All scraping methods failed: url=%s", body.url, exc_info=True)
            raise HTTPException(status_code=502, detail="Failed to scrape job description.")


@app.post("/job/search", response_model=List[JobSearchResult], tags=["job"])
async def search_jobs(request: Request, body: JobSearchRequest):
    _logger.info("Job search: keywords=%s locations=%s", body.keywords, body.locations)
    results = [
        JobSearchResult(
            id="1",
            title="Senior Python Engineer",
            company="Tech Corp",
            location="Remote",
            url="https://linkedin.com/jobs/1",
        ),
        JobSearchResult(
            id="2",
            title="FastAPI Developer",
            company="Startup Inc",
            location="New York",
            url="https://indeed.com/jobs/2",
        ),
    ]
    _logger.info("Job search returned %d results.", len(results))
    return results
