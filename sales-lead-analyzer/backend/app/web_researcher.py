import asyncio
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from .models import CompanyInfo, EmployeeSize

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}

_EMPLOYEE_SIZE_TERMS = {
    "unter_200": ["kleines Unternehmen", "KMU", "Mittelstand"],
    "200_500": ["mittelständisches Unternehmen", "Mittelstand", "KMU"],
    "500_1000": ["mittelgroßes Unternehmen", "Mittelstand"],
    "ueber_1000": ["Großunternehmen", "Konzern", "großes Unternehmen"],
}

_ERP_KEYWORDS = [
    "SAP", "Navision", "Microsoft Dynamics NAV", "Microsoft Dynamics",
    "Dynamics AX", "AX 2012", "Pro Alpha", "proALPHA",
    "Oracle ERP", "Oracle E-Business", "S/4HANA", "S4HANA",
    "ERP", "Warenwirtschaft", "Buchhaltungssoftware",
    "Business Central", "SAP R/3", "SAP ECC",
]

_EMPLOYEE_PATTERNS = [
    r"(\d[\d.]*)\s*Mitarbeiter",
    r"(\d[\d.]*)\s*Beschäftigte",
    r"(\d[\d.]*)\s*Angestellte",
    r"(\d[\d.]*)\s*employees",
    r"Team\s+von\s+(\d[\d.]*)",
    r"über\s+(\d[\d.]*)\s+Mitarbeiter",
    r"ca\.\s+(\d[\d.]*)\s+Mitarbeiter",
]

_TITLE_CLEANUP = [
    " - Homepage", " | Startseite", " - Startseite",
    " – Startseite", " | Homepage", " - Offizielle Website",
    " | Offizielle Website", " - Willkommen", " | Willkommen",
]


def _clean_title(title: str) -> str:
    for suffix in _TITLE_CLEANUP:
        if title.endswith(suffix):
            title = title[: -len(suffix)]
    return title.strip()[:120]


def _base_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


async def _ddg_text(query: str, max_results: int = 15, region: str = "de-de") -> List[Dict]:
    def _run():
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results, region=region))

    try:
        return await asyncio.to_thread(_run)
    except Exception:
        return []


class WebResearcher:
    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    async def find_companies(
        self,
        industry: str,
        region: str,
        employee_size: str,
        max_results: int = 20,
    ) -> List[CompanyInfo]:
        size_terms = _EMPLOYEE_SIZE_TERMS.get(employee_size, ["Unternehmen"])
        size_label = size_terms[0]

        region_term = "DACH Deutschland Österreich Schweiz" if region == "DACH" else region

        queries = [
            f"{industry} Unternehmen {region_term} {size_label}",
            f"{industry} Firma {region_term} Mittelstand",
            f"{industry} GmbH {region_term}",
        ]

        seen: set = set()
        companies: List[CompanyInfo] = []

        for query in queries:
            if len(companies) >= max_results:
                break
            results = await _ddg_text(query, max_results=15)
            for r in results:
                name = _clean_title(r.get("title", ""))
                url = _base_url(r.get("href", ""))
                if not name or url in seen:
                    continue
                seen.add(url)
                companies.append(
                    CompanyInfo(
                        name=name,
                        website=url or None,
                        description=r.get("body", "")[:400],
                    )
                )

        return companies[:max_results]

    async def scrape_homepage(self, url: Optional[str]) -> Dict:
        if not url:
            return {}

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=HEADERS,
            ) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return {"url": url, "error": f"HTTP {response.status_code}"}

                soup = BeautifulSoup(response.text, "lxml")

                # Remove nav/footer noise
                for tag in soup.select("nav, footer, script, style"):
                    tag.decompose()

                text = soup.get_text(separator=" ", strip=True)

                # ERP keyword scan
                found_erp = [kw for kw in _ERP_KEYWORDS if kw.lower() in text.lower()]

                # Employee count mentions
                employee_mentions = []
                for pattern in _EMPLOYEE_PATTERNS:
                    employee_mentions.extend(re.findall(pattern, text, re.IGNORECASE))

                # Contact extraction
                emails = list(
                    {m for m in re.findall(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", text)}
                )[:3]
                phones = list(
                    {m[0] for m in re.findall(r"((\+49|0049|0)[0-9\s\-\/\(\)]{7,20})", text)}
                )[:3]

                meta_desc = ""
                if meta := soup.find("meta", {"name": "description"}):
                    meta_desc = meta.get("content", "")[:300]

                return {
                    "url": url,
                    "erp_keywords_found": found_erp,
                    "employee_mentions": employee_mentions[:5],
                    "emails": emails,
                    "phones": phones,
                    "meta_description": meta_desc,
                    "text_excerpt": text[:3000],
                }
        except Exception as exc:
            return {"url": url, "error": str(exc)}
