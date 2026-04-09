# BIMGUARD AI — NotebookLM Source Library

## How to load these sources

In NotebookLM, click **Add Source → Website** and paste each URL individually. NotebookLM will crawl the page and index its content. For best results, load all sources before submitting any queries.

Total sources: 36  
Last verified: April 2026

---

## Module 1 — Centre-to-centre spacing and pipe design

These sources provide the core C-to-C formula, spacing charts, and design principles that underpin Phase 1 of the BIMGUARD spatial filter.

```
https://whatispiping.com/pipe-spacing-chart/
```
Comprehensive pipe spacing chart with the full C-to-C formula, flange factor, insulation adder, and thermal displacement. Covers both metric and imperial. Primary reference for Phase 1 minimum spacing calculations.

```
https://www.piping-world.com/pipe-to-pipe-spacing-calculator
```
Live C-to-C calculator supporting four configurations: bare pipe to bare pipe, flange to flange, mixed, and insulated. Useful for validating BIMGUARD Phase 1 outputs against an independent source.

```
https://pdfyar.com/pipe-spacing-chart-pipeline-spacing-chart-2/
```
Full spacing chart breakdown including 600# and 900# flange rating tables. Contains the standard industry formula: C-to-C = (OD₁/2 + T_ins1) + 25mm + (T_ins2 + OD₂/2) + thermal displacement.

---

## Module 2 — Pipe dimensions (NPS / DN / OD / schedule)

These sources provide the actual outside diameters and wall thicknesses that BIMGUARD reads from IFC Psets and cross-references for validation. Critical for the "ghost clash" problem where NPS 4" (114.3mm OD) differs from DN100 (110mm OD).

```
https://en.wikipedia.org/wiki/Nominal_Pipe_Size
```
Authoritative NPS reference with OD tables based on ASME B36.10M and B36.19M. Explains why nominal size does not equal actual OD for NPS ⅛ through NPS 12, and provides the full schedule wall thickness table.

```
https://www.engineersedge.com/fluid_flow/metric_pipe_sizes_dn_vs_nps_15040.htm
```
DN (Diametre Nominal) vs NPS comparison table from DN 6 to DN 2200. Essential for hybrid projects mixing European and US pipe specifications.

```
https://www.engineersedge.com/pipe_schedules.htm
```
Full schedule chart per ANSI B36.10M and API 5L. Covers OD, wall thickness, and weight per metre for all standard schedules from Schedule 5S through XXS.

```
https://mechguru.com/machine-design/nominal-metric-pipe-size-chart/
```
NPS/DN comparison table compliant with ANSI B36.10M and API 5L. Includes metric wall thickness in mm alongside imperial values in brackets.

---

## Module 3 — Flange dimensions (ASME B16.5 — US / imperial)

Flange OD is almost always the largest radius in a pipe assembly and therefore the controlling dimension in worst-case C-to-C calculations. These sources provide actual flange ODs by class.

```
https://www.wermac.org/flanges/dimensions_welding-neck-flanges_asme-b16-5.html
```
Weld neck flange dimensions in mm and inches for all classes (150–2500). Includes OD, hub diameter, thickness, bolt circle, and dimensional tolerances per ASME B16.5 2013.

```
https://www.wermac.org/flanges/dimensions_weldneck_in_asme-b16-5.html
```
Same data in inch units for Class 150. Cross-reference for imperial project specifications.

```
https://www.wermac.org/flanges/dimensions_weldneck_in_asme-b16-5_300.html
```
Weld neck flange dimensions in inches for Class 300. Used where 300# flanges control the spacing envelope.

```
https://www.wermac.org/flanges/dimensions_weldneck_in_asme-b16-5_600.html
```
Weld neck flange dimensions in inches for Class 600. High-pressure process and steam applications.

```
https://blog.projectmaterials.com/flanges/flange-dimensions/asme-b16-5-slip-on-flange-sizes/
```
Slip-on flange OD, thickness, hub OD, raised face diameter, PCD, bolt hole specs, and weight for Classes 150–2500 in both mm and inches.

```
https://blog.projectmaterials.com/flanges/flange-dimensions/asme-b16-5-socket-weld-flange-sizes/
```
Socket weld flange dimensions for Classes 150, 300, and 600 in mm. Used for small-bore high-pressure applications common in process and pharmaceutical MEP.

```
https://blog.projectmaterials.com/gaskets-bolts/asme-b-15-flange-bolting-torque-charts/
```
Stud bolt dimensions, lengths, and torque charts for ASME B16.5 flanges Classes 150–2500. Used by BIMGUARD's bolt extraction clearance check — bolt length determines the longitudinal clearance zone behind each flange.

---

## Module 4 — Flange dimensions (EN 1092-1 — European / metric)

European flange standard covering PN designations PN6 through PN400. Required for the EU branch of BIMGUARD's dual-standard engine.

```
https://roymech.org/Useful_Tables/Flanges/BSEN1092_16_Dimensions.html
```
BS EN 1092-1 PN16 flange dimensions table. PN16 is the most common rating in commercial building services across Europe.

```
https://www.roymech.co.uk/Useful_Tables/Flanges/BSEN1092_40_Dimensions.html
```
BS EN 1092-1 PN40 flange dimensions. Used for higher-pressure HVAC and process applications.

```
https://blog.projectmaterials.com/category/products/piping/flanges/en-1092-plate-flange-sizes/
```
EN 1092-1 Type 01 plate flange dimensions for PN6, PN10, PN16, PN25, and PN40 with metric stud bolt requirements.

