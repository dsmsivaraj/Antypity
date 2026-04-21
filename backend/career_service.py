from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from .config import Settings
from .database import PostgreSQLDatabaseClient
from .model_router import ModelRouter

TRUSTED_JOB_PORTALS: Dict[str, Dict[str, Any]] = {
    "linkedin": {
        "label": "LinkedIn Jobs",
        "hosts": ["linkedin.com", "www.linkedin.com"],
        "search_url": "https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}",
    },
    "indeed": {
        "label": "Indeed",
        "hosts": ["indeed.com", "www.indeed.com"],
        "search_url": "https://www.indeed.com/jobs?q={keywords}&l={location}",
    },
    "glassdoor": {
        "label": "Glassdoor",
        "hosts": ["glassdoor.com", "www.glassdoor.com"],
        "search_url": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={keywords}&locT=C&locId=&locKeyword={location}",
    },
    "wellfound": {
        "label": "Wellfound",
        "hosts": ["wellfound.com", "angel.co"],
        "search_url": "https://wellfound.com/jobs?query={keywords}&location={location}",
    },
    "naukri": {
        "label": "Naukri",
        "hosts": ["naukri.com", "www.naukri.com"],
        "search_url": "https://www.naukri.com/{keywords}-jobs-in-{location}",
    },
    "dice": {
        "label": "Dice",
        "hosts": ["dice.com", "www.dice.com"],
        "search_url": "https://www.dice.com/jobs?q={keywords}&location={location}",
    },
    "ziprecruiter": {
        "label": "ZipRecruiter",
        "hosts": ["ziprecruiter.com", "www.ziprecruiter.com"],
        "search_url": "https://www.ziprecruiter.com/jobs-search?search={keywords}&location={location}",
    },
}

DEFAULT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "modern-executive",
        "name": "Modern Executive",
        "target_role": "Senior engineering and product leadership",
        "style": "executive-minimal",
        "figma_prompt": "Create a clean one-page resume with a bold name band, asymmetric metrics rail, and restrained serif/sans pairing.",
        "sections": ["Header", "Executive Summary", "Experience", "Leadership Impact", "Core Skills", "Education"],
        "design_tokens": {
            "primary": "#0d3b66",
            "accent": "#f4a261",
            "surface": "#f8fafc",
            "font_heading": "Manrope",
            "font_body": "IBM Plex Sans",
        },
        "preview_markdown": "A one-page executive resume with a strong summary and quantified impact blocks.",
        "source": "system",
    },
    {
        "id": "creative-product",
        "name": "Creative Product Builder",
        "target_role": "Product, design, and startup operators",
        "style": "editorial-modular",
        "figma_prompt": "Design a modular resume with editorial hierarchy, stacked project cards, and subtle grid accents.",
        "sections": ["Header", "Profile", "Selected Work", "Experience", "Tools", "Education"],
        "design_tokens": {
            "primary": "#1d3557",
            "accent": "#e63946",
            "surface": "#fffaf3",
            "font_heading": "Space Grotesk",
            "font_body": "DM Sans",
        },
        "preview_markdown": "A portfolio-forward resume with project callouts and modular content blocks.",
        "source": "system",
    },
]


@dataclass(frozen=True)
class ParsedResume:
    filename: str
    text: str
    metadata: Dict[str, Any]


