import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .job_searcher import JobSearcher
from .lead_qualifier import LeadQualifier
from .models import LeadSearchRequest, LeadSearchResponse
from .web_researcher import WebResearcher

app = FastAPI(
    title="Sales Lead Analyzer API",
    description=(
        "Recherchiert und qualifiziert B2B Sales Leads für den DACH-Markt. "
        "Durchsucht Unternehmenswebsites und Jobportale nach ERP-Nutzungs-Hinweisen "
        "und qualifiziert Leads mit Claude AI vor."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_researcher = WebResearcher()
_job_searcher = JobSearcher()
_qualifier = LeadQualifier()

_API_KEY = os.getenv("API_KEY", "")


def _check_api_key(x_api_key: Optional[str]) -> None:
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


async def _research_and_qualify(company, erp_system, criteria):
    homepage_info, job_info = await asyncio.gather(
        _researcher.scrape_homepage(company.website),
        _job_searcher.search_erp_jobs(company.name, erp_system),
    )
    return await _qualifier.qualify_lead(
        company=company,
        homepage_info=homepage_info,
        job_info=job_info,
        criteria=criteria,
    )


@app.post("/api/search-leads", response_model=LeadSearchResponse)
async def search_leads(
    request: LeadSearchRequest,
    x_api_key: Optional[str] = Header(default=None),
):
    """
    Sucht und qualifiziert Sales Leads basierend auf Branche, Region, ERP-System und Mitarbeiterzahl.

    Der Prozess:
    1. Unternehmenssuche via DuckDuckGo
    2. Homepage-Analyse (ERP-Hinweise, Kontaktdaten, Mitarbeiterzahl)
    3. Stellenanzeigen-Recherche auf Stepstone, Indeed, Monster, XING, LinkedIn
    4. Lead-Qualifizierung und Scoring mit Claude AI
    """
    _check_api_key(x_api_key)

    companies = await _researcher.find_companies(
        industry=request.industry,
        region=request.region.value,
        employee_size=request.employee_size.value,
        max_results=request.max_results + 5,
    )

    # Analyze top companies concurrently (max 10 at once to avoid rate limits)
    batch = companies[: min(request.max_results, 10)]
    tasks = [
        _research_and_qualify(company, request.erp_system.value, request)
        for company in batch
    ]
    leads = await asyncio.gather(*tasks)

    sorted_leads = sorted(leads, key=lambda l: l.lead_score, reverse=True)

    return LeadSearchResponse(
        leads=sorted_leads,
        total_found=len(sorted_leads),
        search_criteria={
            "industry": request.industry,
            "region": request.region.value,
            "erp_system": request.erp_system.value,
            "employee_size": request.employee_size.value,
        },
        search_timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Sales Lead Analyzer"}