```
https://www.wermac.org/din/dim_wn_flg_pn16.html
```
DIN EN 1092-1 PN16 weld neck (Vorschweiss) flange with hex bolt and stud bolt dimensions. Includes note on interchangeability with ASME B16.5 and MSS SP-44 at equivalent PN ratings.

---

## Module 5 — Thermal expansion (kinematic clash logic)

Required for Phase 2 Halo calculations where high-temperature services may grow into adjacent pipe envelopes during operation. Expansion direction determines which axis the Halo buffer must be extended on.

```
https://www.engineersedge.com/heat_transfer/thermal_expansion_of_metal_pipe_15701.htm
```
Thermal expansion of metal pipe with coefficient table and design guidelines. Includes anchor force calculations and the case for never anchoring a straight steel run at both ends.

```
https://www.engineersedge.com/heat_transfer/thermal_expansion_or_contraction_of_piping_16234.htm
```
Thermal expansion per ASME B31.8 with coefficient for carbon and low alloy steels: 6.5×10⁻⁶ in/in/°F (1.17×10⁻⁵ cm/cm/°C). Includes temperature-specific expansion table.

```
https://www.engineersedge.com/materials/coefficients_linear_thermal_expansion_13165.htm
```
Coefficients of linear thermal expansion for a broad range of engineering materials. Primary lookup table for BIMGUARD's kinematic clash module.

```
https://www.engineersedge.com/calculators/pipe_expansion_thermal_loop_15035.htm
```
Pipe expansion loop equations and calculator. Provides the formula for loop width and height sizing — relevant to Halo buffer direction on high-temperature runs.

```
https://www.piping-world.com/thermal-expansion
```
Full thermal expansion coefficient table up to 300°C for all common pipe materials including carbon steel, stainless steel 304/316, copper, CPVC, and PVC.

```
https://amesweb.info/Materials/Linear-Thermal-Expansion-Coefficient-Metals.aspx
```
CTE table in both 10⁻⁶/°C and 10⁻⁶/°F with inline calculator. Covers stainless 304, stainless 316, carbon steel, aluminium, copper, titanium, brass, and Invar.

---

## Module 6 — Galvanic corrosion (Phase 3 material gate)

These sources provide the electrochemical data that drives Phase 3 of the BIMGUARD compliance engine — the galvanic gate. BIMGUARD's GC-001 ruleset uses voltage gap thresholds from NASA-STD-6012 applied against the galvanic series data in these sources.

```
https://www.engineersedge.com/galvanic_capatability.htm
```
Galvanic series from ASTM with anodic index voltage values and compatibility rules by environment class: harsh (0.15V max), normal (0.25V max), controlled (0.50V max). Primary voltage threshold reference for GC-001.

```
https://structx.com/Material_Properties_001.html
```
Electrochemical series chart with voltage ranges in flowing seawater at 2.5–4 m/s, 5–30°C. Includes colour-coded compatibility matrix for rapid pairwise assessment.

```
https://industrialmetalservice.com/metal-university/avoid-long-term-problems-with-our-galvanic-corrosion-chart/
```
Galvanic corrosion chart focused on construction and industrial metals: stainless steel, aluminium, copper, zinc, galvanised steel. Includes worked examples relevant to MEP assemblies.

```
https://www.corrosionpedia.com/an-introduction-to-the-galvanic-series-galvanic-compatibility-and-corrosion/2/1403
```
Detailed explanation of anodic index, area ratio effects, and prevention strategies. Academic-quality source suitable for thesis referencing. Covers the three conditions required for galvanic corrosion: dissimilar metals, electrolyte, and conductive path.

---

## Module 7 — IFC 4.3 schema (BIM data structure)

These sources define exactly where BIMGUARD looks for data inside an IFC file. Every Pset reference in the BIMGUARD codebase traces back to the official buildingSMART schema documentation.

```
https://ifc43-docs.standards.buildingsmart.org/
```
Official IFC 4.3.2 live documentation — the primary schema reference. Auto-generated from the latest published XMI. Covers all entities, property sets, quantity sets, and concept templates.

```
https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcPipeSegment.htm
```
IfcPipeSegment entity definition with inheritance hierarchy, property sets (Pset_PipeSegmentOccurrence), quantity sets, material profile set usage, and port nesting. Direct reference for BIMGUARD's IFC parser module.

```
https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/toc.html
```
Full IFC 4.3 table of contents. Covers all HVAC domain entities including IfcPipeFitting, IfcValve, IfcDuctSegment, IfcCovering, IfcDistributionSystem, and all associated Psets.

```
https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/
```
Official ISO-submitted static publication of IFC 4.3. The version as submitted to ISO — use this for academic citation as it carries the ISO publication status.

---

## Module 8 — ISO 19650 and BIM governance

These sources define the information management framework within which BIMGUARD operates. Phase 5 of BIMGUARD maps its output directly onto ISO 19650 status codes and information container workflow states.

```
https://imiframework.org/resources/
```
UK IMI Framework — full suite of ISO 19650 guidance parts A through F, freely downloadable. Covers information management function, appointing party requirements, delivery team requirements, developing information requirements, tendering and appointments, and security.

```
https://www.e-zigurat.com/en/blog/understanding-iso-19650-guide/
```
Clear explanation of all five parts of ISO 19650 with BIM clash detection context. Accessible academic-quality overview suitable for thesis background reading.

```
https://theaecassociates.com/blog/bim-standards-iso-19650/
```
ISO 19650 and BIM clash detection workflows, CDE platform context, and certification requirements. Covers structured data exchange and quality control processes.

```
https://www.iso.org/standard/68078.html
```
ISO 19650-1 official standard page. Scope, abstract, and publication details. Use for formal academic citation of the standard itself.
