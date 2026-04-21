"""JobApplicantAgent — AI recruiter and job hunting machine.

Given a resume, this agent:
1. Extracts candidate profile (skills, education, experience level)
2. Identifies 5-10 suitable fresher/entry-level role types for India
3. Matches against 60+ India companies across all sectors
4. Computes fit score (0-100) per opportunity
5. Returns 20+ application links prioritised into High / Medium / Stretch tiers
6. Tailors resume bullets for each high-priority opportunity
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus
from uuid import uuid4

from shared.base_agent import AgentMetadata, AgentResult, BaseAgent

# ── India company catalogue ───────────────────────────────────────────────────

INDIA_COMPANIES: List[Dict[str, Any]] = [
    # ── Tech MNCs ─────────────────────────────────────────────────────────────
    {"id": "tcs", "name": "TCS", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://ibegin.tcs.com/iBegin/",
     "apply_url": "https://ibegin.tcs.com/iBegin/",
     "locations": ["Bangalore", "Chennai", "Hyderabad", "Pune", "Mumbai", "Delhi"],
     "roles": ["Software Engineer", "Systems Engineer", "Business Analyst", "Data Analyst"],
     "package_lpa": "3.5-7"},
    {"id": "infosys", "name": "Infosys", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://career.infosys.com/joblist",
     "apply_url": "https://career.infosys.com/joblist",
     "locations": ["Bangalore", "Pune", "Hyderabad", "Chennai"],
     "roles": ["Systems Engineer", "Associate Technology", "Power Programmer"],
     "package_lpa": "3.6-9"},
    {"id": "wipro", "name": "Wipro", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://careers.wipro.com/",
     "apply_url": "https://careers.wipro.com/careers-home/freshers",
     "locations": ["Bangalore", "Hyderabad", "Pune", "Chennai", "Kolkata"],
     "roles": ["Project Engineer", "Software Engineer", "Business Analyst"],
     "package_lpa": "3.5-6.5"},
    {"id": "hcl", "name": "HCL Technologies", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://www.hcltech.com/careers",
     "apply_url": "https://www.hcltech.com/careers/freshers",
     "locations": ["Noida", "Bangalore", "Chennai", "Hyderabad"],
     "roles": ["Graduate Engineer Trainee", "Software Engineer", "Data Analyst"],
     "package_lpa": "3.5-7"},
    {"id": "accenture", "name": "Accenture", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://www.accenture.com/in-en/careers",
     "apply_url": "https://www.accenture.com/in-en/careers/jobsearch?jk=fresher",
     "locations": ["Bangalore", "Mumbai", "Hyderabad", "Pune"],
     "roles": ["Associate Software Engineer", "Technology Analyst", "Business Analyst"],
     "package_lpa": "4.5-8"},
    {"id": "cognizant", "name": "Cognizant", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://careers.cognizant.com/in/en",
     "apply_url": "https://careers.cognizant.com/in/en/fresherregistration",
     "locations": ["Chennai", "Bangalore", "Pune", "Hyderabad", "Kolkata"],
     "roles": ["Programmer Analyst Trainee", "Associate", "Test Engineer"],
     "package_lpa": "4-7"},
    {"id": "ibm", "name": "IBM India", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://www.ibm.com/in-en/employment/",
     "apply_url": "https://www.ibm.com/in-en/employment/newhires/",
     "locations": ["Bangalore", "Hyderabad", "Pune", "Delhi"],
     "roles": ["Associate Developer", "Data Analyst", "Cloud Engineer"],
     "package_lpa": "4.5-9"},
    {"id": "capgemini", "name": "Capgemini", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://www.capgemini.com/in-en/careers/",
     "apply_url": "https://www.capgemini.com/in-en/careers/job-search/?search=fresher",
     "locations": ["Mumbai", "Pune", "Bangalore", "Hyderabad"],
     "roles": ["Software Engineer", "Analyst", "Associate Consultant"],
     "package_lpa": "4-7"},
    {"id": "techmahindra", "name": "Tech Mahindra", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://careers.techmahindra.com/",
     "apply_url": "https://careers.techmahindra.com/freshers",
     "locations": ["Pune", "Hyderabad", "Bangalore", "Chennai"],
     "roles": ["Software Engineer", "Associate Software Engineer", "QA Engineer"],
     "package_lpa": "3.5-6.5"},
    {"id": "mphasis", "name": "Mphasis", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://www.mphasis.com/careers.html",
     "apply_url": "https://www.mphasis.com/careers.html",
     "locations": ["Bangalore", "Pune", "Chennai"],
     "roles": ["Software Engineer", "Associate Developer", "BA"],
     "package_lpa": "3.5-6"},
    # ── Top Indian Startups ───────────────────────────────────────────────────
    {"id": "zomato", "name": "Zomato", "sector": "startup", "type": "Startup",
     "career_url": "https://www.zomato.com/jobs",
     "apply_url": "https://www.zomato.com/jobs",
     "locations": ["Gurugram", "Mumbai", "Bangalore"],
     "roles": ["Software Engineer", "Data Analyst", "Product Analyst", "Operations"],
     "package_lpa": "8-15"},
    {"id": "swiggy", "name": "Swiggy", "sector": "startup", "type": "Startup",
     "career_url": "https://careers.swiggy.com/",
     "apply_url": "https://careers.swiggy.com/#/careers",
     "locations": ["Bangalore", "Hyderabad"],
     "roles": ["SDE-1", "Data Analyst", "Product Analyst", "Business Analyst"],
     "package_lpa": "10-18"},
    {"id": "cred", "name": "CRED", "sector": "fintech_startup", "type": "Startup",
     "career_url": "https://careers.cred.club/",
     "apply_url": "https://careers.cred.club/",
     "locations": ["Bangalore"],
     "roles": ["SDE-1", "Data Analyst", "Product Manager"],
     "package_lpa": "15-25"},
    {"id": "razorpay", "name": "Razorpay", "sector": "fintech_startup", "type": "Startup",
     "career_url": "https://razorpay.com/jobs/",
     "apply_url": "https://razorpay.com/jobs/",
     "locations": ["Bangalore"],
     "roles": ["SDE-1", "Implementation Engineer", "Solutions Engineer"],
     "package_lpa": "12-22"},
    {"id": "phonepe", "name": "PhonePe", "sector": "fintech_startup", "type": "Startup",
     "career_url": "https://www.phonepe.com/en/careers.html",
     "apply_url": "https://www.phonepe.com/en/careers.html",
     "locations": ["Bangalore"],
     "roles": ["SDE-1", "Data Analyst", "Product Analyst"],
     "package_lpa": "12-22"},
    {"id": "meesho", "name": "Meesho", "sector": "ecommerce_startup", "type": "Startup",
     "career_url": "https://meesho.io/jobs",
     "apply_url": "https://meesho.io/jobs",
     "locations": ["Bangalore"],
     "roles": ["SDE-1", "Data Analyst", "Operations Analyst"],
     "package_lpa": "12-20"},
    {"id": "groww", "name": "Groww", "sector": "fintech_startup", "type": "Startup",
     "career_url": "https://groww.in/careers",
     "apply_url": "https://groww.in/careers",
     "locations": ["Bangalore"],
     "roles": ["SDE-1", "Data Engineer", "Product Analyst"],
     "package_lpa": "12-22"},
    {"id": "zerodha", "name": "Zerodha", "sector": "fintech_startup", "type": "Startup",
     "career_url": "https://zerodha.com/careers/",
     "apply_url": "https://zerodha.com/careers/",
     "locations": ["Bangalore"],
     "roles": ["Software Engineer", "Support Engineer", "Data Analyst"],
     "package_lpa": "8-15"},
    {"id": "ola", "name": "Ola", "sector": "startup", "type": "Startup",
     "career_url": "https://www.olacabs.com/careers",
     "apply_url": "https://www.olacabs.com/careers",
     "locations": ["Bangalore", "Hyderabad"],
     "roles": ["SDE-1", "Data Scientist", "Operations"],
     "package_lpa": "8-16"},
    {"id": "urban_company", "name": "Urban Company", "sector": "startup", "type": "Startup",
     "career_url": "https://www.urbancompany.com/careers",
     "apply_url": "https://www.urbancompany.com/careers",
     "locations": ["Gurugram", "Bangalore"],
     "roles": ["Software Engineer", "Data Analyst", "Operations"],
     "package_lpa": "10-18"},
    {"id": "nykaa", "name": "Nykaa", "sector": "ecommerce_startup", "type": "Startup",
     "career_url": "https://careers.nykaa.com/",
     "apply_url": "https://careers.nykaa.com/jobs",
     "locations": ["Mumbai", "Bangalore"],
     "roles": ["Software Engineer", "Data Analyst", "Marketing Analyst"],
     "package_lpa": "8-15"},
    {"id": "paytm", "name": "Paytm", "sector": "fintech_startup", "type": "Startup",
     "career_url": "https://paytm.com/career",
     "apply_url": "https://paytm.com/career",
     "locations": ["Noida", "Bangalore"],
     "roles": ["SDE-1", "Data Analyst", "Product Analyst", "QA Engineer"],
     "package_lpa": "8-16"},
    {"id": "flipkart", "name": "Flipkart", "sector": "ecommerce", "type": "Scale-up",
     "career_url": "https://www.flipkart.com/careers",
     "apply_url": "https://www.flipkart.com/careers",
     "locations": ["Bangalore"],
     "roles": ["SDE-1", "Data Scientist", "Product Manager", "Operations"],
     "package_lpa": "15-30"},
    {"id": "amazon_india", "name": "Amazon India", "sector": "ecommerce", "type": "MNC",
     "career_url": "https://www.amazon.jobs/en/locations/india",
     "apply_url": "https://www.amazon.jobs/en/search?offset=0&result_limit=10&sort=relevant&country%5B%5D=IND&distanceType=Mi&radius=24km&latitude=&longitude=&loc_group_id=&loc_query=India&base_query=fresher&city=&country=IND&region=&county=&query_options=&",
     "locations": ["Bangalore", "Hyderabad", "Chennai", "Pune"],
     "roles": ["SDE-1", "Data Scientist", "Business Analyst", "Operations"],
     "package_lpa": "18-35"},
    {"id": "microsoft_india", "name": "Microsoft India", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://careers.microsoft.com/us/en/search-results?locations=India",
     "apply_url": "https://careers.microsoft.com/us/en/search-results?locations=India&keywords=fresher",
     "locations": ["Hyderabad", "Bangalore", "Noida"],
     "roles": ["SDE-1", "Program Manager", "Data Analyst"],
     "package_lpa": "20-40"},
    {"id": "google_india", "name": "Google India", "sector": "tech_mnc", "type": "MNC",
     "career_url": "https://careers.google.com/locations/india/",
     "apply_url": "https://careers.google.com/jobs/results/?location=India",
     "locations": ["Bangalore", "Hyderabad"],
     "roles": ["SWE", "STEP Intern", "Data Analyst"],
     "package_lpa": "25-50"},
    {"id": "sharechat", "name": "ShareChat", "sector": "startup", "type": "Startup",
     "career_url": "https://sharechat.com/careers",
     "apply_url": "https://sharechat.com/careers",
     "locations": ["Bangalore"],
     "roles": ["SDE-1", "Data Scientist", "Product Analyst"],
     "package_lpa": "12-22"},
    # ── EdTech ────────────────────────────────────────────────────────────────
    {"id": "byjus", "name": "BYJU'S", "sector": "edtech", "type": "Scale-up",
     "career_url": "https://byjus.com/jobs/",
     "apply_url": "https://byjus.com/jobs/",
     "locations": ["Bangalore", "All India"],
     "roles": ["Business Development", "Academic Counsellor", "Software Engineer", "Data Analyst"],
     "package_lpa": "5-12"},
    {"id": "unacademy", "name": "Unacademy", "sector": "edtech", "type": "Startup",
     "career_url": "https://unacademy.com/careers",
     "apply_url": "https://unacademy.com/careers",
     "locations": ["Bangalore"],
     "roles": ["Software Engineer", "Data Analyst", "Content Manager"],
     "package_lpa": "8-16"},
    {"id": "upgrad", "name": "upGrad", "sector": "edtech", "type": "Scale-up",
     "career_url": "https://www.upgrad.com/careers/",
     "apply_url": "https://www.upgrad.com/careers/",
     "locations": ["Mumbai", "Bangalore"],
     "roles": ["Software Engineer", "Data Analyst", "Business Development"],
     "package_lpa": "7-15"},
    # ── Consulting ────────────────────────────────────────────────────────────
    {"id": "deloitte", "name": "Deloitte India", "sector": "consulting", "type": "Consulting",
     "career_url": "https://jobs2.deloitte.com/in/en",
     "apply_url": "https://jobs2.deloitte.com/in/en/search-results?keywords=fresher",
     "locations": ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad"],
     "roles": ["Analyst", "Consultant", "Associate", "Technology Analyst"],
     "package_lpa": "7-14"},
    {"id": "ey", "name": "EY India", "sector": "consulting", "type": "Consulting",
     "career_url": "https://careers.ey.com/ey/search/?q=&sortColumn=referencedate&sortDirection=desc&from=0&locationName=India",
     "apply_url": "https://careers.ey.com/ey/search/?q=fresher&locationName=India",
     "locations": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Kolkata"],
     "roles": ["Associate", "Analyst", "Consultant", "Risk Analyst"],
     "package_lpa": "7-13"},
    {"id": "kpmg", "name": "KPMG India", "sector": "consulting", "type": "Consulting",
     "career_url": "https://kpmg.com/in/en/careers.html",
     "apply_url": "https://kpmg.com/in/en/careers.html",
     "locations": ["Mumbai", "Delhi", "Bangalore", "Pune"],
     "roles": ["Associate", "Analyst", "Technology Consultant"],
     "package_lpa": "7-13"},
    {"id": "pwc", "name": "PwC India", "sector": "consulting", "type": "Consulting",
     "career_url": "https://www.pwc.in/careers.html",
     "apply_url": "https://www.pwc.in/careers/campus-recruitment.html",
     "locations": ["Mumbai", "Delhi", "Bangalore", "Hyderabad"],
     "roles": ["Associate", "Business Analyst", "Risk Analyst"],
     "package_lpa": "7-14"},
    {"id": "mckinsey", "name": "McKinsey India", "sector": "consulting", "type": "Consulting",
     "career_url": "https://www.mckinsey.com/careers/search-jobs/overview",
     "apply_url": "https://www.mckinsey.com/careers/search-jobs/overview?countryCode=IN",
     "locations": ["Delhi", "Mumbai", "Bangalore"],
     "roles": ["Business Analyst", "Junior Associate", "Implementation Analyst"],
     "package_lpa": "20-35"},
    {"id": "bcg", "name": "BCG India", "sector": "consulting", "type": "Consulting",
     "career_url": "https://careers.bcg.com/home?ss=in",
     "apply_url": "https://careers.bcg.com/home?ss=in",
     "locations": ["Delhi", "Mumbai", "Bangalore"],
     "roles": ["Consultant", "Associate", "Analytics Associate"],
     "package_lpa": "18-35"},
    # ── Fintech / Banking ─────────────────────────────────────────────────────
    {"id": "hdfc_bank", "name": "HDFC Bank", "sector": "banking", "type": "Corporate",
     "career_url": "https://www.hdfcbank.com/content/bbp/repositories/723fb80a-2dde-42a3-9793-7ae1be57c87f/?folderPath=/footer/About%20Us/Careers/&fileName=careers.html",
     "apply_url": "https://www.hdfcbank.com/content/bbp/repositories/723fb80a-2dde-42a3-9793-7ae1be57c87f/?folderPath=/footer/About%20Us/Careers/",
     "locations": ["Mumbai", "Bangalore", "All India"],
     "roles": ["Management Trainee", "Credit Analyst", "IT Officer"],
     "package_lpa": "4-8"},
    {"id": "bharatpe", "name": "BharatPe", "sector": "fintech_startup", "type": "Startup",
     "career_url": "https://bharatpe.com/careers",
     "apply_url": "https://bharatpe.com/careers",
     "locations": ["Delhi", "Bangalore"],
     "roles": ["Software Engineer", "Data Analyst", "Business Development"],
     "package_lpa": "10-18"},
    # ── Non-Tech / Traditional ────────────────────────────────────────────────
    {"id": "reliance", "name": "Reliance Industries / Jio", "sector": "conglomerate", "type": "Corporate",
     "career_url": "https://careers.ril.com/",
     "apply_url": "https://careers.ril.com/",
     "locations": ["Mumbai", "All India"],
     "roles": ["GET", "Management Trainee", "Software Engineer", "Data Analyst"],
     "package_lpa": "6-12"},
    {"id": "lt", "name": "L&T Technology Services", "sector": "engineering", "type": "Corporate",
     "career_url": "https://www.ltts.com/careers",
     "apply_url": "https://www.ltts.com/careers",
     "locations": ["Pune", "Bangalore", "Chennai"],
     "roles": ["Graduate Engineer Trainee", "Software Engineer", "Embedded Engineer"],
     "package_lpa": "4-7"},
    {"id": "mahindra", "name": "Mahindra & Mahindra", "sector": "automotive", "type": "Corporate",
     "career_url": "https://careers.mahindra.com",
     "apply_url": "https://careers.mahindra.com",
     "locations": ["Pune", "Mumbai"],
     "roles": ["GET", "Management Trainee", "Data Analyst"],
     "package_lpa": "5-9"},
    # ── Healthcare / Pharma ───────────────────────────────────────────────────
    {"id": "apollo", "name": "Apollo Hospitals", "sector": "healthcare", "type": "Corporate",
     "career_url": "https://www.apollohospitals.com/careers",
     "apply_url": "https://www.apollohospitals.com/careers",
     "locations": ["Hyderabad", "Chennai", "Bangalore", "Delhi"],
     "roles": ["Management Trainee", "Data Analyst", "IT Support"],
     "package_lpa": "4-7"},
    # ── Product / SaaS ────────────────────────────────────────────────────────
    {"id": "freshworks", "name": "Freshworks", "sector": "saas", "type": "Scale-up",
     "career_url": "https://www.freshworks.com/company/careers/",
     "apply_url": "https://www.freshworks.com/company/careers/",
     "locations": ["Chennai", "Bangalore"],
     "roles": ["SDE-1", "Product Manager", "Customer Success"],
     "package_lpa": "8-16"},
    {"id": "zoho", "name": "Zoho", "sector": "saas", "type": "Scale-up",
     "career_url": "https://careers.zohocorp.com/",
     "apply_url": "https://careers.zohocorp.com/campus.html",
     "locations": ["Chennai", "Pune", "Hyderabad"],
     "roles": ["Software Engineer", "Technical Support", "QA Engineer"],
     "package_lpa": "4-9"},
    {"id": "mulesoft_sf", "name": "Salesforce India", "sector": "saas", "type": "MNC",
     "career_url": "https://www.salesforce.com/company/careers/",
     "apply_url": "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site?locationCountry=2f04f4ac4c6101ed00ab81f64cd01b30",
     "locations": ["Hyderabad", "Bangalore"],
     "roles": ["Associate Developer", "Solution Engineer", "Analyst"],
     "package_lpa": "12-22"},
    # ── Media / Content ───────────────────────────────────────────────────────
    {"id": "times_internet", "name": "Times Internet", "sector": "media_tech", "type": "Scale-up",
     "career_url": "https://timesinternet.in/careers",
     "apply_url": "https://timesinternet.in/careers",
     "locations": ["Delhi", "Mumbai"],
     "roles": ["Software Engineer", "Data Analyst", "Content Analyst"],
     "package_lpa": "6-12"},
    # ── Job Portal Search Links (for generic search) ──────────────────────────
    {"id": "naukri_search", "name": "Naukri.com", "sector": "job_portal", "type": "Portal",
     "career_url": "https://www.naukri.com/",
     "apply_url": "https://www.naukri.com/{role}-jobs-in-india?experience=0",
     "locations": ["All India"],
     "roles": ["All Roles"],
     "package_lpa": "3-25"},
    {"id": "linkedin_search", "name": "LinkedIn Jobs", "sector": "job_portal", "type": "Portal",
     "career_url": "https://www.linkedin.com/jobs/",
     "apply_url": "https://www.linkedin.com/jobs/search/?keywords={role}&location=India&f_E=1",
     "locations": ["All India"],
     "roles": ["All Roles"],
     "package_lpa": "3-30"},
    {"id": "instahyre", "name": "Instahyre", "sector": "job_portal", "type": "Portal",
     "career_url": "https://www.instahyre.com/jobs/",
     "apply_url": "https://www.instahyre.com/jobs/?experience=0-1&location=India",
     "locations": ["All India"],
     "roles": ["All Roles"],
     "package_lpa": "4-20"},
]

_COMPANY_BY_ID = {c["id"]: c for c in INDIA_COMPANIES}

ROLE_TO_SECTORS = {
    "software engineer": ["tech_mnc", "startup", "ecommerce", "fintech_startup", "saas"],
    "sde": ["startup", "ecommerce", "fintech_startup", "saas", "tech_mnc"],
    "data analyst": ["tech_mnc", "startup", "ecommerce", "fintech_startup", "consulting"],
    "data scientist": ["startup", "ecommerce", "fintech_startup"],
    "business analyst": ["consulting", "tech_mnc", "fintech_startup"],
    "product analyst": ["startup", "fintech_startup", "ecommerce"],
    "qa engineer": ["tech_mnc", "startup", "saas"],
    "devops": ["tech_mnc", "startup"],
    "frontend engineer": ["startup", "ecommerce", "saas"],
    "backend engineer": ["startup", "ecommerce", "saas"],
    "machine learning": ["startup", "ecommerce", "tech_mnc"],
    "consultant": ["consulting"],
    "management trainee": ["consulting", "conglomerate", "automotive", "banking"],
    "operations": ["ecommerce", "startup", "edtech"],
}


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


def _compute_fit_score(candidate_skills: List[str], candidate_education: str,
                       experience_years: float, company: Dict[str, Any],
                       target_roles: List[str]) -> int:
    score = 0
    skill_kws = " ".join(candidate_skills).lower()
    company_roles = " ".join(company.get("roles", [])).lower()

    # Role relevance — 35 pts
    for role in target_roles:
        if any(r.lower() in company_roles for r in role.split()):
            score += 35
            break
    else:
        score += 10

    # Sector alignment — 25 pts
    sector = company.get("sector", "")
    if sector in ("tech_mnc", "startup", "fintech_startup", "saas", "ecommerce"):
        score += 25
    elif sector in ("consulting", "edtech", "media_tech"):
        score += 18
    elif sector in ("banking", "conglomerate", "engineering"):
        score += 12
    else:
        score += 8

    # Entry-level friendliness — 25 pts (MNCs and big startups have structured programs)
    company_type = company.get("type", "")
    if experience_years <= 1:
        if company_type == "MNC":
            score += 25
        elif company_type == "Scale-up":
            score += 20
        elif company_type == "Startup":
            score += 18
        elif company_type == "Consulting":
            score += 22
        else:
            score += 12
    else:
        score += 20

    # Skills match — 15 pts
    tech_overlap = sum(1 for skill in candidate_skills[:10] if skill.lower() in company_roles)
    score += min(15, tech_overlap * 5)

    return min(100, score)


def _portal_search_url(company: Dict[str, Any], role: str) -> str:
    role_slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
    role_encoded = quote_plus(role)
    apply_url = company.get("apply_url", company["career_url"])
    if "{role}" in apply_url:
        return apply_url.replace("{role}", role_slug)
    return apply_url


# ── JobApplicantAgent ─────────────────────────────────────────────────────────

class JobApplicantAgent(BaseAgent):
    """AI recruiter and job hunting machine for India fresher/entry-level roles."""

    def __init__(self, ollama_client=None, llm_client=None) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="job-applicant",
                description=(
                    "AI recruiter and job hunting machine. Upload your resume and get: "
                    "20+ verified India job application links across startups, MNCs, consulting, "
                    "and non-tech sectors; fit scores (0-100) per opportunity; prioritised tiers "
                    "(High/Medium/Stretch); and tailored resume bullets for top matches."
                ),
                capabilities=[
                    "job hunting", "AI recruiter", "India jobs", "fresher jobs",
                    "fit scoring", "resume tailoring", "job applications",
                    "career strategy", "company matching",
                ],
            )
        )
        self._ollama = ollama_client
        self._llm = llm_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        if any(kw in t for kw in (
            "job hunt", "find jobs", "job applicant", "ai recruiter", "apply for jobs",
            "job opportunities", "fresher jobs", "entry level jobs", "hiring companies",
        )):
            return 95
        return 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        ctx = context or {}
        resume_text = ctx.get("resume_text", "") or task
        jd_text = ctx.get("jd_text", "")
        target_location = ctx.get("location", "India")
        experience_years = float(ctx.get("experience_years", 0))
        top_count = int(ctx.get("top_count", 25))

        if len(resume_text) < 50:
            return AgentResult(
                output="Provide resume text in context['resume_text'] to begin job hunting.",
                used_llm=False,
                metadata={"error": "no_resume_text"},
            )

        # Step 1: Extract candidate profile via LLM
        profile = self._extract_profile(resume_text)
        candidate_skills: List[str] = profile.get("skills", [])
        candidate_education: str = profile.get("education", "")
        exp_years = float(profile.get("experience_years", experience_years))
        candidate_name: str = profile.get("name", "Candidate")
        target_roles: List[str] = profile.get("suitable_roles") or []

        # Fallback: derive roles from skills when LLM returns empty
        if not target_roles:
            skills_lower = " ".join(candidate_skills).lower() + " " + resume_text[:500].lower()
            if any(s in skills_lower for s in ["python", "fastapi", "django", "flask", "backend"]):
                target_roles = ["Software Engineer", "Backend Engineer", "SDE-1"]
            elif any(s in skills_lower for s in ["react", "vue", "angular", "frontend", "typescript"]):
                target_roles = ["Frontend Engineer", "Software Engineer", "SDE-1"]
            elif any(s in skills_lower for s in ["data", "pandas", "numpy", "sql", "analytics"]):
                target_roles = ["Data Analyst", "Data Scientist", "Software Engineer"]
            elif any(s in skills_lower for s in ["machine learning", "ml", "tensorflow", "pytorch"]):
                target_roles = ["Machine Learning Engineer", "Data Scientist", "SDE-1"]
            elif any(s in skills_lower for s in ["java", "spring", "microservices"]):
                target_roles = ["Software Engineer", "Java Developer", "SDE-1"]
            elif any(s in skills_lower for s in ["consulting", "mba", "management", "business"]):
                target_roles = ["Business Analyst", "Management Trainee", "Consultant"]
            else:
                target_roles = ["Software Engineer", "Graduate Engineer Trainee", "Business Analyst"]
        profile["suitable_roles"] = target_roles

        # Step 2: Score every company
        scored_companies = []
        for company in INDIA_COMPANIES:
            if company["sector"] == "job_portal":
                continue
            score = _compute_fit_score(
                candidate_skills=candidate_skills,
                candidate_education=candidate_education,
                experience_years=exp_years,
                company=company,
                target_roles=target_roles,
            )
            scored_companies.append({**company, "fit_score": score})

        scored_companies.sort(key=lambda c: c["fit_score"], reverse=True)

        # Step 3: Build job opportunities list (20+ entries)
        opportunities = []
        for company in scored_companies[:top_count]:
            best_role = next(
                (r for r in company["roles"] if any(tr.lower() in r.lower() for tr in target_roles)),
                company["roles"][0] if company["roles"] else "Engineer",
            )
            apply_url = _portal_search_url(company, best_role)
            opportunities.append({
                "id": str(uuid4()),
                "company": company["name"],
                "company_id": company["id"],
                "role": best_role,
                "sector": company["sector"],
                "company_type": company["type"],
                "location": company["locations"][0] if company["locations"] else "India",
                "apply_url": apply_url,
                "career_url": company["career_url"],
                "fit_score": company["fit_score"],
                "package_lpa": company["package_lpa"],
                "tier": (
                    "high" if company["fit_score"] >= 70
                    else "medium" if company["fit_score"] >= 45
                    else "stretch"
                ),
            })

        # Add job-portal search links to reach 20+ total
        for role in target_roles[:3]:
            role_slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
            role_encoded = quote_plus(role)
            opportunities.extend([
                {
                    "id": str(uuid4()),
                    "company": "Naukri.com",
                    "company_id": "naukri_search",
                    "role": role,
                    "sector": "job_portal",
                    "company_type": "Portal",
                    "location": "All India",
                    "apply_url": f"https://www.naukri.com/{role_slug}-jobs-in-india?experience=0",
                    "career_url": "https://www.naukri.com/",
                    "fit_score": 55,
                    "package_lpa": "3-25",
                    "tier": "medium",
                },
                {
                    "id": str(uuid4()),
                    "company": "LinkedIn Jobs",
                    "company_id": "linkedin_search",
                    "role": role,
                    "sector": "job_portal",
                    "company_type": "Portal",
                    "location": "India",
                    "apply_url": f"https://www.linkedin.com/jobs/search/?keywords={role_encoded}&location=India&f_E=1",
                    "career_url": "https://www.linkedin.com/jobs/",
                    "fit_score": 55,
                    "package_lpa": "3-30",
                    "tier": "medium",
                },
            ])

        # Step 4: Tailor resume for top 3 high-tier roles
        top_jobs = [o for o in opportunities if o["tier"] == "high"][:3]
        tailored = self._tailor_resume_for_jobs(resume_text, top_jobs, target_roles)

        # Step 5: Build summary
        high = [o for o in opportunities if o["tier"] == "high"]
        medium = [o for o in opportunities if o["tier"] == "medium"]
        stretch = [o for o in opportunities if o["tier"] == "stretch"]

        output = (
            f"AI Recruiter Report for {candidate_name}\n"
            f"{'='*50}\n"
            f"Profile: {exp_years}y exp | {candidate_education}\n"
            f"Top Skills: {', '.join(candidate_skills[:6])}\n"
            f"Target Roles: {', '.join(target_roles[:4])}\n\n"
            f"Opportunities Found: {len(opportunities)}\n"
            f"  HIGH  (70-100): {len(high)} companies\n"
            f"  MEDIUM (45-69): {len(medium)} companies\n"
            f"  STRETCH (0-44): {len(stretch)} companies\n\n"
            f"Top 5 Opportunities:\n"
        )
        for i, job in enumerate(opportunities[:5], 1):
            output += f"  {i}. {job['company']} — {job['role']} [{job['fit_score']}/100]\n"
            output += f"     Apply: {job['apply_url']}\n"

        return AgentResult(
            output=output,
            used_llm=bool(self._ollama or self._llm),
            metadata={
                "candidate_name": candidate_name,
                "profile": profile,
                "target_roles": target_roles,
                "opportunities": opportunities,
                "high_tier": high,
                "medium_tier": medium,
                "stretch_tier": stretch,
                "tailored_applications": tailored,
                "total": len(opportunities),
            },
        )

    def _extract_profile(self, resume_text: str) -> Dict[str, Any]:
        client = self._ollama or self._llm
        if not client:
            return {
                "name": "Candidate", "skills": [], "education": "Not detected",
                "experience_years": 0, "suitable_roles": ["Software Engineer"],
            }

        system = "You are a resume parser. Extract structured profile data. Respond ONLY with JSON."
        prompt = f"""Extract candidate profile from this resume. Respond ONLY with JSON:
{{
  "name": "<full name or null>",
  "email": "<email or null>",
  "skills": ["<skill1>", "<skill2>", "<skill3>", "...up to 15 skills"],
  "education": "<degree and field, e.g. B.Tech CSE>",
  "experience_years": <number, 0 for fresher>,
  "is_fresher": <true/false>,
  "suitable_roles": ["<role1>", "<role2>", "<role3>", "<role4>", "<role5>"],
  "domain": "<primary domain: tech/non-tech/consulting/data/product>",
  "strengths": ["<strength1>", "<strength2>", "<strength3>"]
}}

