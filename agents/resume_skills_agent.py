"""Resume skill agents: Evaluator, Writer, Reviewer.

Three focused agents that can be used standalone or composed by the
JobApplicantAgent pipeline.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from shared.base_agent import AgentMetadata, AgentResult, BaseAgent


# ── helpers ───────────────────────────────────────────────────────────────────

def _safe_json(text: str, default: Any = None) -> Any:
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return default if default is not None else {}


def _safe_list(text: str) -> List[str]:
    data = _safe_json(text, [])
    if isinstance(data, list):
        return [str(item) for item in data]
    if isinstance(data, dict):
        for key in ("items", "list", "points", "suggestions"):
            if isinstance(data.get(key), list):
                return [str(i) for i in data[key]]
    return [line.lstrip("•-*0123456789. ").strip() for line in text.splitlines() if line.strip()][:10]


# ── ResumeEvaluatorAgent ──────────────────────────────────────────────────────

class ResumeEvaluatorAgent(BaseAgent):
    """Deep ATS evaluation with section-level scoring and prioritised fix list."""

    def __init__(self, ollama_client=None, llm_client=None) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="resume-evaluator",
                description="Scores a resume across 6 ATS dimensions (format, keywords, experience, education, impact, readability) and returns a 0-100 grade with a prioritised improvement list.",
                capabilities=["resume evaluation", "ATS scoring", "resume quality", "resume scoring"],
            )
        )
        self._ollama = ollama_client
        self._llm = llm_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        if any(kw in t for kw in ("evaluate resume", "score resume", "resume score", "ats score", "resume rating", "rate my resume")):
            return 90
        return 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        ctx = context or {}
        resume_text = ctx.get("resume_text", "") or task
        jd_text = ctx.get("jd_text", "")
        if len(resume_text) < 50:
            return AgentResult(
                output="Provide resume text in context['resume_text'].",
                used_llm=False,
                metadata={"error": "no_resume_text"},
            )

        jd_block = f"\n\nJob Description (for matching):\n{jd_text[:3000]}" if jd_text else ""
        system = (
            "You are a senior ATS specialist and recruiter with 15 years of experience. "
            "Evaluate resumes against 6 scoring dimensions. Respond ONLY with valid JSON."
        )
        prompt = f"""Evaluate this resume and respond ONLY with JSON:
{{
  "overall_score": <0-100 integer>,
  "grade": "<A/B/C/D/F>",
  "dimensions": {{
    "format_structure": {{"score": <0-20>, "max": 20, "notes": "<one line>"}},
    "keyword_density": {{"score": <0-20>, "max": 20, "notes": "<one line>"}},
    "experience_impact": {{"score": <0-20>, "max": 20, "notes": "<one line>"}},
    "education_credentials": {{"score": <0-15>, "max": 15, "notes": "<one line>"}},
    "quantified_achievements": {{"score": <0-15>, "max": 15, "notes": "<one line>"}},
    "readability_concision": {{"score": <0-10>, "max": 10, "notes": "<one line>"}}
  }},
  "top_strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "critical_fixes": ["<fix 1>", "<fix 2>", "<fix 3>", "<fix 4>", "<fix 5>"],
  "missing_sections": ["<section>"],
  "ats_risk_level": "<low|medium|high>",
  "summary": "<2-3 sentence overall verdict>"
}}

