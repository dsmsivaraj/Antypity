from __future__ import annotations

import re
from typing import Dict, List, Optional

SKILL_KEYWORDS = [
    "python", "java", "sql", "aws", "docker", "react", "typescript", "node",
    "tensorflow", "pytorch", "pandas", "numpy", "c++", "c#", "html", "css",
    "kubernetes", "gcp", "azure", "leadership", "management", "product",
    "javascript", "golang", "rust", "scala", "spark", "kafka", "redis",
    "postgresql", "mongodb", "fastapi", "django", "flask", "spring",
    "machine learning", "deep learning", "nlp", "llm", "openai", "genai",
    "ci/cd", "terraform", "ansible", "linux", "git", "agile", "scrum",
    "data engineering", "data science", "mlops", "devops", "restful", "graphql",
    "microservices", "system design", "api design", "product management",
]

EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{6,}\d)")
DEGREE_KEYWORDS = ["bachelor", "master", "m.sc", "msc", "mba", "phd", "b.s.", "bsc", "bs", "ba", "b.e.", "m.e.", "b.tech", "m.tech"]

_nlp = None


def _get_nlp():
    """Lazy-load spaCy model with graceful fallback when unavailable."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = False  # sentinel: spaCy or model unavailable
    return _nlp if _nlp is not False else None


def parse_resume_text(text: str) -> Dict[str, object]:
    """Resume canonicalizer using NER (spaCy) + regex fallback.

    Returns: name, emails, phones, skills, education, summary, companies
    """
    if not text:
        return {
            "name": None,
            "emails": [],
            "phones": [],
            "skills": [],
            "education": [],
            "summary": "",
            "companies": [],
        }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    full_text = "\n".join(lines)

    # Emails
    emails = list(dict.fromkeys(EMAIL_RE.findall(full_text)))

    # Phones
    raw_phones = PHONE_RE.findall(full_text)
    phones = list(dict.fromkeys([re.sub(r"\s+", " ", p).strip() for p in raw_phones]))

    # Skills: keyword list match
    lowered = full_text.lower()
    found_skills: List[str] = []
    for skill in SKILL_KEYWORDS:
        if re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", lowered):
            found_skills.append(skill)

    # Education
    education: List[str] = []
    for deg in DEGREE_KEYWORDS:
        if deg in lowered:
            education.append(deg)

    # Summary: experience section or first lines
    summary = ""
    exp_idx: Optional[int] = None
    for i, ln in enumerate(lines):
        if re.search(r"experience|professional experience|work experience", ln, re.I):
            exp_idx = i
            break
    if exp_idx is not None:
        summary = " ".join(lines[exp_idx + 1: exp_idx + 4])
    else:
        summary = " ".join(lines[1:4]) if len(lines) > 1 else (lines[0] if lines else "")

    # Name heuristic (regex fallback)
    name: Optional[str] = None
    if lines:
        candidate = lines[0]
        if len(candidate.split()) <= 4 and any(c.isalpha() for c in candidate) and candidate == candidate.title():
            name = candidate
        elif len(lines) > 1:
            candidate = lines[1]
            if len(candidate.split()) <= 4 and candidate == candidate.title():
                name = candidate

    companies: List[str] = []

    # spaCy NER upgrade: PERSON → name, ORG → companies, noun chunks → extra skills
    nlp = _get_nlp()
    if nlp is not None:
        doc = nlp(full_text[:5000])
        person_ents = [
            e.text for e in doc.ents
            if e.label_ == "PERSON" and len(e.text.split()) >= 2
        ]
        if person_ents:
            name = person_ents[0]

        companies = list(dict.fromkeys(
            e.text for e in doc.ents if e.label_ == "ORG"
        ))[:10]

        # Noun-chunk skill augmentation: short multi-word phrases not all stop-words
        chunk_skills = [
            chunk.text.lower()
            for chunk in doc.noun_chunks
            if 1 <= len(chunk) <= 3 and not all(t.is_stop for t in chunk)
        ]
        for cs in chunk_skills:
            if cs in lowered and cs not in found_skills:
                found_skills.append(cs)

    return {
        "name": name,
        "emails": emails,
        "phones": phones,
        "skills": list(dict.fromkeys(found_skills)),
        "education": education,
        "summary": summary,
        "companies": companies,
    }
