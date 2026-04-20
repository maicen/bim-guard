# BIMGUARD AI — NotebookLM Master Prompt and Query Templates

## Master prompt

Paste this as your first message in a new NotebookLM session to configure the notebook's behaviour before running any technical queries.

---

> You are the BIMGUARD AI Technical Auditor. BIMGUARD is an OpenBIM automated compliance checking application that detects corrosion risk and spatial coordination failures in MEP (Mechanical, Electrical, and Plumbing) building services using IFC 4.3 data.
>
> When answering questions, apply the following source priority order:
>
> 1. IFC 4.3 documentation (buildingSMART) for all questions about data extraction, property sets, entity definitions, and schema structure
> 2. The pipe spacing formula sources (whatispiping.com, piping-world.com) for all centre-to-centre calculation questions
> 3. ASME B16.5 sources (wermac.org, projectmaterials.com) for US/imperial flange envelope calculations
> 4. EN 1092-1 sources (roymech.org, projectmaterials.com) for European/metric flange envelope calculations
> 5. The engineersedge.com galvanic compatibility table for all material voltage gap assessments
> 6. NASA-STD-6012 voltage thresholds: 0.15V harsh environments, 0.25V normal building services, 0.50V controlled dry conditions
> 7. IMI Framework and ISO 19650 guidance for all information management, CDE workflow, and status code questions
>
> Always provide results in both metric (mm) and imperial (inches) unless the query specifies one system only.
>
> When a calculation is requested, show the formula, identify the source standard, substitute the values, and state the result clearly.
>
> When a material compatibility check is requested, state the voltage gap, the applicable threshold for the environment class, and whether a moisture bridge risk exists based on the proximity described.

---

## Phase 1 — Spatial filter queries

Use these to validate centre-to-centre spacing calculations and understand the Phase 1 logic.

**Basic C-to-C formula**
> Using the pipe spacing formula from the loaded sources, calculate the minimum centre-to-centre distance between a DN100 carbon steel pipe with 50mm insulation and a DN50 stainless steel pipe with 25mm insulation. Show the formula and result in both mm and inches.

**Flange-controlled spacing**
> What is the minimum centre-to-centre distance between an NPS 4 Class 300 flanged line and an NPS 2 Class 150 flanged line, both uninsulated, assuming worst-case non-staggered flange alignment? Use the ASME B16.5 flange OD tables from the loaded sources.

**European standard check**
> Using EN 1092-1 PN16 flange dimensions, what is the minimum centre-to-centre spacing between a DN150 and a DN80 flanged pipe in a normal building services environment with 50mm insulation on both lines?

**Mixed standard hybrid**
> A project has a US-specified NPS 6 Class 150 line running parallel to a European DN150 PN16 line. What is the actual outside diameter difference between these two nominally equivalent pipes, and how does this affect the centre-to-centre calculation?

**Thermal expansion adder**
> A carbon steel steam line 25 metres long operates at 180°C and is installed at 20°C. Using the thermal expansion coefficients from the loaded sources, calculate the free thermal expansion in mm and determine what additional spacing allowance should be added to the base C-to-C minimum.

---

## Phase 2 — Halo envelope queries

Use these to understand LOD 350 space reservation requirements and seismic buffer sizing.

**Standard Halo calculation**
> Calculate the full Phase 2 Halo envelope radius for a DN200 insulated pipe (75mm insulation) in a non-seismic zone. Show the breakdown: pipe radius + insulation + support buffer + seismic buffer.

**Seismic zone comparison**
> Compare the minimum centre-to-centre spacing required for two DN100 pipes with 50mm insulation each in (a) a non-seismic zone and (b) a high-seismic zone applying the SMACNA sway brace buffer. What is the additional spacing required by the seismic zone?

**LOD 300 to LOD 350 transition**
> Explain what information is typically missing from an LOD 300 IFC model that prevents accurate Halo calculation, and what Psets BIMGUARD looks for to determine whether to apply default buffer values.

---

## Phase 3 — Galvanic gate queries

Use these to check material compatibility and understand the three conditions for galvanic corrosion.

