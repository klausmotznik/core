import json
import uuid
from typing import Dict

import anthropic

from .models import (
    CompanyInfo,
    ContactInfo,
    Lead,
    LeadCategory,
    LeadSearchRequest,
)

_SCORING_INSTRUCTIONS = """
Bewertungskriterien (Punkte addieren sich):
- Starke Hinweise auf gesuchtes ERP-System: +35 Punkte
- Schwache/indirekte ERP-Hinweise: +15 Punkte
- Mitarbeiterzahl passt zur Kategorie: +20 Punkte
- Region stimmt überein: +15 Punkte
- Hinweise auf Migrationsbedarf (altes System, Wachstum, offene ERP-Stellen): +20 Punkte
- Vollständige Kontaktdaten verfügbar: +10 Punkte

Kategorien:
- hot: Score >= 70 (klare ERP-Nutzung + passende Größe/Region)
- warm: Score 40-69 (wahrscheinliche ERP-Nutzung oder gute Kriterienpassung)
- cold: Score < 40 (wenig Hinweise, unklare Datenlage)
"""


class LeadQualifier:
    def __init__(self, model: str = "claude-opus-4-7"):
        self.client = anthropic.Anthropic()
        self.model = model

    async def qualify_lead(
        self,
        company: CompanyInfo,
        homepage_info: Dict,
        job_info: Dict,
        criteria: LeadSearchRequest,
    ) -> Lead:
        context = (
            f"Unternehmensname: {company.name}\n"
            f"Website: {company.website or 'unbekannt'}\n"
            f"Beschreibung: {company.description or ''}\n\n"
            f"=== Homepage-Analyse ===\n"
            f"{json.dumps(homepage_info, ensure_ascii=False, indent=2)}\n\n"
            f"=== Stellenanzeigen-Recherche ===\n"
            f"{json.dumps(job_info, ensure_ascii=False, indent=2)}\n\n"
            f"=== Suchkriterien ===\n"
            f"Branche: {criteria.industry}\n"
            f"Region: {criteria.region}\n"
            f"Gesuchtes ERP-System: {criteria.erp_system}\n"
            f"Mitarbeitergröße: {criteria.employee_size}\n"
        )

        prompt = f"""Du bist ein B2B Sales-Experte für ERP-Software-Migrationen im DACH-Markt.
Analysiere diesen potenziellen Sales Lead und erstelle eine strukturierte Bewertung.

{context}

{_SCORING_INSTRUCTIONS}

Gib deine Antwort AUSSCHLIESSLICH als JSON-Objekt zurück (kein Markdown, keine Erklärungen):

{{
  "lead_score": <Zahl 0-100>,
  "lead_category": <"hot" | "warm" | "cold">,
  "employee_count_estimate": <z.B. "ca. 250", "500-1000", "unbekannt">,
  "erp_indicators": [<Liste konkreter Textfundstellen die auf ERP hinweisen>],
  "erp_evidence": [<Liste von Belegen aus Stellenanzeigen/Homepage>],
  "migration_potential": <"hoch" | "mittel" | "niedrig" | "unbekannt">,
  "contact_info": {{
    "email": <E-Mail-Adresse oder null>,
    "phone": <Telefonnummer oder null>,
    "decision_maker_hints": <Hinweise auf IT-/ERP-Entscheider oder null>
  }},
  "qualification_notes": <2-3 prägnante Sätze auf Deutsch zur Lead-Qualität und Empfehlung>
}}"""

        try:
            import asyncio

            def _call():
                return self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )

            message = await asyncio.to_thread(_call)
            raw = message.content[0].text.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0]

            data = json.loads(raw.strip())

            contact = data.get("contact_info", {})
            return Lead(
                id=str(uuid.uuid4()),
                company_name=company.name,
                website=company.website,
                region=str(criteria.region.value),
                employee_count_estimate=data.get("employee_count_estimate", "unbekannt"),
                industry=criteria.industry,
                erp_indicators=data.get("erp_indicators", []),
                erp_evidence=data.get("erp_evidence", []),
                lead_score=min(100, max(0, int(data.get("lead_score", 0)))),
                lead_category=LeadCategory(data.get("lead_category", "cold")),
                qualification_notes=data.get("qualification_notes", ""),
                contact_info=ContactInfo(
                    email=contact.get("email"),
                    phone=contact.get("phone"),
                    decision_maker_hints=contact.get("decision_maker_hints"),
                ),
                sources=[company.website] if company.website else [],
                migration_potential=data.get("migration_potential"),
            )

        except Exception as exc:
            return Lead(
                id=str(uuid.uuid4()),
                company_name=company.name,
                website=company.website,
                region=str(criteria.region.value),
                industry=criteria.industry,
                erp_indicators=[],
                erp_evidence=[],
                lead_score=0,
                lead_category=LeadCategory.COLD,
                qualification_notes=f"Automatische Analyse fehlgeschlagen: {exc}",
                sources=[company.website] if company.website else [],
            )
