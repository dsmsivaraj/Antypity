"""Resume and Job Description analysis agents using local Llama (Ollama).

- LocalResumeAgent   — parses resume text and extracts structured insights locally
- LocalJDAgent       — analyses job description text, extracts requirements locally
- ResumeTemplateAgent — recommends or generates resume templates
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from shared.base_agent import AgentMetadata, AgentResult, BaseAgent


class LocalResumeAgent(BaseAgent):
    """Runs resume analysis locally via Ollama (no data leaves the machine)."""

    def __init__(self, ollama_client) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="local-resume-analyzer",
                description="Locally analyses resume text using Llama. Extracts skills, experience, gaps, and ATS keywords without sending data to the cloud.",
                capabilities=["resume analysis", "ATS keywords", "skill extraction", "career gap detection", "local LLM"],
                preferred_model="ollama-llama3",
            )
        )
        self._ollama = ollama_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        if any(kw in t for kw in ("analyze resume", "parse resume", "resume skills", "resume keywords", "ats score", "resume gaps")):
            return 88
        return 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        resume_text = (context or {}).get("resume_text", "") or task
        if len(resume_text) < 50:
            return AgentResult(
                output="Please provide resume text in the context['resume_text'] field.",
                used_llm=False,
                metadata={"error": "no_resume_text"},
            )

        system = (
            "You are an expert ATS (Applicant Tracking System) analyst. "
            "Extract structured information from the resume. "
            "Always respond with valid JSON only — no extra text."
        )
        prompt = f"""Analyse this resume and respond ONLY with a JSON object with these keys:
- "name": candidate full name (string or null)
- "email": email address (string or null)
- "summary": 2-sentence professional summary
- "skills": list of technical and soft skills (list of strings)
- "ats_keywords": top 15 ATS-relevant keywords from the resume
- "experience_years": estimated years of total experience (number)
- "education": highest degree and field (string)
- "strengths": list of 3 key strengths
- "gaps": list of any notable gaps or weaknesses
- "suggestions": list of 3 actionable improvements for ATS optimisation

RESUME:
{resume_text[:4000]}"""

        result = self._ollama.complete(prompt, system_prompt=system)
        parsed = _safe_json(result.content, {})

        output_lines = [
            f"Resume Analysis (via {result.provider})",
            f"Name: {parsed.get('name', 'Unknown')}",
            f"Experience: {parsed.get('experience_years', '?')} years",
            f"Education: {parsed.get('education', 'Not found')}",
            f"Skills ({len(parsed.get('skills', []))}): {', '.join((parsed.get('skills') or [])[:8])}",
            f"ATS Keywords: {', '.join((parsed.get('ats_keywords') or [])[:10])}",
        ]

        return AgentResult(
            output="\n".join(output_lines),
            used_llm=result.used_llm,
            metadata={
                "provider": result.provider,
                "analysis": parsed,
                "ats_keywords": parsed.get("ats_keywords", []),
                "skills": parsed.get("skills", []),
                "suggestions": parsed.get("suggestions", []),
            },
        )


class LocalJDAgent(BaseAgent):
    """Locally analyses job description text using Llama."""

    def __init__(self, ollama_client) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="local-jd-analyzer",
                description="Locally analyses job description text. Extracts required skills, responsibilities, and match criteria without cloud calls.",
                capabilities=["job description analysis", "requirements extraction", "local LLM", "JD parsing"],
                preferred_model="ollama-llama3",
            )
        )
        self._ollama = ollama_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        if any(kw in t for kw in ("analyze job", "job description", "jd analysis", "job requirements", "parse jd")):
            return 88
        return 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        jd_text = (context or {}).get("jd_text", "") or task
        if len(jd_text) < 30:
            return AgentResult(
                output="Please provide job description text in context['jd_text'].",
                used_llm=False,
                metadata={"error": "no_jd_text"},
            )

        system = (
            "You are a recruitment expert. Extract structured requirements from job descriptions. "
            "Always respond with valid JSON only."
        )
        prompt = f"""Analyse this job description and respond ONLY with a JSON object:
- "title": job title
- "company": company name or null
- "location": location or "Remote"
- "required_skills": list of must-have technical skills
- "preferred_skills": list of nice-to-have skills
- "responsibilities": list of top 5 key responsibilities
- "experience_required": string like "3-5 years" or "Senior"
- "education_required": required degree/field or null
- "keywords": top 15 ATS keywords from this JD
- "seniority": "junior"/"mid"/"senior"/"lead"/"executive"
- "industry": industry sector

JOB DESCRIPTION:
{jd_text[:4000]}"""

        result = self._ollama.complete(prompt, system_prompt=system)
        parsed = _safe_json(result.content, {})

        return AgentResult(
            output=f"JD Analysis: {parsed.get('title', 'Unknown Role')} at {parsed.get('company', 'Unknown')} ({parsed.get('seniority', '?')} level)",
            used_llm=result.used_llm,
            metadata={
                "provider": result.provider,
                "analysis": parsed,
                "keywords": parsed.get("keywords", []),
                "required_skills": parsed.get("required_skills", []),
            },
        )


class ResumeTemplateAgent(BaseAgent):
    """Recommends resume templates based on career context and generates content suggestions."""

    def __init__(self, figma_client, ollama_client) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="resume-template-advisor",
                description="Recommends resume templates from Figma community library based on role type and provides AI-generated template content suggestions.",
                capabilities=["resume templates", "template recommendation", "Figma", "resume design"],
            )
        )
        self._figma = figma_client
        self._ollama = ollama_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        if any(kw in t for kw in ("resume template", "template", "design resume", "figma", "cv template", "resume format")):
            return 85
        return 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        ctx = context or {}
        role = ctx.get("role", "")
        industry = ctx.get("industry", "")
        resume_analysis = ctx.get("resume_analysis", {})

        templates = self._figma.list_templates()

        # Use Ollama to match best template
        match_prompt = (
            f"A candidate is looking for a resume template. "
            f"Role: {role or 'not specified'}. Industry: {industry or 'not specified'}. "
            f"Available templates: {json.dumps([{'id': t['id'], 'name': t['name'], 'style': t['style'], 'tags': t.get('tags', [])} for t in templates])}. "
            f"Respond ONLY with JSON: {{\"recommended_id\": \"<id>\", \"reason\": \"<one sentence>\"}}"
        )
        match_result = self._ollama.complete(match_prompt)
        match_data = _safe_json(match_result.content, {})
        recommended_id = match_data.get("recommended_id", templates[0]["id"] if templates else "")
        recommended = next((t for t in templates if t["id"] == recommended_id), templates[0] if templates else {})

        return AgentResult(
            output=f"Recommended template: {recommended.get('name', 'Unknown')} — {match_data.get('reason', '')}",
            used_llm=match_result.used_llm,
            metadata={
                "templates": templates,
                "recommended": recommended,
                "reason": match_data.get("reason", ""),
            },
        )


def _safe_json(text: str, default: Any) -> Any:
    """Extract and parse the first JSON object from text."""
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the text
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return default
