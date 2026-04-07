# BIMGUARD AI — Research Resources

**Project:** BIMGUARD AI — Automated BIM Compliance Checking System
**Programme:** MAICEN-1125 · Zigurat Global Institute of Technology · Group 5
**Team:** Mark Shane Haines · Osama Ata · Letícia Cristovam Clemente · Malak Yaseen · Marc Azzam

---

## Google NotebookLM Research Notebooks

These notebooks contain the curated research sources, AI-generated summaries, and compliance rule foundations that underpin the BIMGUARD AI rule engine. Click the links to open them directly in your browser — no login required.

### Notebook 1 — AI BIM/MEP Compliance Copilot
> Core research notebook covering galvanic corrosion theory, MEP material compatibility, the galvanic series, and how these translate into machine-readable compliance rules for the BIMGUARD AI rule engine.

**Open notebook:** https://notebooklm.google.com/notebook/c4fb4eb1-cf82-4ef1-b9be-24c97fc2b801

**Key topics covered:**
- Galvanic corrosion mechanisms — anode/cathode, voltage gaps, area ratio effect
- Galvanic series data (NASA-STD-6012 / WorldStainless Vol.10)
- MEP material pairings — copper pipework, stainless steel fixings, aluminium cladding
- Environment class multipliers — Interior, Urban Exterior, Coastal, Pool
- ISO 19650 compliance requirements for material metadata in BIM models
- BCF issue report format and structure
- AI and BIM integration research (2023–2025 papers)

---

### Notebook 2 — BIMGUARD AI Halo Module
> Research notebook focused on the Halo clearance volume innovation — the soft/spatial compliance capability that distinguishes BIMGUARD AI from standard clash detection tools.

**Open notebook:** https://notebooklm.google.com/notebook/2eb5fed8-cfbb-424d-bc05-a4c322b227f3

**Key topics covered:**
- Soft/spatial compliance — maintenance zones, clearance volumes, egress widths
- Halo volume calculation from IFC bounding boxes
- NFPA 70 electrical panel clearance requirements
- IfcOpenShell spatial relationship queries
- Comparison of BIMGUARD AI Halo approach vs standard clash detection
- SHACL constraint application to IFC linked building data

---

## How to Use These Notebooks

Each notebook contains the source documents and AI-generated research that informed the BIMGUARD AI rule sets. Use them to:

| Task | How |
|---|---|
| Look up a rule source clause | Search the notebook for the standard name (e.g. NASA-STD-6012) |
| Generate a new rule set | Prompt the notebook: "Extract all material compatibility rules from these sources and return as BIMGUARD AI JSON format" |
| Write thesis content | Prompt: "Act as a Masters thesis supervisor. Write a 300-word literature review paragraph on [topic] using these sources" |
| Verify a technical claim | Paste the claim into the notebook and ask "Is this supported by the sources?" |

---

## Key Source Documents

The following documents are loaded into the NotebookLM notebooks and form the academic foundation of the BIMGUARD AI rule engine.

### Galvanic Corrosion — Technical Standards
| Source | URL | Used in |
|---|---|---|
| WorldStainless: Stainless Steel in Contact with Other Metallic Materials | https://worldstainless.org/wp-content/uploads/2025/02/Contact_with_Other_EN.pdf | Notebook 1 |
| Prosoco Tech Note 104: Galvanic Corrosion in Mechanical Anchors | https://prosoco.com/app/uploads/2021/06/Tech-Note-104-Galvanic-Corrosion-in-Mechanical-Anchors.pdf | Notebook 1 |
| AUCSC Basic Corrosion Course (2024) | https://www.aucsc.com/downloads/AUCSC%20Basic%20Text%20%202024.pdf | Notebook 1 |
| IMOA: Which Stainless Steel Should Be Specified | https://www.imoa.info/download_files/stainless-steel/folder_which_stainless_steel_EN.pdf | Notebook 1 |
| Nickel Institute: Design Guidelines for Stainless Steels (No. 9014) | https://nickelinstitute.org/media/1667/designguidelinesfortheselectionanduseofstainlesssteels_9014_.pdf | Notebook 1 |

### BIM, AI and Digital Twin Research
| Source | URL | Used in |
|---|---|---|
| AI Applications in BIM — Systematic Mapping (2025) | https://www.tandfonline.com/doi/full/10.1080/17452007.2025.2579741 | Notebook 1 |
| ML for Corrosion in MEP Pipelines (PMC, 2024) | https://pmc.ncbi.nlm.nih.gov/articles/PMC11175261/ | Notebook 1 |
| BIM-Based Corrosion Prediction (ResearchGate, 2019) | https://www.researchgate.net/publication/336960091 | Notebook 1 |
| Deep Learning in Corrosion Assessment (De Gruyter, 2024) | https://www.degruyterbrill.com/document/doi/10.1515/corrrev-2024-0060/html | Notebook 1 |

### Spatial Compliance and Halo Module
| Source | URL | Used in |
|---|---|---|
| NFPA 70 National Electrical Code — Panel Clearances | https://www.nfpa.org/codes-and-standards/nfpa-70 | Notebook 2 |
| IfcOpenShell Documentation | https://ifcopenshell.org | Notebook 2 |
| BuildingSMART IFC4 Reference View | https://www.buildingsmart.org | Notebook 2 |
| ISO 19650 BIM Implementation Framework | https://globalbim.org/info-collection/mexico-national-implementation-of-iso-19650-standard/ | Notebooks 1 & 2 |

---

## NotebookLM Prompts Used

The following prompts were used to generate rule sets, literature reviews and compliance checklists from the research sources. Recorded here as part of the White Box Architecture audit trail.

### Rule generation
```
Using the WorldStainless PDF and Prosoco Tech Note 104, create a table of the 10 most
common MEP material pairings. For each pair state: the anodic metal, the cathodic metal,
the approximate voltage gap, and the risk level in a coastal vs interior environment.
```

### Literature review
```
Act as a Masters thesis supervisor. Using all sources, write a 300-word critical
literature review paragraph that positions BIMGUARD AI within existing research on
corrosion prediction, digital twins, and BIM automation. Identify the gap the project fills.
```

### ISO 19650 compliance mapping
```
From the BIM and AI sources, identify which IFC metadata attributes should be tagged
on MEP components to enable automated galvanic corrosion checking. Map each attribute
to its corresponding compliance check (voltage gap, area ratio, environment class).
```

### Halo module research
```
Using the spatial compliance sources, describe what clearance volumes are required
around electrical panels, mechanical equipment, and fire suppression systems under
NFPA 70 and BS EN standards. Return as a structured JSON rule set in BIMGUARD AI format.
```

---

## Contributing to This File

If you add a new NotebookLM notebook or source document to the project, update this file by:

1. Opening `RESOURCES.md` in GitHub
2. Clicking the pencil (edit) icon
3. Adding your notebook link and description in the correct section
4. Scrolling to the bottom and clicking **Commit changes**
5. Write a commit message like: `docs: add new NotebookLM notebook — [topic name]`

---

*Last updated: April 2026 · BIMGUARD AI Group 5 · MAICEN-1125*
