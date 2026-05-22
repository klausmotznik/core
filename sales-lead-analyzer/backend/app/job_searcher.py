import asyncio
from typing import Dict, List

from duckduckgo_search import DDGS

_ERP_SEARCH_TERMS: Dict[str, List[str]] = {
    "Navision": ["Navision", "Microsoft Dynamics NAV", "Business Central"],
    "SAP R3": ["SAP R/3", "SAP R3", "SAP ECC"],
    "AX 2012": ["Dynamics AX", "AX 2012", "Microsoft AX"],
    "Pro Alpha": ["proALPHA", "Pro Alpha"],
    "S4 Hana": ["S/4HANA", "S4HANA", "SAP S/4"],
    "Oracle": ["Oracle ERP", "Oracle E-Business Suite", "Oracle Fusion"],
}

_JOB_PORTALS = [
    "stepstone.de",
    "indeed.com",
    "monster.de",
    "xing.com/jobs",
    "linkedin.com/jobs",
]


async def _ddg_text(query: str, max_results: int = 5) -> List[Dict]:
    def _run():
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results, region="de-de"))

    try:
        return await asyncio.to_thread(_run)
    except Exception:
        return []


class JobSearcher:
    async def search_erp_jobs(self, company_name: str, erp_system: str) -> Dict:
        terms = _ERP_SEARCH_TERMS.get(erp_system, [erp_system])

        job_findings: List[Dict] = []
        erp_evidence: List[str] = []
        seen_urls: set = set()

        # Portal-specific searches (limit to first 3 portals, first 2 ERP terms)
        portal_tasks = []
        for portal in _JOB_PORTALS[:3]:
            for term in terms[:2]:
                query = f'site:{portal} "{company_name}" "{term}"'
                portal_tasks.append((portal, term, query))

        results = await asyncio.gather(
            *[_ddg_text(q, max_results=3) for _, _, q in portal_tasks]
        )

        for (portal, term, _), hits in zip(portal_tasks, results):
            for hit in hits:
                url = hit.get("href", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                body = hit.get("body", "")
                if company_name.lower() in body.lower() or company_name.lower() in hit.get("title", "").lower():
                    job_findings.append(
                        {
                            "portal": portal,
                            "title": hit.get("title", "")[:150],
                            "excerpt": body[:300],
                            "url": url,
                            "erp_term": term,
                        }
                    )
                    if term.lower() in body.lower():
                        erp_evidence.append(
                            f"Stellenanzeige auf {portal} erwähnt '{term}'"
                        )

        # General job search (all portals, broader query)
        general_query = f'"{company_name}" Stellenanzeige {" OR ".join(terms[:3])} Kenntnisse'
        general_hits = await _ddg_text(general_query, max_results=8)
        for hit in general_hits:
            body = hit.get("body", "")
            for term in terms:
                if term.lower() in body.lower():
                    evidence = f"Allgemeine Jobsuche: '{term}' in Stellenanzeige von {company_name}"
                    if evidence not in erp_evidence:
                        erp_evidence.append(evidence)

        return {
            "company": company_name,
            "erp_system": erp_system,
            "job_findings": job_findings[:10],
            "erp_evidence": list(set(erp_evidence))[:8],
        }
