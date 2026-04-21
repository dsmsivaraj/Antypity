"""LiveJobSearchService — fetches real job listings and generates targeted portal search links.

Strategy:
  1. Remotive API  — real remote job listings (public, no auth)
  2. Portal search links — deep-search URLs for Naukri, LinkedIn, Indeed, Wellfound
     with role + location + experience filters embedded.  These open real, filtered
     search-results pages on each portal — not generic homepages.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List
from urllib.parse import quote_plus
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

_logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}


def _slug(text: str) -> str:
    """Convert role to URL-friendly slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _exp_range(years: float) -> tuple[int, int]:
    if years >= 18:
        return (15, 25)
    if years >= 12:
        return (10, 18)
    if years >= 8:
        return (6, 12)
    if years >= 4:
        return (3, 7)
    return (0, 3)


class LiveJobSearchService:
    def __init__(self, timeout: float = 12.0) -> None:
        self.timeout = timeout

    async def search_for_resume(
        self,
        *,
        target_roles: List[str],
        location: str,
        experience_years: float = 5.0,
        limit_per_role: int = 6,
    ) -> List[Dict[str, Any]]:
        """
        Returns two categories of results:
          - type "listing": real job postings from Remotive
          - type "portal_search": deep-search links to Naukri/LinkedIn/Indeed/Wellfound
        """
        jobs: List[Dict[str, Any]] = []
        seen_urls: set = set()

        # ── 1. Remotive live listings ─────────────────────────────────────────
        remotive_jobs = await self._fetch_remotive_all()
        for job in remotive_jobs:
            url = job.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                jobs.append(job)

        # ── 2. Portal search links per role ───────────────────────────────────
        exp_min, exp_max = _exp_range(experience_years)
        for role in target_roles[:5]:
            for portal_job in self._build_portal_links(role, location, exp_min, exp_max):
                url = portal_job.get("url", "")
                if url not in seen_urls:
                    seen_urls.add(url)
                    jobs.append(portal_job)

        return jobs

    # ── Remotive ──────────────────────────────────────────────────────────────

    async def _fetch_remotive_all(self) -> List[Dict[str, Any]]:
        """Fetch all currently listed Remotive jobs."""
        url = "https://remotive.com/api/remote-jobs?limit=50"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=_HEADERS) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            jobs_raw = resp.json().get("jobs", [])
            results: List[Dict[str, Any]] = []
            for j in jobs_raw:
                desc_html = j.get("description", "")
                desc = BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)
                results.append({
                    "id": str(uuid4()),
                    "title": j.get("title", "Unknown"),
                    "company": j.get("company_name", "Unknown"),
                    "location": j.get("candidate_required_location") or "Remote / Worldwide",
                    "url": j.get("url", ""),
                    "source": "remotive",
                    "source_label": "Remotive (Remote)",
                    "result_type": "listing",
                    "jd_snippet": desc[:600],
                    "jd_full": desc[:6000],
                    "published": j.get("publication_date", ""),
                })
            return results
        except Exception as exc:
            _logger.warning("Remotive fetch error: %s", exc)
            return []

    # ── Portal search links ───────────────────────────────────────────────────

    def _build_portal_links(
        self,
        role: str,
        location: str,
        exp_min: int,
        exp_max: int,
    ) -> List[Dict[str, Any]]:
        """Build deep-search links to major job portals for a given role."""
        role_q = quote_plus(role)
        loc_q = quote_plus(location)
        role_slug = _slug(role)
        loc_slug = _slug(location)

        portals = [
            {
                "source": "naukri",
                "source_label": "Naukri.com",
                "url": (
                    f"https://www.naukri.com/{role_slug}-jobs-in-{loc_slug}"
                    f"?experience={exp_min}-{exp_max}"
                    f"&k={role_q}&l={loc_q}"
                ),
                "jd_snippet": (
                    f"Live {role} openings on Naukri — India's largest job portal. "
                    f"Filtered for {exp_min}–{exp_max} years experience in {location}. "
                    f"Click to see current listings with salary details."
                ),
            },
            {
                "source": "linkedin",
                "source_label": "LinkedIn Jobs",
                "url": (
                    f"https://www.linkedin.com/jobs/search/"
                    f"?keywords={role_q}&location={loc_q}"
                    f"&f_E=5%2C6&f_TPR=r86400"
                ),
                "jd_snippet": (
                    f"LinkedIn Jobs — Director/Executive level {role} roles in {location}. "
                    f"Filtered to senior experience band (f_E=5,6), last 24h postings shown first."
                ),
            },
            {
                "source": "indeed",
                "source_label": "Indeed India",
                "url": (
                    f"https://www.indeed.co.in/jobs"
                    f"?q={role_q}&l={loc_q}"
                    f"&explvl=senior_level&sort=date"
                ),
                "jd_snippet": (
                    f"Indeed India — Senior-level {role} jobs in {location}, sorted by date. "
                    f"Click to browse live listings."
                ),
            },
            {
                "source": "wellfound",
                "source_label": "Wellfound (Startups)",
                "url": (
                    f"https://wellfound.com/jobs"
                    f"?query={role_q}&location={loc_q}"
                ),
                "jd_snippet": (
                    f"Wellfound — {role} at funded startups in {location}. "
                    f"Equity + salary visible, direct founder contact."
                ),
            },
        ]

        results: List[Dict[str, Any]] = []
        for p in portals:
            results.append({
                "id": str(uuid4()),
                "title": f"{role} — Search Results",
                "company": p["source_label"],
                "location": location,
                "url": p["url"],
                "source": p["source"],
                "source_label": p["source_label"],
                "result_type": "portal_search",
                "jd_snippet": p["jd_snippet"],
                "jd_full": p["jd_snippet"],
                "published": "",
            })
        return results
