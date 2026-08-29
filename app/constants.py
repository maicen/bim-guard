"""Static reference data for BIM-Guard project setup and analysis routing.

Generated from tools/NOTEBOOK_STANDARDS.py and the country list in
docs/experimental/bimguard-frontend-prototype-v1.html. Edit those sources and
regenerate rather than editing this module by hand.
"""

from typing import Any

#: Analysis types a project can be routed to matching rules categories: Arch, Piping, or seismic.
ANALYSIS_TYPES: list[str] = [
    "Arch",
    "Piping",
    "seismic",
]

#: Defaults matching migration column defaults.
DEFAULT_COUNTRY: str = "UK"
DEFAULT_ANALYSIS_TYPE: str = "Arch"

#: LLM extraction defaults
DEFAULT_LLM_MODEL: str = "openrouter/auto"
COMPLIANCE_TEMPERATURE: float = 0.2
MAX_TOKENS_RULE_EXTRACTION: int = 4096

#: Analysis type -> URL slug served by app/routes/analyze_*.py.
ANALYSIS_ROUTES: dict[str, str] = {
    "Arch": "architecture",
    "Piping": "corrosion",
    "seismic": "seismic",
    # Legacy aliases
    "Architectural": "architecture",
    "Architecture": "architecture",
    "Piping (Corrosive)": "corrosion",
    "Seismic": "seismic",
    "Halo": "seismic",
}

_ANALYSIS_TYPE_ALIASES: dict[str, set[str]] = {
    "Arch": {"Arch", "Architectural", "Architecture", "arch"},
    "Piping": {"Piping", "Piping (Corrosive)", "piping", "corrosion"},
    "seismic": {"seismic", "Seismic", "Halo", "Piping (Seismic)"},
}


def normalize_analysis_type(analysis_type: str, default: str = "Arch") -> str:
    """Normalize legacy or alias analysis domain string into canonical domain name: Arch, Piping, or seismic."""
    if not analysis_type:
        return default
    s = analysis_type.strip()
    if s in ("Arch", "Architectural", "Architecture", "arch"):
        return "Arch"
    if s in ("Piping", "Piping (Corrosive)", "piping", "corrosion"):
        return "Piping"
    if s in ("seismic", "Seismic", "Halo", "Piping (Seismic)"):
        return "seismic"
    return s

#: Building types offered by the project setup wizard.
PROJECT_TYPES: list[str] = [
    "Commercial Office",
    "Residential",
    "Healthcare",
    "Educational",
    "Industrial",
    "Retail",
    "Mixed-Use",
    "Infrastructure",
]

#: Client document categories. Mirrors the ``category`` check constraint on
#: ``public.client_documents`` (migration_003) -- keep the two in step.
DOCUMENT_CATEGORIES: list[str] = [
    "Specification",
    "Schedule",
    "Drawing",
    "O&M Manual",
    "Warranty",
    "Assessment",
    "RFI Log",
    "Other",
]

#: Accepted upload extensions for custom standards.
STANDARD_UPLOAD_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx")