RESUME:
{resume_text[:5000]}{jd_block}"""

        client = self._ollama or self._llm
        if not client:
            return AgentResult(output="No LLM client configured.", used_llm=False, metadata={"error": "no_client"})

        result = client.complete(prompt, system_prompt=system)
        parsed = _safe_json(result.content)

        score = parsed.get("overall_score", 0)
        grade = parsed.get("grade", "?")
        risk = parsed.get("ats_risk_level", "unknown")

        output = (
            f"Resume Evaluation — Score: {score}/100 (Grade {grade})\n"
            f"ATS Risk: {risk.upper()}\n"
            f"Summary: {parsed.get('summary', '')}\n\n"
            f"Critical Fixes:\n" + "\n".join(f"  {i+1}. {f}" for i, f in enumerate(parsed.get("critical_fixes", [])))
        )

        return AgentResult(
            output=output,
            used_llm=result.used_llm,
            metadata={
                "provider": result.provider,
                "evaluation": parsed,
                "overall_score": score,
                "grade": grade,
                "ats_risk_level": risk,
                "critical_fixes": parsed.get("critical_fixes", []),
                "dimensions": parsed.get("dimensions", {}),
            },
        )


# ── ResumeWriterAgent ─────────────────────────────────────────────────────────

class ResumeWriterAgent(BaseAgent):
    """AI resume writer: generates or rewrites resume sections for a target role."""

    def __init__(self, ollama_client=None, llm_client=None) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="resume-writer",
                description="Writes or rewrites resume sections (summary, experience bullets, skills, objective) optimised for a target role and ATS keywords from the job description.",
                capabilities=["resume writing", "content generation", "bullet rewriting", "resume summary", "ATS optimisation"],
            )
        )
        self._ollama = ollama_client
        self._llm = llm_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        if any(kw in t for kw in ("write resume", "rewrite resume", "generate resume", "improve resume", "resume content", "write bullet", "rewrite bullet")):
            return 90
        return 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        ctx = context or {}
        resume_text = ctx.get("resume_text", "")
        jd_text = ctx.get("jd_text", "")
        target_role = ctx.get("target_role", "Software Engineer")
        section = ctx.get("section", "all")
        candidate_name = ctx.get("candidate_name", "the candidate")

        if not resume_text and not jd_text:
            return AgentResult(
                output="Provide resume_text and/or jd_text and target_role in context.",
                used_llm=False,
                metadata={"error": "missing_context"},
            )

        system = (
            "You are a professional resume writer and career coach. You write compelling, "
            "ATS-optimised resume content. Use strong action verbs, quantified impact, "
            "and naturally embed job keywords. Respond ONLY with JSON."
        )

        prompt = f"""You are writing/improving a resume for: {candidate_name}
Target Role: {target_role}
Section to write: {section}

Existing Resume (if any):
{resume_text[:4000] if resume_text else "New resume — use candidate background from context."}

Job Description (for keyword alignment):
{jd_text[:3000] if jd_text else "Not provided — write for general {target_role} roles."}