class CareerService:
    def __init__(
        self,
        *,
        settings: Settings,
        model_router: ModelRouter,
        database_client: PostgreSQLDatabaseClient,
    ) -> None:
        self.settings = settings
        self.model_router = model_router
        self.database_client = database_client

    def trusted_sources(self) -> List[Dict[str, Any]]:
        allowed = set(self.settings.trusted_job_sources)
        return [
            {"id": key, **value}
            for key, value in TRUSTED_JOB_PORTALS.items()
            if key in allowed
        ]

    def parse_resume(self, filename: str, content: bytes) -> ParsedResume:
        lower_name = filename.lower()
        if lower_name.endswith(".pdf"):
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            raw_pages = [(page.extract_text() or "").strip() for page in reader.pages]
            text = self._fix_pdf_text("\n".join(raw_pages)).strip()
            metadata = {"pages": len(reader.pages), "type": "pdf"}
        elif lower_name.endswith(".docx"):
            import docx

            doc = docx.Document(BytesIO(content))
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs).strip()
            metadata = {"paragraphs": len(doc.paragraphs), "type": "docx"}
        elif lower_name.endswith(".txt"):
            text = content.decode("utf-8", errors="ignore").strip()
            metadata = {"type": "txt"}
        else:
            raise ValueError("Unsupported file format. Supported formats: pdf, docx, txt.")

        return ParsedResume(filename=filename, text=text, metadata=metadata)

    def analyze_resume(
        self,
        *,
        resume_text: str,
        jd_text: str,
        model_profile: Optional[str],
        source_filename: Optional[str],
        created_by: Optional[str],
    ) -> Dict[str, Any]:
        resume_keywords = self._extract_keywords(resume_text)
        jd_keywords = self._extract_keywords(jd_text)
        matched = sorted(resume_keywords & jd_keywords)
        missing = sorted(jd_keywords - resume_keywords)
        strengths = self._extract_bullets(resume_text, limit=4)
        summary_seed = (
            f"Resume keywords: {', '.join(sorted(resume_keywords)[:20]) or 'none'}\n"
            f"JD keywords: {', '.join(sorted(jd_keywords)[:20]) or 'none'}\n"
            f"Top strengths: {', '.join(strengths) or 'none'}"
        )
        profile, completion = self.model_router.complete(
            model_profile=model_profile or self._preferred_profile("resume"),
            prompt=summary_seed,
            system_prompt=(
                "You are a resume reviewer. Summarize the candidate fit in 4-6 concise sentences, "
                "highlight missing experience, and keep the answer grounded in the provided signals."
            ),
        )
        suggestions = self._build_resume_suggestions(matched=matched, missing=missing, strengths=strengths)
        recommended_roles = self._recommend_roles(resume_keywords, resume_text)
        match_score = self._compute_match_score(matched=len(matched), total=max(len(jd_keywords), 1))
        record = {
            "id": str(uuid4()),
            "title": source_filename or "Uploaded resume",
            "source_filename": source_filename,
            "resume_text": resume_text,
            "jd_text": jd_text,
            "summary": completion.content,
            "match_score": match_score,
            "suggestions": suggestions,
            "ats_keywords": sorted(matched) if jd_text else sorted(resume_keywords)[:25],
            "strengths": strengths,
            "gaps": missing[:12],
            "recommended_roles": recommended_roles,
            "model_profile": profile.id,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "used_llm": completion.used_llm,
            "provider": completion.provider,
        }
        if self.database_client.is_configured:
            self.database_client.save_resume_analysis(record)
        return record

    def chat_resume(
        self,
        *,
        question: str,
        resume_text: str,
        jd_text: str,
        model_profile: Optional[str],
    ) -> Dict[str, Any]:
        profile, completion = self.model_router.complete(
            model_profile=model_profile or self._preferred_profile("resume"),
            prompt=(
                f"Resume:\n{resume_text[:5000]}\n\n"
                f"Job description:\n{jd_text[:5000]}\n\n"
                f"Question:\n{question}"
            ),
            system_prompt=(
                "You are a resume copilot. Answer precisely, quote relevant experience, suggest edits if needed, "
                "and keep the reply concise and recruiter-friendly."
            ),
        )
        return {
            "answer": completion.content,
            "used_llm": completion.used_llm,
            "provider": completion.provider,
            "model_profile": profile.id,
            "suggested_questions": [
                "Which bullets should I rewrite for ATS?",
                "What keywords are still missing for this role?",
                "How should I tighten the summary for this position?",
            ],
        }

    def list_templates(self) -> List[Dict[str, Any]]:
        templates = list(DEFAULT_TEMPLATES)
        if self.database_client.is_configured:
            templates.extend(
                [
                    {**record, "source": "generated"}
                    for record in self.database_client.list_resume_templates(limit=50)
                ]
            )
        return templates

    def design_template(
        self,
        *,
        name: str,
        target_role: str,
        style: str,
        notes: str,
        model_profile: Optional[str],
        created_by: Optional[str],
    ) -> Dict[str, Any]:
        sections = self._template_sections_for_role(target_role)
        design_tokens = self._design_tokens_for_style(style)
        profile, completion = self.model_router.complete(
            model_profile=model_profile or self._preferred_profile("template"),
            prompt=(
                f"Template name: {name}\n"
                f"Target role: {target_role}\n"
                f"Style: {style}\n"
                f"Notes: {notes or 'No additional notes.'}\n"
                f"Sections: {', '.join(sections)}"
            ),
            system_prompt=(
                "You are a resume art director. Produce a Figma-ready creative brief with layout direction, "
                "type hierarchy, spacing, and content framing for a high-conversion resume template."
            ),
        )
        record = {
            "id": str(uuid4()),
            "name": name,
            "target_role": target_role,
            "style": style,
            "notes": notes,
            "figma_prompt": completion.content,
            "sections": sections,
            "design_tokens": design_tokens,
            "preview_markdown": self._preview_markdown(name, target_role, sections),
            "model_profile": profile.id,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "generated",
        }
        if self.database_client.is_configured:
            self.database_client.save_resume_template(record)
        return record

    async def extract_job_description(
        self,
        *,
        url: Optional[str],
        text: Optional[str],
    ) -> Dict[str, Any]:
        if text and text.strip():
            cleaned = text.strip()
            return {
                "title": "Manual job description",
                "company": "Provided manually",
                "description": cleaned,
                "source": "manual",
                "source_type": "manual",
                "keywords": sorted(self._extract_keywords(cleaned))[:20],
            }
        if not url:
            raise ValueError("Either a job description URL or raw text must be provided.")

        source_id = self._validate_job_source(url)
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": "Actypity/2.0"}) as client:
            response = await client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else "Job description"
        description = self._normalize_whitespace(soup.get_text(" ", strip=True))[:8000]
        return {
            "title": title,
            "company": self._guess_company_from_title(title),
            "description": description,
            "source": url,
            "source_type": source_id,
            "keywords": sorted(self._extract_keywords(description))[:20],
        }

    def search_jobs(
        self,
        *,
        keywords: List[str],
        locations: List[str],
        sources: List[str],
        created_by: Optional[str],
    ) -> List[Dict[str, Any]]:
        normalized_keywords = [item.strip() for item in keywords if item.strip()]
        normalized_locations = [item.strip() for item in locations if item.strip()] or ["remote"]
        normalized_sources = [item for item in sources if item in TRUSTED_JOB_PORTALS]
        if not normalized_keywords:
            raise ValueError("At least one keyword is required to search jobs.")
        if not normalized_sources:
            normalized_sources = [source["id"] for source in self.trusted_sources()]

        query = " ".join(normalized_keywords)
        results: List[Dict[str, Any]] = []
        for source in normalized_sources:
            config = TRUSTED_JOB_PORTALS[source]
            for location in normalized_locations:
                keyword_token = quote_plus(query)
                location_token = quote_plus(location)
                search_url = config["search_url"].format(
                    keywords=keyword_token,
                    location=location_token,
                )
                results.append(
                    {
                        "id": str(uuid4()),
                        "title": f"{config['label']} search for {query}",
                        "company": config["label"],
                        "location": location,
                        "url": search_url,
                        "source": source,
                        "summary": f"Open a trusted {config['label']} search for {query} in {location}.",
                        "ats_score": None,
                        "description": f"Trusted job search link for {query} in {location} on {config['label']}.",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

        if self.database_client.is_configured:
            self.database_client.save_career_query(
                {
                    "id": str(uuid4()),
                    "query_type": "job_search",
                    "query_text": query,
                    "sources": normalized_sources,
                    "result_count": len(results),
                    "metadata": {"locations": normalized_locations},
                    "created_by": created_by,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            self.database_client.save_job_search_results(results)
        return results

    def evaluate_resume(
        self,
        *,
        resume_text: str,
        jd_text: str,
        model_profile: Optional[str],
    ) -> Dict[str, Any]:
        from agents.resume_skills_agent import ResumeEvaluatorAgent
        agent = ResumeEvaluatorAgent(
            ollama_client=self._ollama_client(),
            llm_client=self.model_router.llm_client if self.model_router.settings.llm_enabled else None,
        )
        result = agent.execute(
            "evaluate resume",
            context={"resume_text": resume_text, "jd_text": jd_text},
        )
        evaluation = result.metadata.get("evaluation", {})
        return {
            "overall_score": evaluation.get("overall_score", 0),
            "grade": evaluation.get("grade", "?"),
            "ats_risk_level": evaluation.get("ats_risk_level", "unknown"),
            "summary": evaluation.get("summary", result.output),
            "dimensions": evaluation.get("dimensions", {}),
            "top_strengths": evaluation.get("top_strengths", []),
            "critical_fixes": evaluation.get("critical_fixes", []),
            "missing_sections": evaluation.get("missing_sections", []),
            "used_llm": result.used_llm,
            "provider": result.metadata.get("provider", ""),
        }

    def write_resume(
        self,
        *,
        resume_text: str,
        jd_text: str,
        target_role: str,
        section: str,
        candidate_name: str,
        model_profile: Optional[str],
    ) -> Dict[str, Any]:
        from agents.resume_skills_agent import ResumeWriterAgent
        agent = ResumeWriterAgent(
            ollama_client=self._ollama_client(),
            llm_client=self.model_router.llm_client if self.model_router.settings.llm_enabled else None,
        )
        result = agent.execute(
            f"write resume for {target_role}",
            context={
                "resume_text": resume_text,
                "jd_text": jd_text,
                "target_role": target_role,
                "section": section,
                "candidate_name": candidate_name,
            },
        )
        written = result.metadata.get("written_content", {})
        return {
            "target_role": target_role,
            "written_content": {
                "professional_summary": written.get("professional_summary", ""),
                "experience_bullets": written.get("experience_bullets", []),
                "skills_section": written.get("skills_section", {}),
                "objective_statement": written.get("objective_statement", ""),
                "keywords_embedded": written.get("keywords_embedded", []),
                "writing_notes": written.get("writing_notes", ""),
            },
            "used_llm": result.used_llm,
            "provider": result.metadata.get("provider", ""),
        }

    def review_resume(
        self,
        *,
        resume_text: str,
        jd_text: str,
        target_role: str,
        model_profile: Optional[str],
    ) -> Dict[str, Any]:
        from agents.resume_skills_agent import ResumeReviewerAgent
        agent = ResumeReviewerAgent(
            ollama_client=self._ollama_client(),
            llm_client=self.model_router.llm_client if self.model_router.settings.llm_enabled else None,
        )
        result = agent.execute(
            "review resume",
            context={
                "resume_text": resume_text,
                "jd_text": jd_text,
                "target_role": target_role,
            },
        )
        review = result.metadata.get("review", {})
        return {
            "overall_verdict": review.get("overall_verdict", result.output),
            "interview_probability": review.get("interview_probability", "medium"),
            "sections": review.get("sections", {}),
            "top_3_immediate_actions": review.get("top_3_immediate_actions", []),
            "red_flags": review.get("red_flags", []),
            "interview_tips": review.get("interview_tips", []),
            "used_llm": result.used_llm,
            "provider": result.metadata.get("provider", ""),
        }

    async def live_hunt_jobs(
        self,
        *,
        resume_text: str,
        location: str,
        experience_years: float,
        model_profile: Optional[str],
    ) -> Dict[str, Any]:
        from .job_search_service import LiveJobSearchService

        resume_keywords = self._extract_keywords(resume_text)
        candidate_name = self._extract_name(resume_text)
        target_roles = self._recommend_roles(resume_keywords, resume_text)[:5]

        searcher = LiveJobSearchService()
        raw_jobs = await searcher.search_for_resume(
            target_roles=target_roles,
            location=location,
            experience_years=experience_years,
            limit_per_role=8,
        )

        analyzed: List[Dict[str, Any]] = []
        for job in raw_jobs:
            fit = self._analyze_job_fit(resume_keywords, job)
            analyzed.append({**job, **fit})

        analyzed.sort(key=lambda j: j["match_score"], reverse=True)
        for j in analyzed:
            score = j["match_score"]
            j["tier"] = "high" if score >= 60 else "medium" if score >= 35 else "stretch"

        high = [j for j in analyzed if j["tier"] == "high"]
        medium = [j for j in analyzed if j["tier"] == "medium"]
        stretch = [j for j in analyzed if j["tier"] == "stretch"]

        return {
            "candidate_name": candidate_name,
            "target_roles": target_roles,
            "total_found": len(analyzed),
            "jobs": analyzed,
            "high_tier": high,
            "medium_tier": medium,
            "stretch_tier": stretch,
        }

    def _extract_name(self, resume_text: str) -> str:
        for line in resume_text.splitlines()[:10]:
            line = line.strip().rstrip('.,|:')
            if re.match(r'^[A-Z][a-z]+(?: [A-Z][a-z]+){1,3}$', line):
                return line
        # fallback: scan first 400 chars for a capitalised 2-word name
        match = re.search(r'\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2})\b', resume_text[:400])
        return match.group(1) if match else "Candidate"

    def _analyze_job_fit(self, resume_keywords: set[str], job: Dict[str, Any]) -> Dict[str, Any]:
        jd_text = job.get("jd_full") or job.get("jd_snippet", "")
        jd_keywords = self._extract_keywords(jd_text)
        matched = sorted(resume_keywords & jd_keywords)
        missing = sorted(jd_keywords - resume_keywords)
        match_score = self._compute_match_score(matched=len(matched), total=max(len(jd_keywords), 1))

        improvement_areas: List[str] = []
        if missing[:6]:
            improvement_areas.append(f"Add these missing keywords: {', '.join(missing[:6])}")
        if match_score < 60:
            improvement_areas.append("Tailor your professional summary to mirror this role's core requirements")
        if match_score < 40:
            improvement_areas.append("Quantify achievements in domains this JD emphasises")
            improvement_areas.append("Rewrite 2-3 experience bullets to align with the role's language")

        if match_score >= 60:
            ats_summary = f"{match_score}% keyword match — strong fit, apply now."
        elif match_score >= 35:
            ats_summary = f"{match_score}% keyword match — partial fit, tailor your resume before applying."
        else:
            ats_summary = f"{match_score}% keyword match — stretch opportunity, significant gaps to address."

        return {
            "match_score": match_score,
            "matched_keywords": matched[:18],
            "missing_keywords": missing[:12],
            "improvement_areas": improvement_areas,
            "ats_summary": ats_summary,
        }

    def hunt_jobs(
        self,
        *,
        resume_text: str,
        location: str,
        experience_years: float,
        top_count: int,
        model_profile: Optional[str],
    ) -> Dict[str, Any]:
        from agents.job_applicant_agent import JobApplicantAgent
        agent = JobApplicantAgent(
            ollama_client=self._ollama_client(),
            llm_client=self.model_router.llm_client if self.model_router.settings.llm_enabled else None,
        )
        result = agent.execute(
            "job hunt",
            context={
                "resume_text": resume_text,
                "location": location,
                "experience_years": experience_years,
                "top_count": top_count,
            },
        )
        md = result.metadata
        return {
            "candidate_name": md.get("candidate_name", "Candidate"),
            "target_roles": md.get("target_roles", []),
            "total_opportunities": md.get("total", 0),
            "opportunities": md.get("opportunities", []),
            "high_tier": md.get("high_tier", []),
            "medium_tier": md.get("medium_tier", []),
            "stretch_tier": md.get("stretch_tier", []),
            "tailored_applications": md.get("tailored_applications", []),
            "profile": md.get("profile", {}),
        }

    def _ollama_client(self):
        # Lazy-import to avoid circular dependency; container wires the router
        from .local_llm import OllamaClient
        router = self.model_router
        if hasattr(router, "ollama_client") and router.ollama_client and router.ollama_client.enabled:
            return router.ollama_client
        return None

    def analytics(self) -> Dict[str, Any]:
        if self.database_client.is_configured:
            return self.database_client.get_career_analytics()
        return {
            "total_resume_analyses": 0,
            "total_templates": len(DEFAULT_TEMPLATES),
            "total_job_queries": 0,
            "total_job_results": 0,
            "average_match_score": 0.0,
            "top_sources": {},
        }

    def _preferred_profile(self, workload: str) -> Optional[str]:
        if workload == "resume" and self.settings.llama_resume_model_path:
            return "llama-local-resume"
        if workload == "job" and self.settings.llama_job_model_path:
            return "llama-local-jd"
        if workload == "template" and self.settings.llama_template_model_path:
            return "llama-local-template"
        if self.settings.llama_model_path:
            return "llama-local-general"
        if self.settings.azure_openai_deployment:
            return "azure-general"
        return None

    def _validate_job_source(self, url: str) -> str:
        hostname = (urlparse(url).hostname or "").lower()
        for source_id, config in TRUSTED_JOB_PORTALS.items():
            if hostname in config["hosts"]:
                return source_id
        raise ValueError("Only trusted job portal URLs are accepted.")

    def _extract_keywords(self, text: str) -> set[str]:
        # Only match alphanumeric + technical chars (+#); no dots to avoid URL/company-name noise
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#]{2,}", text.lower())
        stop_words = {
            "with", "from", "that", "this", "have", "will", "your", "their", "about",
            "role", "team", "work", "experience", "years", "skills", "using", "build",
            "strong", "ability", "preferred", "required", "responsible", "you", "the",
            "and", "for", "are", "our", "can", "has", "not", "all", "but", "its",
            "who", "how", "was", "did", "new", "also", "any", "get", "one", "may",
            "job", "include", "including", "position", "company", "candidates",
            "opportunity", "looking", "seeking", "join", "part", "full", "time",
            "remote", "hybrid", "onsite", "apply", "email", "send", "resume", "please",
        }
        return {token for token in tokens if token not in stop_words and len(token) > 2}

    def _extract_bullets(self, text: str, limit: int) -> List[str]:
        lines = [
            self._normalize_whitespace(line)
            for line in text.splitlines()
            if self._normalize_whitespace(line)
        ]
        return lines[:limit]

    def _build_resume_suggestions(self, *, matched: List[str], missing: List[str], strengths: List[str]) -> List[str]:
        suggestions: List[str] = []
        if missing:
            suggestions.append(f"Add evidence for missing job keywords: {', '.join(missing[:6])}.")
        if strengths:
            suggestions.append(f"Rewrite top bullets to foreground impact: {strengths[0][:120]}.")
        if not matched:
            suggestions.append("Mirror more role-specific terminology from the job description in the summary and experience sections.")
        suggestions.append("Quantify outcomes with metrics, scale, ownership, or business impact wherever possible.")
        return suggestions[:4]

    def _fix_pdf_text(self, text: str) -> str:
        # Split camelCase run-ons produced by some PDF extractors (e.g. "abilityto" → no fix, but "leadershipAI" → "leadership AI")
        text = re.sub(r'([a-z]{2})([A-Z][a-z])', r'\1 \2', text)
        # Re-space lowercase run-ons where a known boundary word is fused (e.g. "aboutusing" → "about using")
        boundary_words = (
            "about|ability|across|also|and|are|as|at|be|been|being|between|by|can|career|"
            "with|within|without|worked|working|years|using|used|through|to|the|that|their|"
            "of|on|or|in|into|is|it|for|from|has|have|helping|including|leveraging|managing|"
            "multiple|new|not|over|product|providing|responsible|since|skills|such|team|led"
        )
        text = re.sub(rf'({boundary_words})([A-Z])', r'\1 \2', text, flags=re.IGNORECASE)
        # Fix missing space before capitalised words that immediately follow lowercase (heurisitc for missing spaces)
        text = re.sub(r'([a-z]{3,})([A-Z][a-z]{2,})', r'\1 \2', text)
        # Collapse multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        return text

    def _detect_seniority(self, keywords: set[str], resume_text: str) -> str:
        text_lower = resume_text.lower()
        vp_signals = {"vp", "vice president", "executive vice", "evp", "svp", "chief", "cto", "cdo", "cpo"}
        director_signals = {"director", "associate director", "senior director", "head of"}
        manager_signals = {"manager", "lead", "principal", "staff", "senior"}
        if vp_signals & keywords or any(s in text_lower for s in vp_signals):
            return "vp"
        if director_signals & keywords or any(s in text_lower for s in director_signals):
            return "director"
        if manager_signals & keywords:
            return "manager"
        # Heuristic: count experience year mentions
        year_matches = re.findall(r'(\d+)\s*\+?\s*years?', text_lower)
        max_years = max((int(y) for y in year_matches), default=0)
        if max_years >= 15:
            return "vp"
        if max_years >= 8:
            return "director"
        if max_years >= 4:
            return "manager"
        return "ic"

    def _recommend_roles(self, keywords: set[str], resume_text: str = "") -> List[str]:
        seniority = self._detect_seniority(keywords, resume_text)
        is_ai = bool({"ai", "genai", "llm", "langchain", "rag", "mlops", "pytorch", "tensorflow",
                      "machine", "learning", "nlp", "data", "ml"} & keywords)
        is_data = bool({"data", "analytics", "bi", "sql", "tableau", "powerbi", "databricks"} & keywords)
        is_frontend = bool({"react", "typescript", "frontend", "angular", "vue"} & keywords)
        is_backend = bool({"python", "fastapi", "backend", "django", "flask", "node"} & keywords)
        is_consulting = bool({"consulting", "strategy", "engagement", "advisory", "mckinsey",
                              "deloitte", "kpmg", "pwc", "accenture"} & keywords)

        if seniority == "vp":
            if is_ai:
                return ["VP AI / Head of AI", "Chief AI Officer", "SVP Data & AI", "Director of AI Labs", "VP Engineering (AI)"]
            if is_data:
                return ["VP Data & Analytics", "Chief Data Officer", "Head of Data Science"]
            if is_consulting:
                return ["Partner / Principal", "VP Strategy & AI", "Managing Director – Digital"]
            return ["VP Engineering", "SVP Technology", "CTO – Scale-up"]
        if seniority == "director":
            if is_ai:
                return ["Director of AI", "Head of GenAI", "Director ML Engineering", "Principal AI Architect"]
            if is_data:
                return ["Director Data Science", "Head of Analytics", "Principal Data Engineer"]
            if is_frontend:
                return ["Director of Engineering – Frontend", "Head of Product Engineering"]
            if is_backend:
                return ["Director of Backend Engineering", "Principal Platform Engineer"]
            return ["Director of Engineering", "Head of Technology", "Senior Engineering Manager"]
        if seniority == "manager":
            if is_ai:
                return ["Senior ML Engineer", "AI/ML Tech Lead", "Senior Data Scientist", "ML Platform Lead"]
            if is_frontend:
                return ["Senior Frontend Engineer", "Tech Lead – Frontend", "Staff Product Engineer"]
            if is_backend:
                return ["Senior Backend Engineer", "Platform Engineer", "Applied AI Engineer"]
            return ["Engineering Manager", "Tech Lead", "Senior Software Engineer"]
        # IC / fresher
        if is_ai:
            return ["Machine Learning Engineer", "Data Scientist", "AI Engineer", "NLP Engineer"]
        if {"react", "typescript", "frontend"} & keywords:
            return ["Frontend Engineer", "React Developer", "UI Engineer"]
        if {"python", "fastapi", "backend"} & keywords:
            return ["Backend Engineer", "Software Engineer", "SDE-1"]
        return ["Software Engineer", "Graduate Engineer Trainee", "Associate Software Developer"]

    def _compute_match_score(self, *, matched: int, total: int) -> int:
        return max(0, min(100, round((matched / total) * 100)))

    def _template_sections_for_role(self, target_role: str) -> List[str]:
        role = target_role.lower()
        if "design" in role:
            return ["Header", "Profile", "Case Studies", "Experience", "Toolbox", "Education"]
        if "engineer" in role or "developer" in role:
            return ["Header", "Summary", "Technical Skills", "Experience", "Projects", "Education"]
        return ["Header", "Summary", "Experience", "Achievements", "Skills", "Education"]

    def _design_tokens_for_style(self, style: str) -> Dict[str, str]:
        style_key = style.lower()
        if "minimal" in style_key:
            return {
                "primary": "#102a43",
                "accent": "#f0b429",
                "surface": "#f7fafc",
                "font_heading": "Manrope",
                "font_body": "Source Sans 3",
            }
        if "creative" in style_key or "bold" in style_key:
            return {
                "primary": "#2b2d42",
                "accent": "#ef476f",
                "surface": "#fff8f0",
                "font_heading": "Space Grotesk",
                "font_body": "Plus Jakarta Sans",
            }
        return {
            "primary": "#0b132b",
            "accent": "#3a86ff",
            "surface": "#f8f9fb",
            "font_heading": "Sora",
            "font_body": "Inter",
        }

    def _preview_markdown(self, name: str, target_role: str, sections: List[str]) -> str:
        return (
            f"# {name}\n\n"
            f"Designed for **{target_role}**.\n\n"
            f"Sections:\n- " + "\n- ".join(sections)
        )

    def _guess_company_from_title(self, title: str) -> str:
        if " at " in title.lower():
            return title.split(" at ", 1)[-1].strip()
        return "Unknown"

    def _normalize_whitespace(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()