#: Countries offered by the wizard (199, alphabetical).
COUNTRIES: list[str] = [
    "Afghanistan",
    "Albania",
    "Algeria",
    "Andorra",
    "Angola",
    "Antigua and Barbuda",
    "Argentina",
    "Armenia",
    "Australia",
    "Austria",
    "Azerbaijan",
    "Bahamas",
    "Bahrain",
    "Bangladesh",
    "Barbados",
    "Belarus",
    "Belgium",
    "Belize",
    "Benin",
    "Bhutan",
    "Bolivia",
    "Bosnia and Herzegovina",
    "Botswana",
    "Brazil",
    "Brunei",
    "Bulgaria",
    "Burkina Faso",
    "Burundi",
    "Cabo Verde",
    "Cambodia",
    "Cameroon",
    "Canada",
    "Central African Republic",
    "Chad",
    "Chile",
    "China",
    "Colombia",
    "Comoros",
    "Congo (Brazzaville)",
    "Congo (Kinshasa)",
    "Costa Rica",
    "Croatia",
    "Cuba",
    "Cyprus",
    "Czechia",
    "Côte d'Ivoire",
    "Denmark",
    "Djibouti",
    "Dominica",
    "Dominican Republic",
    "Ecuador",
    "Egypt",
    "El Salvador",
    "Equatorial Guinea",
    "Eritrea",
    "Estonia",
    "Eswatini",
    "Ethiopia",
    "Fiji",
    "Finland",
    "France",
    "Gabon",
    "Gambia",
    "Georgia",
    "Germany",
    "Ghana",
    "Greece",
    "Grenada",
    "Guatemala",
    "Guinea",
    "Guinea-Bissau",
    "Guyana",
    "Haiti",
    "Honduras",
    "Hong Kong SAR",
    "Hungary",
    "Iceland",
    "India",
    "Indonesia",
    "Iran",
    "Iraq",
    "Ireland",
    "Israel",
    "Italy",
    "Jamaica",
    "Japan",
    "Jordan",
    "Kazakhstan",
    "Kenya",
    "Kiribati",
    "Kosovo",
    "Kuwait",
    "Kyrgyzstan",
    "Laos",
    "Latvia",
    "Lebanon",
    "Lesotho",
    "Liberia",
    "Libya",
    "Liechtenstein",
    "Lithuania",
    "Luxembourg",
    "Macao SAR",
    "Madagascar",
    "Malawi",
    "Malaysia",
    "Maldives",
    "Mali",
    "Malta",
    "Marshall Islands",
    "Mauritania",
    "Mauritius",
    "Mexico",
    "Micronesia",
    "Moldova",
    "Monaco",
    "Mongolia",
    "Montenegro",
    "Morocco",
    "Mozambique",
    "Myanmar",
    "Namibia",
    "Nauru",
    "Nepal",
    "Netherlands",
    "New Zealand",
    "Nicaragua",
    "Niger",
    "Nigeria",
    "North Korea",
    "North Macedonia",
    "Norway",
    "Oman",
    "Pakistan",
    "Palau",
    "Palestine",
    "Panama",
    "Papua New Guinea",
    "Paraguay",
    "Peru",
    "Philippines",
    "Poland",
    "Portugal",
    "Qatar",
    "Romania",
    "Russia",
    "Rwanda",
    "Saint Kitts and Nevis",
    "Saint Lucia",
    "Saint Vincent and the Grenadines",
    "Samoa",
    "San Marino",
    "Sao Tome and Principe",
    "Saudi Arabia",
    "Senegal",
    "Serbia",
    "Seychelles",
    "Sierra Leone",
    "Singapore",
    "Slovakia",
    "Slovenia",
    "Solomon Islands",
    "Somalia",
    "South Africa",
    "South Korea",
    "South Sudan",
    "Spain",
    "Sri Lanka",
    "Sudan",
    "Suriname",
    "Sweden",
    "Switzerland",
    "Syria",
    "Taiwan",
    "Tajikistan",
    "Tanzania",
    "Thailand",
    "Timor-Leste",
    "Togo",
    "Tonga",
    "Trinidad and Tobago",
    "Tunisia",
    "Turkey",
    "Turkmenistan",
    "Tuvalu",
    "Uganda",
    "Ukraine",
    "United Arab Emirates",
    "United Kingdom",
    "United States",
    "Uruguay",
    "Uzbekistan",
    "Vanuatu",
    "Vatican City",
    "Venezuela",
    "Vietnam",
    "Yemen",
    "Zambia",
    "Zimbabwe",
]

#: Standard domains, in the order they should be presented.
STANDARD_DOMAINS: list[str] = [
    "Galvanic Corrosion",
    "Crevice Corrosion",
    "Mechanical Assembly",
    "Structural Design",
    "BIM Information Management",
    "Building Safety & Compliance",
    "Regulatory / AI Governance",
    "Regional Building Code",
    "Safety & Health",
    "Thermal & Environmental",
]

