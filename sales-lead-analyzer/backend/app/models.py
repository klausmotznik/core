from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime


class Region(str, Enum):
    DACH = "DACH"
    DEUTSCHLAND = "Deutschland"
    OESTERREICH = "Österreich"
    SCHWEIZ = "Schweiz"
    BADEN_WUERTTEMBERG = "Baden-Württemberg"
    BAYERN = "Bayern"
    BERLIN = "Berlin"
    BRANDENBURG = "Brandenburg"
    BREMEN = "Bremen"
    HAMBURG = "Hamburg"
    HESSEN = "Hessen"
    MECKLENBURG_VORPOMMERN = "Mecklenburg-Vorpommern"
    NIEDERSACHSEN = "Niedersachsen"
    NORDRHEIN_WESTFALEN = "Nordrhein-Westfalen"
    RHEINLAND_PFALZ = "Rheinland-Pfalz"
    SAARLAND = "Saarland"
    SACHSEN = "Sachsen"
    SACHSEN_ANHALT = "Sachsen-Anhalt"
    SCHLESWIG_HOLSTEIN = "Schleswig-Holstein"
    THUERINGEN = "Thüringen"


class ERPSystem(str, Enum):
    NAVISION = "Navision"
    SAP_R3 = "SAP R3"
    AX_2012 = "AX 2012"
    PRO_ALPHA = "Pro Alpha"
    S4_HANA = "S4 Hana"
    ORACLE = "Oracle"


class EmployeeSize(str, Enum):
    UNTER_200 = "unter_200"
    ZWISCHEN_200_500 = "200_500"
    ZWISCHEN_500_1000 = "500_1000"
    UEBER_1000 = "ueber_1000"


class LeadCategory(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class CompanyInfo(BaseModel):
    name: str
    website: Optional[str] = None
    description: Optional[str] = None


class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    decision_maker_hints: Optional[str] = None


class Lead(BaseModel):
    id: str
    company_name: str
    website: Optional[str] = None
    region: Optional[str] = None
    employee_count_estimate: Optional[str] = None
    industry: Optional[str] = None
    erp_indicators: List[str] = []
    erp_evidence: List[str] = []
    lead_score: int = Field(ge=0, le=100)
    lead_category: LeadCategory
    qualification_notes: str
    contact_info: ContactInfo = ContactInfo()
    sources: List[str] = []
    migration_potential: Optional[str] = None


class LeadSearchRequest(BaseModel):
    industry: str = Field(..., description="Branche des Unternehmens, z.B. Maschinenbau, Handel")
    region: Region = Field(..., description="Region oder Bundesland")
    erp_system: ERPSystem = Field(..., description="Eingesetztes ERP-System das gesucht wird")
    employee_size: EmployeeSize = Field(..., description="Mitarbeiterzahl-Kategorie")
    max_results: int = Field(default=10, ge=1, le=20)


class LeadSearchResponse(BaseModel):
    leads: List[Lead]
    total_found: int
    search_criteria: Dict
    search_timestamp: str
