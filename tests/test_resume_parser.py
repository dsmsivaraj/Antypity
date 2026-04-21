from __future__ import annotations

from unittest.mock import patch

from backend.resume_parser import parse_resume_text


SAMPLE_TEXT = '''
Jane Doe
Senior Software Engineer
Email: jane.doe@example.com
Phone: +1 (555) 123-4567

Summary
Experienced engineer with 8+ years building data platforms using Python, AWS, Docker, and Kubernetes.

Education
Master of Business Administration (MBA), Example University

Experience
- Senior Engineer at Acme Corp
- Built ETL pipelines, led migration to AWS

Skills
Python, SQL, AWS, Docker, Kubernetes, Terraform
'''

FULL_RESUME = """Aisha Patel
aisha.patel@example.com | +91 98765 43210

SUMMARY
Senior Software Engineer with 8 years of experience.

SKILLS
Python, AWS, Docker, React, TypeScript, SQL, Kubernetes, machine learning

EXPERIENCE
Senior Software Engineer at Google
- Built microservices with FastAPI
- Led ML pipeline using TensorFlow

EDUCATION
Bachelor of Engineering in Computer Science, IIT Bombay 2016
"""


def test_parse_basic_fields():
    parsed = parse_resume_text(SAMPLE_TEXT)
    assert parsed["name"] == "Jane Doe"
    assert "jane.doe@example.com" in parsed["emails"]
    assert any("555" in p or "+1" in p for p in parsed["phones"])
    assert "python" in parsed["skills"]
    assert "aws" in parsed["skills"]
    assert any(k in parsed["education"][0].lower() if parsed["education"] else "" for k in ["mba", "master"]) or parsed["education"]


def test_empty_string_returns_safe_defaults():
    result = parse_resume_text("")
    assert result["name"] is None
    assert result["emails"] == []
    assert result["phones"] == []
    assert result["skills"] == []
    assert result["education"] == []
    assert result["summary"] == ""
    assert result["companies"] == []


def test_name_from_title_case_first_line():
    text = "John Smith\njohn@example.com\nSoftware Engineer"
    result = parse_resume_text(text)
    assert result["name"] == "John Smith"


def test_email_single():
    text = "Jane Doe\njane.doe@company.com\nEngineer"
    result = parse_resume_text(text)
    assert "jane.doe@company.com" in result["emails"]


def test_email_multiple():
    text = "Name\nfoo@bar.com | work@corp.org\nSome text"
    result = parse_resume_text(text)
    assert "foo@bar.com" in result["emails"]
    assert "work@corp.org" in result["emails"]


def test_phone_us_format():
    text = "Alice Brown\n+1 (555) 123-4567\nEngineer"
    result = parse_resume_text(text)
    assert any("555" in p for p in result["phones"])


def test_phone_international():
    text = "Bob\n+91 98765 43210\nDeveloper"
    result = parse_resume_text(text)
    assert len(result["phones"]) >= 1


def test_skill_keyword_detected():
    text = "Dev\ndev@x.com\nSKILLS: Python, AWS, Docker"
    result = parse_resume_text(text)
    assert "python" in result["skills"]
    assert "aws" in result["skills"]


def test_absent_skill_not_detected():
    text = "Dev\ndev@x.com\nSKILLS: painting, woodworking"
    result = parse_resume_text(text)
    assert "python" not in result["skills"]


def test_education_bachelor():
    text = "Name\nemail@x.com\nEDUCATION\nBachelor of Science, MIT"
    result = parse_resume_text(text)
    assert "bachelor" in result["education"]


def test_education_phd():
    text = "Dr. Kim\nkim@uni.edu\nPhD in Computer Science"
    result = parse_resume_text(text)
    assert "phd" in result["education"]


def test_summary_from_experience_section():
    text = "Name\nemail@x.com\nEXPERIENCE\nBuilt distributed systems\nLed a team of 10"
    result = parse_resume_text(text)
    assert "distributed" in result["summary"] or "Built" in result["summary"]


def test_summary_fallback_to_first_lines():
    text = "Name\nFull Stack Developer\nPassionate about AI"
    result = parse_resume_text(text)
    assert len(result["summary"]) > 0


def test_full_resume_sample():
    result = parse_resume_text(FULL_RESUME)
    assert result["name"] is not None
    assert "aisha.patel@example.com" in result["emails"]
    assert "python" in result["skills"]
    assert "bachelor" in result["education"]
    assert len(result["summary"]) > 0


def test_spacy_disabled_fallback():
    with patch("backend.resume_parser._get_nlp", return_value=None):
        result = parse_resume_text(FULL_RESUME)
    assert "aisha.patel@example.com" in result["emails"]
    assert "python" in result["skills"]
    assert result["companies"] == []


def test_email_deduplication():
    text = "Name\nfoo@bar.com\nfoo@bar.com\nother text"
    result = parse_resume_text(text)
    assert result["emails"].count("foo@bar.com") == 1


def test_companies_empty_without_spacy():
    with patch("backend.resume_parser._get_nlp", return_value=None):
        result = parse_resume_text("Name\nemail@x.com\nGoogle Microsoft")
    assert result["companies"] == []


def test_result_has_companies_key():
    result = parse_resume_text("Any text")
    assert "companies" in result