#: Normative references from the thesis, offered in wizard step 5.
NOTEBOOK_STANDARDS: list[dict[str, Any]] = [
    {
        "id": "nasa-12",
        "name": "NASA-STD-6012",
        "domain": "Galvanic Corrosion",
        "description": "Voltage thresholds and galvanic couple classification (0.15V harsh, 0.25V normal, 0.50V controlled)",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"],
    },
    {
        "id": "imoa-4th",
        "name": "IMOA Design Manual 4th Edition",
        "domain": "Galvanic Corrosion",
        "description": "PREN formula, stainless steel grade selection, galvanic series",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"],
    },
    {
        "id": "worldstainless-25",
        "name": "WorldStainless / Euro Inox (2025)",
        "domain": "Galvanic Corrosion",
        "description": "Galvanic series, corrosion rate data, material compatibility",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"],
    },
    {
        "id": "aucsc-24",
        "name": "AUCSC Basic Corrosion Course (2024)",
        "domain": "Galvanic Corrosion",
        "description": "Galvanic series, electrolyte conductivity, potential differences",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"],
    },
    {
        "id": "aga",
        "name": "American Galvanizers Association",
        "domain": "Galvanic Corrosion",
        "description": "Coating life data, galvanised steel durability, coating protection",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"],
    },
    {
        "id": "en-15329",
        "name": "EN ISO 15329:2007",
        "domain": "Crevice Corrosion",
        "description": "Crevice corrosion testing, Critical Crevice Corrosion Temperature (CCT), wetting classes T0–T5",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"],
    },
    {
        "id": "astm-g48",
        "name": "ASTM G48 Method B",
        "domain": "Crevice Corrosion",
        "description": "CCT values for stainless steel grades, crevice corrosion testing methodology",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"],
    },
    {
        "id": "ciria-c692",
        "name": "CIRIA C692",
        "domain": "Crevice Corrosion",
        "description": "Stainless steel in construction, CCT data, joint design guidance",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"],
    },
    {
        "id": "cibse-g",
        "name": "CIBSE Guide G",
        "domain": "Crevice Corrosion",
        "description": "Plumbing and MEP crevice corrosion guidance, material selection for HVAC/water systems",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"],
    },
    {
        "id": "prosoco-104",
        "name": "Prosoco Tech Note 104",
        "domain": "Mechanical Assembly",
        "description": "Area ratio analysis for mechanical anchors, bimetallic corrosion in fixings",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo"],
    },
    {
        "id": "bs-8539",
        "name": "BS 8539",
        "domain": "Mechanical Assembly",
        "description": "Fixings in construction, bi-metallic assembly, corrosion protection",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo"],
    },
    {
        "id": "en-1993-1-4",
        "name": "EN 1993-1-4",
        "domain": "Structural Design",
        "description": "Structural stainless steel design, material grades, mechanical properties",
        "source": "notebook",
        "applicable_to": ["Halo"],
    },
    {
        "id": "asce-7-22",
        "name": "ASCE 7-22",
        "domain": "Structural Design",
        "description": "Seismic design standard, structural bracing requirements, loading",
        "source": "notebook",
        "applicable_to": ["Halo"],
    },
    {
        "id": "iso-19650",
        "name": "ISO 19650-1/2/3/6",
        "domain": "BIM Information Management",
        "description": "BIM information management, IFC property set framework, data exchange",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"],
    },
    {
        "id": "iso-16739",
        "name": "ISO 16739-1:2024",
        "domain": "BIM Information Management",
        "description": "Industry Foundation Classes (IFC) specification, open BIM standard",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"],
    },
    {
        "id": "bcf-2-1",
        "name": "buildingSMART BCF 2.1",
        "domain": "BIM Information Management",
        "description": "BIM Collaboration Format for issue tracking, viewpoints, markup",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"],
    },
    {
        "id": "ids-1-0",
        "name": "IDS v1.0 (buildingSMART)",
        "domain": "BIM Information Management",
        "description": "Information Delivery Specification, data requirements definition (1 June 2024)",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"],
    },
    {
        "id": "bimforum-lod-25",
        "name": "BIMForum LOD Specification 2025",
        "domain": "BIM Information Management",
        "description": "Level of Development (LOD) definitions, model maturity levels",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"],
    },
    {
        "id": "building-safety-22",
        "name": "Building Safety Act 2022",
        "domain": "Building Safety & Compliance",
        "description": "Golden Thread requirements for higher-risk buildings, compliance tracking",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"],
    },
    {
        "id": "eu-ai-act",
        "name": "EU AI Act",
        "domain": "Regulatory / AI Governance",
        "description": "AI system governance, transparency, risk management in automated decisions",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"],
    },
    {
        "id": "nist-ai-rmf",
        "name": "NIST AI Risk Management Framework 1.0",
        "domain": "Regulatory / AI Governance",
        "description": "AI risk assessment, mitigation strategies, governance",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"],
    },
    {
        "id": "cbc-2024",
        "name": "California Building Code 2024",
        "domain": "Regional Building Code",
        "description": "US state building standard, structural and MEP requirements (California)",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"],
    },
    {
        "id": "nbc-2020",
        "name": "National Building Code 2020",
        "domain": "Regional Building Code",
        "description": "Canadian building standard, structural and MEP requirements",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"],
    },
    {
        "id": "hse-hsg274",
        "name": "HSE HSG274",
        "domain": "Safety & Health",
        "description": "UK Health & Safety Executive guidance on Legionella in water systems, water treatment",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"],
    },
    {
        "id": "cibse-tm13",
        "name": "CIBSE TM13",
        "domain": "Thermal & Environmental",
        "description": "Thermal analysis, environmental design guidance for MEP systems",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Architecture"],
    },
]

