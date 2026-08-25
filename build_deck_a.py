"""Deck A — Galvanic Corrosion Engine (24 slides)."""
from build_fmp_decks import *  # noqa: F403

def build():
    p = new_deck()

    title_slide(p, "Galvanic Corrosion Engine",
        "Detecting Material Incompatibility in MEP Building Services",
        "NASA-STD-6012  ·  WorldStainless  ·  IMOA Design Manual  ·  AUCSC 2024",
        "GC-001  ·  22-material electrochemical series  ·  7 environment classes  ·  PREN adequacy")

    s = slide(p, "Why galvanic corrosion matters", "A predictable, preventable failure mode that no BIM tool checks")
    columns(s, [
        ("The electrochemical process",
         "Two dissimilar metals in electrical contact, bridged by an electrolyte, form a cell. The less noble metal becomes the anode and corrodes preferentially. Rate scales with the potential gap between them and with the cathode-to-anode area ratio.", CYAN),
        ("Real-world consequences",
         "Perforation of the anodic member, typically at the joint, long before design life. Field remediation runs 6–10× the cost of the design-stage specification change that would have prevented it, and arrives with programme delay attached.", RED),
        ("The standard gap",
         "Clash detection resolves geometry, not chemistry. Two touching elements of incompatible material are a valid clash-free model. No mainstream BIM tool interrogates material pairing at the joint.", AMBER)])
    note(s, "GC-001 asks the question the geometry cannot: given what these two elements are made of, and where they sit, will one consume the other?", bold=True)

    s = slide(p, "Three research questions", "The academic scope that frames this engine", BLUE)
    cards(s, [
        ("RQ1  —  Detection from existing IFC data",
         "Can corrosion risk in MEP building services be reliably identified from the material, spatial and zone metadata already present in an IFC model at LOD 300, without additional modelling effort?", CYAN),
        ("RQ2  —  Dual-mechanism simultaneous checking",
         "Can galvanic and crevice corrosion be evaluated in the same pass, such that each reports the failures the other cannot see, rather than collapsing into one combined score?", BLUE),
        ("RQ3  —  OpenBIM cross-platform deployment",
         "Can a compliance checker operating purely on IFC input and BCF output work across authoring tools without vendor plugins or proprietary APIs?", NAVY)])

    s = slide(p, "The 22-material electrochemical series", "Ordered noble to active; the gap between any pair drives the risk")
    table(s, ["Material", "Potential (mV SCE)", "PREN", "Environment suitability"],
        [["Platinum", "+250", "—", "Inert; laboratory service only"],
         ["Titanium Gr 2", "−100", "—", "All classes including E7 coastal"],
         [("SS316 / 1.4401", NAVY, True), ("−50", NAVY, True), ("25.2", NAVY, True), ("E1–E4; marginal above E5", NAVY, True)],
         ["SS304 / 1.4301", "−80", "18.6", "E1–E2 only; pits in chloride"],
         ["Copper C12200", "−350", "—", "E1–E4; avoid coupling to steel"],
         ["Bronze / gunmetal", "−400", "—", "E1–E4 valve bodies"],
         ["Carbon steel", "−600", "—", "E1–E2 dry only; coat otherwise"],
         ["Galvanised steel", "−980", "—", "Sacrificial; reverses above 60 °C"],
         ["Zinc", "−1030", "—", "Anode material, not a service metal"],
         ["Magnesium", "−1600", "—", "Sacrificial anode only"]],
        widths=[2.6, 2.1, 1.3, 3.5], row_h=0.29)
    note(s, "Full series holds 22 entries. Risk rises with separation: copper against carbon steel is a 250 mV gap; copper against galvanised steel is 630 mV.", y=4.75)

    s = slide(p, "Seven environment classes", "Each multiplies the base electrochemical risk", BLUE)
    table(s, ["Class", "Name", "Description", "Multiplier", "Example location"],
        [["E1", "Controlled indoor", "Conditioned, RH < 45%", "0.8×", "Office ceiling void"],
         ["E2", "Heated indoor", "Conditioned, RH 45–60%", "1.0×", "Riser cupboard"],
         ["E3", "Humid indoor", "Intermittent condensation", "1.2×", "Plant room, laundry"],
         ["E4", "Outdoor sheltered", "No direct rain, ambient RH", "1.4×", "Covered walkway"],
         ["E5", "Outdoor exposed", "Direct wetting, UV", "1.6×", "Roof plant"],
         [("E6", NAVY, True), ("Coastal", NAVY, True), ("Airborne chloride < 5 km", NAVY, True), ("1.7×", NAVY, True), ("Seafront plant deck", NAVY, True)],
         ["E7", "High-corrosivity", "Process chemical, pool hall", "1.8×", "Pool plant, dosing room"]],
        widths=[0.8, 2.0, 2.7, 1.1, 2.9], row_h=0.30)
    note(s, "Class is inferred from IFC spatial containment — space name, storey and zone — and recorded on the finding so the inference is auditable.", y=4.75)

    s = slide(p, "PREN: Pitting Resistance Equivalent Number", "Whether a stainless grade suits the environment it sits in", NAVY)
    formula(s, "PREN  =  %Cr  +  3.3 × %Mo  +  16 × %N",
            note="IMOA Design Manual. Higher PREN resists chloride pitting; the threshold rises with environment severity.")
    table(s, ["Environment", "Minimum PREN", "Grade required", "Rationale"],
        [["E1 – E2", "≥ 18", "SS304 (18.6)", "Dry, low chloride; austenitic adequate"],
         ["E3 – E4", "≥ 25", "SS316 (25.2)", "Molybdenum needed against condensation"],
         ["E5 – E7", "≥ 32", "Duplex 2205 (35.0)", "Chloride loading exceeds 316 capacity"]],
        y=2.60, widths=[1.9, 1.7, 2.4, 3.5], row_h=0.32)
    note(s, "A PREN shortfall is reported separately from the galvanic couple: the same SS316 flange can be galvanically clean and still be the wrong grade for E6.", y=4.20)

    s = slide(p, "The GC-001 scoring model", "Three weighted terms, one composite band", BLUE)
    formula(s, "Score_GC  =  (0.50 × voltage risk)  +  (0.30 × area ratio risk)  +  (0.20 × environment)")
    columns(s, [("Voltage risk  0.50", "Normalised potential gap between the coupled materials. The dominant term because it sets whether a cell forms at all.", CYAN),
                ("Area ratio  0.30", "Cathode area over anode area. A small anode against a large cathode concentrates current density and perforates fastest.", BLUE),
                ("Environment  0.20", "The E1–E7 multiplier. Modifies severity; never creates a finding where no couple exists.", NAVY)], y=2.45, h=1.30)
    table(s, ["Band", "Range", "Action"],
        [[("Low", GREEN, True), "< 0.35", "Record only; no BCF issue raised"],
         [("Medium", AMBER, True), "0.35 – 0.65", "BCF issue, design review"],
         [("High", RED, True), "0.65 – 0.85", "BCF issue, mitigation required"],
         [("Critical", RED, True), "> 0.85", "BCF issue, redesign before fabrication"]],
        y=3.90, widths=[1.4, 1.8, 6.3], row_h=0.26)

    s = slide(p, "How GC-001 reads the IFC model", "Inputs, computation and outputs")
    columns(s, [
        ("What it queries",
         "IfcPipeSegment, IfcDuctSegment and fittings; material via IfcRelAssociatesMaterial; Pset_PipeSegmentOccurrence for diameter and wall thickness; Pset_CoveringCommon for insulation; spatial containment for environment class; joint adjacency for the couple.", CYAN),
        ("What it computes",
         "Normalises free-text material to a canonical key; resolves the adjacent element at each joint; derives the potential gap; computes cathode-to-anode area ratio from geometry; applies the environment multiplier; produces the weighted composite.", BLUE),
        ("What it writes",
         "A BCF 2.1 topic per finding with viewpoint and camera on the joint; Pset_CorrosionRisk written back to the flagged element carrying mechanism, score, environment class and mitigation; a row in the machine-readable asset register.", NAVY)])
    note(s, "Every threshold applied is carried in the versioned ruleset, so a finding can be traced to the clause that produced it.", bold=True)

    s = slide(p, "Case study 1 — plant room valve assembly", "SS316 isolation valve against 304SS flex hose, humid chemical plant", AMBER)
    metrics(s, [("20 mV", "potential gap\nSS316 to SS304", CYAN),
                ("4.2 : 1", "cathode-to-anode\narea ratio", BLUE),
                ("E3", "humid indoor\n1.2× multiplier", AMBER),
                ("0.52", "GC-001 composite\nMEDIUM band", AMBER)])
    cards(s, [("Finding and mitigation",
        "A 20 mV gap is small, but the area ratio concentrates current on the hose. Specify a dielectric union at the transition, or bring both members to a single grade. Design-stage change £2,400 against £18,000 for field replacement with the plant shut down.", AMBER)], y=3.05, h=1.10)

    s = slide(p, "Case study 2 — hospital riser support", "Copper pressure tubing bonded to a carbon steel clamp", RED)
    metrics(s, [("520 mV", "potential gap\nCu to carbon steel", RED),
                ("18 : 1", "cathode-to-anode\narea ratio", RED),
                ("E2", "heated indoor\n1.0× multiplier", BLUE),
                ("0.79", "GC-001 composite\nHIGH band", RED)])
    cards(s, [("Finding and mitigation",
        "Copper is strongly cathodic to steel and the clamp is the small anode. Perforation initiates at the clamp contact, inside a wall, above a ward. Specify a plastic-lined clamp or a nylon isolating washer: £800 at design against £6,000-plus for access, replacement and making good.", RED)], y=3.05, h=1.10)

    s = slide(p, "Validation approach", "What the engine was run against", BLUE)
    metrics(s, [("37 / 38", "IFC models processed\n(1 unsupported schema)", CYAN),
                ("8", "independent public\nrepositories", BLUE),
                ("116,006", "piping elements\nscored", NAVY),
                ("49,736", "MEP elements with\nresolved geometry", GREEN)])
    cards(s, [("Corpus composition and method",
        "Hospitals, commercial offices, industrial plant and mixed-use models, in IFC2x3 and IFC4, exported from Revit, ArchiCAD and Autodesk toolchains. Each model is downloaded, parsed, scored by every engine and exported to BCF. The one failure is IFC2X2_FINAL, which IfcOpenShell does not support.", CYAN)], y=3.05, h=1.10)

    s = slide(p, "Validation results — what was measured", "Engine coverage against real third-party models", RED)
    table(s, ["Engine", "Elements flagged", "Flag rate", "Elements with all required inputs", "Coverage"],
        [[("GC-001", NAVY, True), ("0 of 116,006", RED, True), ("0.0%", RED, True), "8", "0.007%"],
         ["CC-001", "116,006 of 116,006", "100.0%", "0", "0.000%"],
         ["MC-001", "116,006 of 116,006", "100.0%", "0", "0.000%"],
         ["MM-001", "unavailable on 24 models", "—", "15", "0.013%"],
         ["XM-001", "unavailable on 24 models", "—", "0", "0.000%"]],
        widths=[1.3, 2.5, 1.2, 2.8, 1.7], row_h=0.30)
    note(s, "A 0% and two 100% flag rates are properties of input availability, not of the buildings. Where required inputs are absent the coercers substitute a default, so the engine scores the default uniformly. Recorded in thesis §13.9 and Appendix B, Table B.4.", y=3.30)
    note(s, "No precision or recall figure is claimed: with coverage below 0.02% there is no population against which either could be computed.", y=4.40, bold=True)

    s = slide(p, "Performance measured across the corpus", "Wall-clock cost of a full sweep")
    table(s, ["Metric", "Measured value", "Note"],
        [["Total sweep", "3,594 s for 37 models", "Download, parse, halo, clash, engines, BCF"],
         ["Mean per model", "≈ 97 s", "Dominated by geometry evaluation"],
         ["Largest model", "632 s — NBU_MedicalClinic", "207 MB multi-discipline archive"],
         ["Smallest MEP model", "4.8 s — wbdg office", "31 piping elements"],
         ["Geometry resolution", "49,736 of 49,736 (100%)", "ifcopenshell.geom, world coordinates"],
         ["Bottleneck", "Geometry evaluation, then clash", "Spatial grid reduces O(n²) pairing"]],
        widths=[2.3, 3.1, 4.1], row_h=0.30)
    note(s, "Measured on this corpus, not estimated. Timings are per-model records in validation_sweep_summary.json.", y=3.65)

    s = slide(p, "Academic contribution", "What this work adds", NAVY)
    columns(s, [("Method, not just result",
        "A documented, reproducible method for interrogating electrochemical risk from IFC metadata alone, with every threshold traceable to a cited standard clause.", CYAN),
        ("Quantified data gap",
         "The corpus measures how far real federated models fall short of what a corrosion assessment needs: 38,012 of 116,006 elements carry material text, and only 2,403 normalise to a scoreable key.", RED),
        ("White-box auditability",
         "Every finding names the clause, the threshold and the inference that produced it, so a reviewer can disagree with the conclusion on the evidence rather than on trust.", NAVY),
        ("Golden Thread integration",
         "Findings persist into the model as Pset data and into the CDE as BCF topics with ISO 19650 status codes.", GREEN)], h=3.10)

    s = slide(p, "Limitations", "Stated plainly", AMBER)
    cards(s, [
        ("Binary risk, not current magnitude", "The composite ranks risk; it does not compute galvanic current density or metal loss rate. That needs Faraday's law and an electrolyte conductivity model.", AMBER),
        ("Static environment class", "One class per element for the model's life. Seasonal humidity swings and commissioning-stage wetting are not represented.", AMBER),
        ("No time-to-failure prediction", "The engine does not estimate when perforation occurs; that requires corrosion-rate data beyond the IFC.", AMBER),
        ("Dependent on material specification", "Where material is absent or unmappable, the element is reported as a data-quality issue rather than scored. On this corpus that is the majority case.", RED)], h=0.88, gap=0.12)

    s = slide(p, "Post-FMP roadmap", "R1 – R4, with the dependency each carries", BLUE)
    table(s, ["Ref", "Enhancement", "Dependency", "Target"],
        [["R1", "Galvanic current modelling (Faraday's law)", "Electrolyte conductivity per environment", "Q2 2027"],
         ["R2", "Time-to-perforation calculator", "Corrosion-rate dataset, ASTM G48 basis", "Q2 2027"],
         ["R3", "Material library expansion beyond 22 entries", "Normaliser rule table widening", "Q1 2027"],
         ["R4", "BMS integration for live environment class", "Sensor feed and IFC round-trip", "Q3 2027"]],
        widths=[0.8, 4.2, 3.4, 1.1], row_h=0.32)
    note(s, "R3 is the highest-value item on the measured evidence: 35,609 elements carry material text the normaliser cannot map, so widening the rule table converts unusable text into scoreable input.", y=3.20, bold=True)

    s = slide(p, "Standards compliance", "Every threshold traces to a cited source", NAVY)
    table(s, ["Standard", "What it supplies", "Where it is applied"],
        [["NASA-STD-6012", "Galvanic couple voltage thresholds", "Voltage risk term, band boundaries"],
         ["WorldStainless / Euro Inox", "Electrochemical series, corrosion data", "22-material potential table"],
         ["IMOA Design Manual", "PREN formula and grade selection", "PREN adequacy check"],
         ["AUCSC Basic Corrosion Course", "Electrolyte conductivity, area-ratio effect", "Area ratio risk term"],
         ["ISO 16739-1", "IFC schema", "Element, material and spatial queries"],
         ["buildingSMART BCF 2.1", "Issue exchange format", "Topic, viewpoint and snapshot output"]],
        widths=[2.7, 3.6, 3.2], row_h=0.30)
    note(s, "All are carried in the versioned ruleset rather than embedded in code, so a threshold change is a reviewable data change.", y=3.65)

    s = slide(p, "Working alongside CC-001", "Why two engines, not one combined score", BLUE)
    cards(s, [
        ("They run independently", "Each engine evaluates its own mechanism against its own ruleset. Neither can suppress the other's finding.", CYAN),
        ("They emit separate BCF topics", "Different mechanisms need different mitigations. A dielectric union does not fix a crevice, and a weld prep does not fix a couple.", BLUE),
        ("Combined band is the higher of the two", "Reported for triage only. The underlying findings remain distinct and separately actionable.", NAVY),
        ("Worked example — SS316 flange, pool plant", "Galvanically clean at 0.00: a single material, no couple, nothing for GC-001 to see. Crevice band 0.89 Critical: chloride under the gasket face at E7. One element, one engine silent, the other decisive.", RED)], h=0.88, gap=0.12)

    s = slide(p, "Asset register output", "The machine-readable compliance record")
    table(s, ["GlobalId", "Material", "GC", "CC", "Combined", "Cost £", "Days"],
        [["0NZ34oqSTTyBSJPT5Cw1AX", "Copper_C12200", "0.79", "0.12", ("HIGH", RED, True), "800", "0"],
         ["1h8Om82ovOQwaLzjgOtw0y", "CarbonSteel", "0.79", "0.34", ("HIGH", RED, True), "800", "0"],
         ["0CCaRDl7PGav91kwXZIizp", "SS316", "0.00", "0.89", ("CRITICAL", RED, True), "3,200", "4"],
         ["0ofHWhBlHI7wRekoFS0Xtk", "GalvanisedSteel", "0.52", "0.41", ("MEDIUM", AMBER, True), "2,400", "2"],
         ["2aA0fSFYDE6hf08n4QlwRz", "SS304", "0.18", "0.22", ("LOW", GREEN, True), "0", "0"]],
        widths=[2.9, 1.9, 0.7, 0.7, 1.4, 1.0, 0.6], row_h=0.30)
    note(s, "GlobalIds are real, drawn from the synthetic hospital MEP fixture. Scores are illustrative of the banding, not measured findings — on this corpus GC-001 produced none.", y=3.65)

    s = slide(p, "Pset write-back — creating the Golden Thread", "The finding travels with the model, not beside it", GREEN)
    columns(s, [("Written to the element", "Pset_CorrosionRisk is attached to every flagged element, so the risk is carried by the object rather than by a report that can be separated from it.", GREEN),
                ("What it carries", "Mechanism, composite score, risk band, environment class, the governing clause and the recommended mitigation.", CYAN),
                ("Why it persists", "It survives export, federation and hand-over between phases, because it is model data rather than an attachment.", BLUE),
                ("Who can audit it", "Any IFC-capable reader. No BIMGUARD installation is needed to inspect the evidence under the Building Safety Act.", NAVY)], h=3.10)

    s = slide(p, "ISO 19650 status mapping", "How a finding moves through the CDE", NAVY)
    table(s, ["Code", "State", "Trigger", "Exit condition"],
        [["S2", "Work in progress", "Any unresolved High or Critical finding", "Mitigation applied and re-run clean"],
         ["S4", "Shared for review", "Medium findings present; NCR raised", "Reviewer accepts or rejects the risk"],
         [("A", GREEN, True), ("Approved", GREEN, True), "All engines pass, or residual risk accepted", "Released for fabrication"]],
        widths=[0.9, 2.2, 3.6, 2.8], row_h=0.32)
    note(s, "The status code is written into the BCF topic and the CDE container, so the compliance state is visible to the workflow rather than held in the tool.", y=2.70)
    note(s, "This is what makes the output an audit trail rather than a report: the state is machine-readable and the transition is recorded.", y=3.50, bold=True)

    s = slide(p, "RQ1 — answered", "Can corrosion risk be detected from IFC data alone?", CYAN)
    metrics(s, [("YES", "with a material\nspecification present", GREEN),
                ("100%", "geometry resolution\n49,736 elements", CYAN),
                ("2.07%", "elements with a\nscoreable material", RED),
                ("37 / 38", "models processed\nend to end", BLUE)])
    cards(s, [("The qualified answer",
        "The method works: where an element carries a mappable material and a resolvable neighbour, the couple is detected and scored deterministically. The constraint is not the method but the corpus — real federated models rarely carry the inputs. That measurement is itself the contribution, and it is what separates a demonstrated method from a deployed one.", CYAN)], y=3.05, h=1.10)

    s = slide(p, "Key findings", "What the corpus established", BLUE)
    cards(s, [
        ("The pairing logic is sound where it can run", "Given material on both sides of a joint, the voltage gap, area ratio and environment multiplier produce a deterministic, reviewable band.", CYAN),
        ("PREN adequacy is a separate and useful check", "It catches the specification error that galvanic scoring cannot see: the right material, wrongly placed.", BLUE),
        ("Material data, not algorithm, is the limiting factor", "38,012 of 116,006 elements carry material text; 2,403 normalise. Widening the normaliser is worth more than refining the score.", RED),
        ("OpenBIM held across the corpus", "IFC2x3 and IFC4, three authoring toolchains, no vendor API. Same-building schema twins differed by 0.11% and 0.00%.", GREEN)], h=0.88, gap=0.12)

    closing(p, "Galvanic Corrosion Engine", "Questions?")

    out = OUT_DIR / "BIMGUARD_FMP_A_Galvanic_Corrosion.pptx"
    p.save(str(out))
    return out, len(p.slides.__iter__.__self__._sldIdLst)

if __name__ == "__main__":
    out, n = build()
    print(f"  {out}  ({n} slides)")