Respond ONLY with JSON:
{{
  "professional_summary": "<3-4 impactful sentences starting with a strong role identity>",
  "experience_bullets": [
    "<action verb + task + quantified result>",
    "<action verb + task + quantified result>",
    "<action verb + task + quantified result>",
    "<action verb + task + quantified result>",
    "<action verb + task + quantified result>"
  ],
  "skills_section": {{
    "technical": ["<skill 1>", "<skill 2>", ...],
    "tools": ["<tool 1>", "<tool 2>", ...],
    "soft_skills": ["<skill 1>", "<skill 2>"]
  }},
  "objective_statement": "<1-2 sentence career objective for fresher/entry-level if applicable>",
  "keywords_embedded": ["<key1>", "<key2>", "<key3>"],
  "writing_notes": "<brief explanation of choices made>"
}}"""

        client = self._ollama or self._llm
        if not client:
            return AgentResult(output="No LLM client configured.", used_llm=False, metadata={"error": "no_client"})

        result = client.complete(prompt, system_prompt=system)
        parsed = _safe_json(result.content)

        output_parts = [f"Resume Content Generated for: {target_role}"]
        if parsed.get("professional_summary"):
            output_parts.append(f"\nSUMMARY:\n{parsed['professional_summary']}")
        if parsed.get("experience_bullets"):
            output_parts.append("\nEXPERIENCE BULLETS:\n" + "\n".join(f"• {b}" for b in parsed["experience_bullets"]))
        if parsed.get("objective_statement"):
            output_parts.append(f"\nOBJECTIVE:\n{parsed['objective_statement']}")

        return AgentResult(
            output="\n".join(output_parts),
            used_llm=result.used_llm,
            metadata={
                "provider": result.provider,
                "written_content": parsed,
                "target_role": target_role,
                "keywords_embedded": parsed.get("keywords_embedded", []),
            },
        )


# ── ResumeReviewerAgent ───────────────────────────────────────────────────────

class ResumeReviewerAgent(BaseAgent):
    """Section-by-section review with actionable feedback for each part of the resume."""

    def __init__(self, ollama_client=None, llm_client=None) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="resume-reviewer",
                description="Reviews every section of a resume like a senior hiring manager — header, summary, experience, education, skills — and returns specific, actionable feedback with a section-level score.",
                capabilities=["resume review", "section feedback", "hiring manager review", "resume coaching", "interview preparation"],
            )
        )
        self._ollama = ollama_client
        self._llm = llm_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        if any(kw in t for kw in ("review resume", "feedback on resume", "improve my resume", "resume feedback", "critique resume")):
            return 90
        return 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        ctx = context or {}
        resume_text = ctx.get("resume_text", "") or task
        jd_text = ctx.get("jd_text", "")
        target_role = ctx.get("target_role", "")

        if len(resume_text) < 50:
            return AgentResult(
                output="Provide resume text in context['resume_text'].",
                used_llm=False,
                metadata={"error": "no_resume_text"},
            )

        role_context = f"Target Role: {target_role}\n" if target_role else ""
        jd_block = f"\nJob Description:\n{jd_text[:2000]}\n" if jd_text else ""

        system = (
            "You are a senior hiring manager and resume coach who has reviewed 10,000+ resumes. "
            "Give honest, specific, actionable feedback. No generic advice. Respond ONLY with JSON."
        )

        prompt = f"""{role_context}Review this resume section by section like a senior hiring manager.
{jd_block}
Respond ONLY with JSON:
{{
  "overall_verdict": "<honest 2-3 sentence verdict>",
  "interview_probability": "<low|medium|high>",
  "sections": {{
    "header_contact": {{
      "score": <0-10>,
      "feedback": "<specific feedback>",
      "fixes": ["<fix 1>", "<fix 2>"]
    }},
    "summary_objective": {{
      "score": <0-10>,
      "feedback": "<specific feedback>",
      "fixes": ["<fix 1>", "<fix 2>"]
    }},
    "experience": {{
      "score": <0-10>,
      "feedback": "<specific feedback>",
      "fixes": ["<fix 1>", "<fix 2>"]
    }},
    "education": {{
      "score": <0-10>,
      "feedback": "<specific feedback>",
      "fixes": ["<fix 1>"]
    }},
    "skills": {{
      "score": <0-10>,
      "feedback": "<specific feedback>",
      "fixes": ["<fix 1>", "<fix 2>"]
    }},
    "projects_achievements": {{
      "score": <0-10>,
      "feedback": "<specific feedback>",
      "fixes": ["<fix 1>"]
    }}
  }},
  "top_3_immediate_actions": ["<action 1>", "<action 2>", "<action 3>"],
  "red_flags": ["<flag if any>"],
  "interview_tips": ["<tip 1>", "<tip 2>"]
}}

RESUME:
{resume_text[:5000]}"""

        client = self._ollama or self._llm
        if not client:
            return AgentResult(output="No LLM client configured.", used_llm=False, metadata={"error": "no_client"})

        result = client.complete(prompt, system_prompt=system)
        parsed = _safe_json(result.content)

        prob = parsed.get("interview_probability", "?")
        verdict = parsed.get("overall_verdict", "")
        actions = parsed.get("top_3_immediate_actions", [])

        output = (
            f"Resume Review\n"
            f"Interview Probability: {prob.upper()}\n"
            f"Verdict: {verdict}\n\n"
            f"Top 3 Immediate Actions:\n" + "\n".join(f"  {i+1}. {a}" for i, a in enumerate(actions))
        )

        return AgentResult(
            output=output,
            used_llm=result.used_llm,
            metadata={
                "provider": result.provider,
                "review": parsed,
                "interview_probability": prob,
                "sections": parsed.get("sections", {}),
                "red_flags": parsed.get("red_flags", []),
                "interview_tips": parsed.get("interview_tips", []),
            },
        )