#: Fast lookup by standard id.
STANDARDS_BY_ID: dict[str, dict[str, Any]] = {s["id"]: s for s in NOTEBOOK_STANDARDS}


def get_standards_by_domain(domain: str) -> list[dict[str, Any]]:
    """Return the standards belonging to ``domain``, in declaration order."""
    return [s for s in NOTEBOOK_STANDARDS if s["domain"] == domain]


def get_standards_by_analysis_type(analysis_type: str) -> list[dict[str, Any]]:
    """Return the standards applicable to ``analysis_type``."""
    canon = normalize_analysis_type(analysis_type)
    aliases = _ANALYSIS_TYPE_ALIASES.get(canon, {analysis_type})
    return [
        s
        for s in NOTEBOOK_STANDARDS
        if any(a in s.get("applicable_to", []) for a in aliases)
    ]


def get_all_domains() -> list[str]:
    """Return every domain, in presentation order.

    Ordered rather than set-derived so grouped checkbox lists render the same
    way on every request.
    """
    return list(STANDARD_DOMAINS)


def get_standard(standard_id: str) -> dict[str, Any] | None:
    """Return one standard by id, or ``None`` if it is not a notebook standard."""
    return STANDARDS_BY_ID.get(standard_id)


def group_standards_by_domain(analysis_type: str | None = None):
    """Yield ``(domain, standards)`` pairs for rendering the grouped picker.

    Passing ``analysis_type`` narrows each group to the standards that apply to
    it; domains left with no standards are skipped.
    """
    aliases = (
        _ANALYSIS_TYPE_ALIASES.get(normalize_analysis_type(analysis_type), {analysis_type})
        if analysis_type is not None
        else None
    )
    for domain in STANDARD_DOMAINS:
        items = get_standards_by_domain(domain)
        if aliases is not None:
            items = [
                s
                for s in items
                if any(a in s.get("applicable_to", []) for a in aliases)
            ]
        if items:
            yield domain, items


def route_for_analysis_type(analysis_type: str) -> str:
    """Return the URL slug for ``analysis_type``.

    Raises:
        ValueError: if ``analysis_type`` is not one of :data:`ANALYSIS_TYPES` or recognized aliases.
    """
    canon = normalize_analysis_type(analysis_type)
    if canon in ANALYSIS_ROUTES:
        return ANALYSIS_ROUTES[canon]
    if analysis_type in ANALYSIS_ROUTES:
        return ANALYSIS_ROUTES[analysis_type]
    raise ValueError(f"Unknown analysis type: {analysis_type!r}")
