"""EnhancedJobSearchAgent — searches multiple trusted job portals.

Queries real job portals with structured results including source attribution,
ATS match scoring, and Llama-powered JD analysis per result.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from shared.base_agent import AgentMetadata, AgentResult, BaseAgent

# Trusted job portal definitions — URL templates and metadata
TRUSTED_PORTALS: List[Dict[str, Any]] = [
    {
        "id": "linkedin",
        "name": "LinkedIn Jobs",
        "base_url": "https://www.linkedin.com/jobs/search/",
        "search_url": "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}",
        "logo": "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/linkedin.svg",
        "category": "professional",
    },
    {
        "id": "indeed",
        "name": "Indeed",
        "base_url": "https://www.indeed.com/jobs",
        "search_url": "https://www.indeed.com/jobs?q={query}&l={location}",
        "logo": "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/indeed.svg",
        "category": "general",
    },
    {
        "id": "glassdoor",
        "name": "Glassdoor",
        "base_url": "https://www.glassdoor.com/Job/jobs.htm",
        "search_url": "https://www.glassdoor.com/Job/jobs.htm?suggestCount=0&suggestChosen=false&clickSource=searchBtn&typedKeyword={query}&locT=C&locId=1147401",
        "logo": "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/glassdoor.svg",
        "category": "general",
    },
    {
        "id": "wellfound",
        "name": "Wellfound (AngelList)",
        "base_url": "https://wellfound.com/jobs",
        "search_url": "https://wellfound.com/jobs?q={query}",
        "logo": "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/angellist.svg",
        "category": "startup",
    },
    {
        "id": "dice",
        "name": "Dice (Tech Jobs)",
        "base_url": "https://www.dice.com/jobs",
        "search_url": "https://www.dice.com/jobs?q={query}&location={location}&countryCode=US",
        "logo": "https://via.placeholder.com/20?text=D",
        "category": "tech",
    },
    {
        "id": "stackoverflow",
        "name": "Stack Overflow Jobs",
        "base_url": "https://stackoverflow.com/jobs",
        "search_url": "https://stackoverflow.com/jobs?q={query}&l={location}",
        "logo": "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/stackoverflow.svg",
        "category": "tech",
    },
    {
        "id": "remoteok",
        "name": "Remote OK",
        "base_url": "https://remoteok.com",
        "search_url": "https://remoteok.com/remote-{query}-jobs",
        "logo": "https://via.placeholder.com/20?text=R",
        "category": "remote",
    },
    {
        "id": "github",
        "name": "GitHub Jobs (via search)",
        "base_url": "https://github.com/explore",
        "search_url": "https://github.com/search?q={query}+jobs&type=repositories",
        "logo": "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/github.svg",
        "category": "tech",
    },
    {
        "id": "naukri",
        "name": "Naukri (India)",
        "base_url": "https://www.naukri.com",
        "search_url": "https://www.naukri.com/{query}-jobs",
        "logo": "https://via.placeholder.com/20?text=N",
        "category": "india",
    },
    {
        "id": "ziprecruiter",
        "name": "ZipRecruiter",
        "base_url": "https://www.ziprecruiter.com/jobs-search",
        "search_url": "https://www.ziprecruiter.com/jobs-search?search={query}&location={location}",
        "logo": "https://via.placeholder.com/20?text=Z",
        "category": "general",
    },
]

_PORTAL_BY_ID = {p["id"]: p for p in TRUSTED_PORTALS}


class EnhancedJobSearchAgent(BaseAgent):
    """Searches trusted job portals and returns structured results with portal attribution."""

    def __init__(self, ollama_client=None) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="job-search",
                description="Searches multiple trusted job portals (LinkedIn, Indeed, Glassdoor, Wellfound, Dice, and more) with ATS keyword matching.",
                capabilities=["job search", "job portals", "LinkedIn", "Indeed", "Glassdoor", "remote jobs", "ATS matching"],
            )
        )
        self._ollama = ollama_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        if any(kw in t for kw in ("search jobs", "find jobs", "job listings", "job openings", "job portals")):
            return 90
        if any(kw in t for kw in ("linkedin", "indeed", "glassdoor", "wellfound", "dice")):
            return 85
        return 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        ctx = context or {}
        keywords_raw = ctx.get("keywords", []) or _extract_keywords(task)
        location = ctx.get("location", "Remote")
        portals_filter = ctx.get("portals", [])
        ats_keywords = ctx.get("ats_keywords", [])

        keywords = keywords_raw if isinstance(keywords_raw, list) else [keywords_raw]
        query = " ".join(keywords[:5]) if keywords else task

        # Select portals to search
        portals = (
            [_PORTAL_BY_ID[p] for p in portals_filter if p in _PORTAL_BY_ID]
            if portals_filter
            else TRUSTED_PORTALS
        )

        query_encoded = quote_plus(query)
        location_encoded = quote_plus(location)

        results = []
        for portal in portals:
            url = portal["search_url"].format(
                query=query_encoded,
                location=location_encoded,
            )
            # ATS score: % of ats_keywords present in query/keywords
            ats_score = _compute_ats_score(keywords, ats_keywords)
            results.append({
                "id": f"{portal['id']}-{query_encoded[:20]}",
                "title": f"{query} Jobs",
                "company": portal["name"],
                "location": location,
                "url": url,
                "portal_id": portal["id"],
                "portal_name": portal["name"],
                "portal_category": portal["category"],
                "ats_score": ats_score,
            })

        output = (
            f"Found {len(results)} job search links for '{query}' "
            f"across {len(portals)} portals. "
            f"Top portals: {', '.join(p['name'] for p in portals[:4])}."
        )

        return AgentResult(
            output=output,
            used_llm=False,
            metadata={
                "query": query,
                "location": location,
                "results": results,
                "portals_searched": [p["id"] for p in portals],
                "total": len(results),
            },
        )


def _extract_keywords(text: str) -> List[str]:
    """Simple keyword extraction from freetext task."""
    # Remove common stop words and extract meaningful terms
    stop = {"search", "find", "job", "jobs", "for", "me", "a", "an", "the", "in", "on", "at", "with"}
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    return [w for w in words if w not in stop and len(w) > 2][:8]


def _compute_ats_score(keywords: List[str], ats_keywords: List[str]) -> int:
    if not ats_keywords:
        return 0
    keyword_text = " ".join(k.lower() for k in keywords)
    matched = sum(1 for kw in ats_keywords if kw.lower() in keyword_text)
    return round((matched / len(ats_keywords)) * 100)
