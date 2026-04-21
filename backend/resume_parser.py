import re
from typing import Dict, List

SKILL_KEYWORDS = [
    "python",
    "java",
    "sql",
    "aws",
    "docker",
    "react",
    "typescript",
    "node",
    "tensorflow",
    "pytorch",
    "pandas",
    "numpy",
    "c++",
    "c#",
    "html",
    "css",
    "kubernetes",
    "gcp",
    "azure",
    "leadership",
    "management",
    "product",
]

EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{6,}\d)")
DEGREE_KEYWORDS = ["bachelor", "master", "m.sc", "msc", "mba", "phd", "b.s.", "bsc", "bs", "ba"]


def parse_resume_text(text: str) -> Dict[str, object]:
    """Lightweight resume canonicalizer.

    Returns a dict with keys: name, emails, phones, skills, education, summary
    """
    if not text:
        return {"name": None, "emails": [], "phones": [], "skills": [], "education": [], "summary": ""}

    # Normalize
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    full_text = "\n".join(lines)

    # Emails
    emails = EMAIL_RE.findall(full_text)

    # Phones
    phones = PHONE_RE.findall(full_text)
    # De-duplicate and normalize phones
    phones = list(dict.fromkeys([re.sub(r"\s+", " ", p).strip() for p in phones]))

    # Heuristic name: first line if it looks like a name (contains letters and at least one space and capitalization)
    name = None
    if lines:
        candidate = lines[0]
        if len(candidate.split()) <= 4 and any(c.isalpha() for c in candidate) and candidate == candidate.title():
            name = candidate
        else:
            # try second line
            if len(lines) > 1:
                candidate = lines[1]
                if len(candidate.split()) <= 4 and candidate == candidate.title():
                    name = candidate

    # Skills detection
    lowered = full_text.lower()
    found_skills = []
    for skill in SKILL_KEYWORDS:
        if re.search(rf"\b{re.escape(skill)}\b", lowered):
            found_skills.append(skill)

    # Education detection
    education = []
    for deg in DEGREE_KEYWORDS:
        if deg in lowered:
            education.append(deg)

    # Summary: attempt to extract Experience section or first 2-4 lines after name
    summary = ""
    exp_idx = None
    for i, ln in enumerate(lines):
        if re.search(r"experience|professional experience|work experience", ln, re.I):
            exp_idx = i
            break
    if exp_idx is not None:
        # take next 3 lines as summary
        summary = " ".join(lines[exp_idx + 1 : exp_idx + 4])
    else:
        summary = " ".join(lines[1:4]) if len(lines) > 1 else lines[0]

    return {
        "name": name,
        "emails": list(dict.fromkeys(emails)),
        "phones": phones,
        "skills": found_skills,
        "education": education,
        "summary": summary,
    }