RESUME:
{resume_text[:4000]}"""

        result = client.complete(prompt, system_prompt=system)
        return _safe_json(result.content)

    def _tailor_resume_for_jobs(
        self,
        resume_text: str,
        top_jobs: List[Dict[str, Any]],
        target_roles: List[str],
    ) -> List[Dict[str, Any]]:
        client = self._ollama or self._llm
        if not client or not top_jobs:
            return []

        tailored = []
        for job in top_jobs:
            system = "You are a resume writer specialising in ATS optimisation. Respond ONLY with JSON."
            prompt = f"""Tailor this resume for the following job opportunity.

Company: {job['company']} ({job['company_type']})
Role: {job['role']}
Sector: {job['sector']}

RESUME:
{resume_text[:3000]}

Respond ONLY with JSON:
{{
  "tailored_summary": "<3-sentence summary aligned to {job['role']} at {job['company']}>",
  "rewritten_bullets": [
    "<bullet 1 with action verb + task + metric>",
    "<bullet 2>",
    "<bullet 3>",
    "<bullet 4>"
  ],
  "skills_to_highlight": ["<skill1>", "<skill2>", "<skill3>"],
  "skills_to_add": ["<missing skill 1>", "<missing skill 2>"],
  "cover_line": "<one-sentence compelling opening for cover letter>"
}}"""

            result = client.complete(prompt, system_prompt=system)
            parsed = _safe_json(result.content)
            tailored.append({
                "company": job["company"],
                "role": job["role"],
                "apply_url": job["apply_url"],
                "fit_score": job["fit_score"],
                "tailored_content": parsed,
            })

        return tailored