**Standard compatibility check**
> Using the galvanic series and voltage threshold data from the loaded sources, assess the galvanic compatibility of copper pipe (Cu) and galvanised steel support brackets in a normal building services environment. State the voltage gap, the applicable threshold, and the recommended mitigation.

**High-purity Fab scenario**
> In a Semiconductor Fab sub-fab environment (harsh, high humidity), assess the galvanic risk of SS316L process pipe running on a shared unistrut hanger with aluminium cable tray. Apply NASA-STD-6012 thresholds.

**Shared support bridge**
> Two pipes are routed 150mm apart centre-to-centre with no direct contact between insulation jackets. Pipe 1 is copper, Pipe 2 is carbon steel. Both are clamped to the same unistrut channel. Does a galvanic couple exist? Explain the moisture bridge mechanism.

**PREN adequacy check**
> What is the Pitting Resistance Equivalent Number (PREN) formula for stainless steels, and what minimum PREN value is recommended for a coastal external environment with chloride concentration above 200 mg/L? Which stainless grades from the loaded sources meet this threshold?

---

## Phase 4 — Resolution hierarchy queries

Use these to understand the logic BIMGUARD applies when deciding which pipe to move.

**Gravity priority**
> A DN150 gravity waste drain (slope 1:100) clashes with a DN50 compressed air pressurised line. Which pipe does BIMGUARD designate as immovable and why? What rule governs this decision?

**Cost delta calculation**
> Pipe A is DN100 SS316L with orbital weld joints. Pipe B is DN50 carbon steel with butt weld joints. A reroute of 5 metres is required on whichever pipe moves. Using labour and material rate principles from the loaded sources, which pipe should move and why?

**Schedule risk tie-break**
> Two pipes have similar reroute costs within 15% of each other. Pipe 1 requires 3 orbital welds in the reroute. Pipe 2 requires 4 standard butt welds. Which pipe should move based on schedule risk, and what is the working day penalty difference?

---

## Phase 5 — Executive report queries

Use these to understand the ISO 19650 output and cost avoidance methodology.

**ISO 19650 status mapping**
> A mechanical services IFC model contains 3 unresolved Phase 1 hard clashes and 5 Phase 2 Halo breaches. What ISO 19650 container status should this model carry in the CDE, and what conditions must be met before it can advance to the next status?

**Cost avoidance methodology**
> Explain the academic basis for the design-stage vs field-stage cost multiplier used in BIMGUARD's cost avoidance calculation. What published framework supports a 6× field multiplier, and what factors drive it higher on Semiconductor Fab projects?

**Golden Thread compliance**
> How does a BIMGUARD Phase 5 output stored against an ISO 19650 information container contribute to the Golden Thread requirement under the Building Safety Act 2022 for higher-risk buildings?

**BCF 2.1 issue structure**
> What are the mandatory fields in a BCF 2.1 issue file, and how does BIMGUARD populate each field from the data generated by Phases 1 through 4?

---

## Cross-phase synthesis queries

Use these for thesis-level synthesis questions that draw across multiple sources.

**OpenBIM vs Closed BIM**
> Explain why BIMGUARD uses IFC (ISO 16739-1) rather than the Revit API as its data source, and how this architectural decision affects which projects and disciplines can use the tool.

**Navisworks gap**
> What is the fundamental limitation of standard BIM clash detection tools such as Navisworks when checking insulated pipe spacing, and how does BIMGUARD's metadata-first approach address this limitation?

**Plannerly integration**
> How would the BIMGUARD five-phase check sequence be implemented within the Plannerly Plan-Scope-Verify workflow? What information requirements would appear in the Scope module, and what triggers the Verify module check?

**Full pipeline worked example**
> Walk through the complete BIMGUARD five-phase check for the following scenario: DN100 SS316 flanged chilled water pipe (50mm insulation) running parallel to DN80 carbon steel hot water pipe (40mm insulation) at 220mm centre-to-centre in a plant room with shared unistrut hangers, non-seismic zone, normal building services environment. State the result of each phase and the final BCF output.
