# NOTEBOOK_STANDARDS.py
# All reference standards from BIMGUARD AI thesis
# Used in project setup wizard Step 5 (Standards Selection)

NOTEBOOK_STANDARDS = [
    # Galvanic Corrosion Standards
    {
        "id": "nasa-12",
        "name": "NASA-STD-6012",
        "domain": "Galvanic Corrosion",
        "description": "Voltage thresholds and galvanic couple classification (0.15V harsh, 0.25V normal, 0.50V controlled)",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"]
    },
    {
        "id": "imoa-4th",
        "name": "IMOA Design Manual 4th Edition",
        "domain": "Galvanic Corrosion",
        "description": "PREN formula, stainless steel grade selection, galvanic series",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"]
    },
    {
        "id": "worldstainless-25",
        "name": "WorldStainless / Euro Inox (2025)",
        "domain": "Galvanic Corrosion",
        "description": "Galvanic series, corrosion rate data, material compatibility",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"]
    },
    {
        "id": "aucsc-24",
        "name": "AUCSC Basic Corrosion Course (2024)",
        "domain": "Galvanic Corrosion",
        "description": "Galvanic series, electrolyte conductivity, potential differences",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"]
    },
    {
        "id": "aga",
        "name": "American Galvanizers Association",
        "domain": "Galvanic Corrosion",
        "description": "Coating life data, galvanised steel durability, coating protection",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"]
    },
    
    # Crevice Corrosion Standards
    {
        "id": "en-15329",
        "name": "EN ISO 15329:2007",
        "domain": "Crevice Corrosion",
        "description": "Crevice corrosion testing, Critical Crevice Corrosion Temperature (CCT), wetting classes T0–T5",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"]
    },
    {
        "id": "astm-g48",
        "name": "ASTM G48 Method B",
        "domain": "Crevice Corrosion",
        "description": "CCT values for stainless steel grades, crevice corrosion testing methodology",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"]
    },
    {
        "id": "ciria-c692",
        "name": "CIRIA C692",
        "domain": "Crevice Corrosion",
        "description": "Stainless steel in construction, CCT data, joint design guidance",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"]
    },
    {
        "id": "cibse-g",
        "name": "CIBSE Guide G",
        "domain": "Crevice Corrosion",
        "description": "Plumbing and MEP crevice corrosion guidance, material selection for HVAC/water systems",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"]
    },
    
    # Mechanical/Structural Standards
    {
        "id": "prosoco-104",
        "name": "Prosoco Tech Note 104",
        "domain": "Mechanical Assembly",
        "description": "Area ratio analysis for mechanical anchors, bimetallic corrosion in fixings",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo"]
    },
    {
        "id": "bs-8539",
        "name": "BS 8539",
        "domain": "Mechanical Assembly",
        "description": "Fixings in construction, bi-metallic assembly, corrosion protection",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo"]
    },
    {
        "id": "en-1993-1-4",
        "name": "EN 1993-1-4",
        "domain": "Structural Design",
        "description": "Structural stainless steel design, material grades, mechanical properties",
        "source": "notebook",
        "applicable_to": ["Halo"]
    },
    {
        "id": "asce-7-22",
        "name": "ASCE 7-22",
        "domain": "Structural Design",
        "description": "Seismic design standard, structural bracing requirements, loading",
        "source": "notebook",
        "applicable_to": ["Halo"]
    },
    
    # BIM & Information Management
    {
        "id": "iso-19650",
        "name": "ISO 19650-1/2/3/6",
        "domain": "BIM Information Management",
        "description": "BIM information management, IFC property set framework, data exchange",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"]
    },
    {
        "id": "iso-16739",
        "name": "ISO 16739-1:2024",
        "domain": "BIM Information Management",
        "description": "Industry Foundation Classes (IFC) specification, open BIM standard",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"]
    },
    {
        "id": "bcf-2-1",
        "name": "buildingSMART BCF 2.1",
        "domain": "BIM Information Management",
        "description": "BIM Collaboration Format for issue tracking, viewpoints, markup",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"]
    },
    {
        "id": "ids-1-0",
        "name": "IDS v1.0 (buildingSMART)",
        "domain": "BIM Information Management",
        "description": "Information Delivery Specification, data requirements definition (1 June 2024)",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"]
    },
    {
        "id": "bimforum-lod-25",
        "name": "BIMForum LOD Specification 2025",
        "domain": "BIM Information Management",
        "description": "Level of Development (LOD) definitions, model maturity levels",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"]
    },
    
    # Building Safety & Compliance
    {
        "id": "building-safety-22",
        "name": "Building Safety Act 2022",
        "domain": "Building Safety & Compliance",
        "description": "Golden Thread requirements for higher-risk buildings, compliance tracking",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"]
    },
    {
        "id": "eu-ai-act",
        "name": "EU AI Act",
        "domain": "Regulatory / AI Governance",
        "description": "AI system governance, transparency, risk management in automated decisions",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"]
    },
    {
        "id": "nist-ai-rmf",
        "name": "NIST AI Risk Management Framework 1.0",
        "domain": "Regulatory / AI Governance",
        "description": "AI risk assessment, mitigation strategies, governance",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"]
    },
    
    # Regional Building Codes
    {
        "id": "cbc-2024",
        "name": "California Building Code 2024",
        "domain": "Regional Building Code",
        "description": "US state building standard, structural and MEP requirements (California)",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"]
    },
    {
        "id": "nbc-2020",
        "name": "National Building Code 2020",
        "domain": "Regional Building Code",
        "description": "Canadian building standard, structural and MEP requirements",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Halo", "Architecture"]
    },
    {
        "id": "hse-hsg274",
        "name": "HSE HSG274",
        "domain": "Safety & Health",
        "description": "UK Health & Safety Executive guidance on Legionella in water systems, water treatment",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)"]
    },
    {
        "id": "cibse-tm13",
        "name": "CIBSE TM13",
        "domain": "Thermal & Environmental",
        "description": "Thermal analysis, environmental design guidance for MEP systems",
        "source": "notebook",
        "applicable_to": ["Piping (Corrosive)", "Architecture"]
    },
]

# Helper function to get standards by domain
def get_standards_by_domain(domain):
    return [s for s in NOTEBOOK_STANDARDS if s["domain"] == domain]

# Helper function to get standards by analysis type
def get_standards_by_analysis_type(analysis_type):
    return [s for s in NOTEBOOK_STANDARDS if analysis_type in s.get("applicable_to", [])]

# Helper function to get all unique domains
def get_all_domains():
    return list(set(s["domain"] for s in NOTEBOOK_STANDARDS))
