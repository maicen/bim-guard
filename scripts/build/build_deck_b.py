"""Deck B — Blue Halo Clearance Algorithm (24 slides)."""
try:
    from build_fmp_decks import *  # noqa: F403
except ImportError:
    from scripts.build.build_fmp_decks import *  # noqa: F403

def build():
    p = new_deck()

    title_slide(p, "Blue Halo Clearance Algorithm",
        "Seismic Bracing Proactive Space Reservation",
        "EN 1998-1  ·  DIN 4149  ·  ASCE 7-22  ·  NFPA 13  ·  SMACNA  ·  MSS SP-58",
        "BH-001  ·  LOD 300 → 350 space reservation  ·  Pluggable jurisdiction configs  ·  BCF 2.1 output")

    s = slide(p, "The problem in the design cycle", "Space for supports is designed after the space is gone", RED)
    cards(s, [
        ("LOD 300 — services routed", "Pipes, ducts and conduit are modelled to their own envelope. The support system does not exist yet, so nothing reserves room for it.", CYAN),
        ("LOD 350 — supports designed", "Hangers and sway braces are added. They need a diagonal leg and a base footprint that the surrounding services have already occupied.", BLUE),
        ("Result — rework, not clash", "The clash is real but late. Rerouting a duct run at LOD 350 costs an order of magnitude more than shifting a pipe at LOD 300, and it lands on the programme.", RED),
        ("Blue Halo — reserve first", "Compute the support envelope at LOD 300 and publish it as a reserved volume. The conflict surfaces while services are still cheap to move.", GREEN)], h=0.88, gap=0.12)

    s = slide(p, "How the clearance envelope is derived", "Jurisdiction-driven, not hard-coded", NAVY)
    formula(s, "halo_bbox  =  element_bbox  ⊕  effective_clearance",
            note="⊕ is a uniform expansion on every face. effective_clearance is read from the jurisdiction config, never from code.")
    formula(s, "effective_clearance  =  base_clearance  +  seismic_zone_addition  +  hospital_addition",
            y=2.50, note="EN 1998-1:2020 + DIN 4149:2022 resolve to 200 mm base; ASCE 7-22 + NFPA 13 resolve to 457.2 mm (18 in).")
    note(s, "The implementation applies a uniform buffer because that is what the corpus can support. Angle-aware wedge envelopes for diagonal cable and rod bracing are deferred: the corpus carries no brace geometry to validate them against, and an unvalidated wedge would be a guess wearing a formula.", y=3.75)

    s = slide(p, "Four-phase architecture", "Each phase fails independently and reports why", BLUE)
    table(s, ["Phase", "Function", "Input", "Output"],
        [["1", "Geometry normalisation", "Any IFC representation type", "World-coordinate bounding boxes, mm"],
         ["2", "Halo generation", "Element bbox + jurisdiction rule", "Expanded clearance envelope per element"],
         ["3", "Spatial indexing", "All candidate geometries", "Uniform grid, cell-bucketed"],
         ["4", "Collision detection", "Halo + indexed candidates", "ClashReport per intersection, severity banded"]],
        widths=[0.8, 2.6, 3.0, 3.1], row_h=0.34)
    note(s, "Separation matters for diagnosis: a model that yields no halos has failed Phase 1, and the run says so rather than reporting zero conflicts as a clean result.", y=3.15)
    note(s, "Measured on the corpus: Phase 1 resolved geometry for 49,736 of 49,736 MEP elements — 100%.", y=4.00, bold=True)

    s = slide(p, "Phase 1 — geometry normalisation", "The phase that decides whether anything else can run", CYAN)
    columns(s, [("Why it is not trivial",
        "Real exports overwhelmingly use IfcMappedItem and IfcFacetedBrep. A fast vertex reader handling only tessellated sets, polylines and swept solids resolves none of them — measured at 0 of 87 elements on the AISC steel models.", RED),
        ("What the harness does",
         "Evaluates real geometry through ifcopenshell.geom's multithreaded iterator, which handles every representation type, then converts to axis-aligned boxes in millimetres.", CYAN),
        ("Two settings that decide correctness",
         "use-world-coords must be set, or every element returns in local coordinates near the origin and everything appears to clash. The iterator emits SI metres regardless of declared file units, so results scale by 1000.", NAVY)])
    note(s, "Verified against a fixture whose true extents are known exactly, so the unit handling is checked rather than assumed.", bold=True)

    s = slide(p, "Phase 2 — halo generation", "Deterministic, and traceable to a clause", BLUE)
    cards(s, [
        ("Read the rule, not a constant", "The brace variant selects a ClearanceRule from the loaded jurisdiction config. Base clearance, spacing and angle limits all come from the pack.", CYAN),
        ("Expand uniformly", "The element bounding box grows by the effective clearance on every face, producing an axis-aligned envelope in millimetres.", BLUE),
        ("Record what produced it", "Each HaloVolume carries the rule variant, the clearance applied and the flags that modified it, so a volume can be traced back to the standard clause.", NAVY),
        ("Immutable with respect to source", "The original element geometry is never mutated; the halo is a separate object keyed by GlobalId.", GREEN)], h=0.88, gap=0.12)

    s = slide(p, "Phase 3 — spatial indexing", "Why brute-force pairing does not finish", NAVY)
    formula(s, "brute force  O(n²)   →   uniform grid  ≈ O(n)  for spatially sparse models",
            note="West Riverside mechanical alone carries 8,732 duct and pipe segments: 76 million pair tests without pre-filtering.")
    columns(s, [("Cell sizing", "Cell edge is the median element extent, floored at four times the clearance, so a halo touches few cells.", CYAN),
                ("Bucketing", "Every candidate bbox is inserted into each cell it overlaps; a halo queries only its own cells.", BLUE),
                ("Exactness preserved", "Results are identical to brute-force pairing. Only the comparisons that could not intersect are removed.", NAVY)], y=2.55, h=1.35)
    note(s, "This is the difference between a sweep that completes in an hour and one that does not complete.", y=4.10, bold=True)

    s = slide(p, "Phase 4 — collision detection and severity", "AABB intersection, banded by overlap fraction", RED)
    formula(s, "overlap_ratio  =  overlap_volume  ÷  halo_volume", y=1.40, h=0.70)
    table(s, ["Band", "Threshold", "Measured across corpus", "Share"],
        [[("Critical", RED, True), "ratio ≥ 0.25", "5,236", "2.34%"],
         [("Major", AMBER, True), "ratio ≥ 0.05", "6,699", "3.00%"],
         [("Minor", GREEN, True), "ratio < 0.05", "211,581", "94.66%"]],
        y=2.30, widths=[1.5, 2.0, 3.2, 1.5], row_h=0.32)
    note(s, "The banding is a spatial heuristic, not a standards-derived threshold — stated as such in Appendix B under threats to validity. Table B.6 shows how sensitive the totals are to the clearance input, which is the stronger reason to treat severity as triage rather than verdict.", y=3.75)

    s = slide(p, "Hospital MEP corridor — brace family comparison", "One element, three candidate supports, one clearance regime", AMBER)
    table(s, ["Brace family", "Clearance", "Halo volume (mm³)", "Conflicts", "Recommendation"],
        [["Angle iron — fire", "200 mm", "688,500,000", "1", "Marginal"],
         ["Angle iron — mechanical", "200 mm", "688,500,000", "1", "Marginal"],
         ["Rod", "200 mm", "688,500,000", "1", "Marginal"],
         [("Cable", GREEN, True), ("200 mm", GREEN, True), ("688,500,000", GREEN, True), ("1", GREEN, True), ("Preferred on footprint", GREEN, True)]],
        widths=[2.6, 1.4, 2.4, 1.2, 2.2], row_h=0.32)
    note(s, "All four variants share one clearance because the EN 1998-1 + DIN 4149 research does not differentiate clearance by brace hardware — a documented data gap in that config, not a property of the building. Where a jurisdiction does differentiate, the comparison separates and the smallest-footprint family wins.", y=3.20)
    note(s, "This is the honest form of the comparison: the method distinguishes families; this jurisdiction's data does not yet let it.", y=4.35, bold=True)

    s = slide(p, "Standards sensitivity — the counter-intuitive result", "Raising the clearance requirement raises findings and lowers severity", RED)
    table(s, ["Clearance", "Jurisdiction", "Clashes", "Critical", "vs 200 mm"],
        [["25 mm", "—", "30,332", "148", "0.29×"],
         ["100 mm", "—", "69,307", "38", "0.67×"],
         [("200 mm", NAVY, True), ("EN 1998-1 + DIN 4149", NAVY, True), ("104,144", NAVY, True), ("31", NAVY, True), ("1.00×", NAVY, True)],
         [("457.2 mm", RED, True), ("ASCE 7-22 + NFPA 13", RED, True), ("172,812", RED, True), ("16", RED, True), ("1.66×", RED, True)],
         ["600 mm", "—", "212,870", "11", "2.04×"]],
        widths=[1.4, 3.2, 1.8, 1.4, 1.4], row_h=0.31)
    note(s, "Adopting the US standard over the European yields 66% more clashes but 48% fewer Critical ones. Severity is an overlap ratio against halo volume, so a larger clearance inflates the denominator faster than the numerator.", y=3.45)
    note(s, "The finding is an argument that the severity heuristic needs rethinking, not retuning. It held on two independent model subsets, at 1.62× and 1.66×.", y=4.40, bold=True)

    s = slide(p, "Validation dataset", "What the algorithm was run against", BLUE)
    metrics(s, [("37 / 38", "models processed\n8 repositories", CYAN),
                ("49,736", "MEP elements\n100% geometry", GREEN),
                ("223,516", "clashes detected\nacross the corpus", NAVY),
                ("37 / 37", "BCF archives\nvalid", BLUE)])
    cards(s, [("Corpus and controls",
        "Hospitals, offices, industrial plant and mixed-use, IFC2x3 and IFC4, from Revit, ArchiCAD and Autodesk toolchains. Two same-building schema twins act as controls: rows 9/14 differ by 0.00% and rows 8/13 by 0.11%, so the result does not depend on the export schema.", GREEN)], y=3.05, h=1.10)

    s = slide(p, "Validation results — tests and integrity", "Every archive parsed, not merely counted", GREEN)
    metrics(s, [("11 / 11", "Blue Halo harness\nchecks passed", GREEN),
                ("8 / 8", "end-to-end IFC\npipeline checks", GREEN),
                ("44 / 44", "HTTP route tests\n(4 known-gap xfail)", CYAN),
                ("100%", "geometry resolution\n49,736 elements", BLUE)])
    cards(s, [("What BCF validity means here",
        "All 37 archives were opened and every XML part parsed: bcf.version and project.bcfp present, one complete topic folder per clash carrying markup.bcf, viewpoint.bcfv and snapshot.png, zero malformed XML. Counting entries would not have established this.", GREEN)], y=3.05, h=1.10)

    s = slide(p, "Performance measured across the corpus", "Where the time actually goes")
    table(s, ["Stage", "Measured", "Complexity", "Note"],
        [["Full sweep, 37 models", "3,594 s", "—", "Download, parse, halo, clash, engines, BCF"],
         ["Mean per model", "≈ 97 s", "—", "Geometry evaluation dominates"],
         ["Largest model", "632 s", "—", "NBU_MedicalClinic, 207 MB, 5,952 MEP"],
         ["Geometry evaluation", "8–95 s per model", "O(n)", "ifcopenshell.geom multithreaded iterator"],
         ["Clash detection", "sub-second to seconds", "≈ O(n)", "Uniform grid; O(n²) without it"],
         ["Smallest MEP model", "4.8 s", "—", "wbdg office, 31 piping elements"]],
        widths=[2.4, 1.9, 1.3, 3.9], row_h=0.30)
    note(s, "Per-model timings are recorded in validation_sweep_summary.json and reproduce on re-run from cache.", y=3.65)

    s = slide(p, "Academic contribution", "What Blue Halo adds", NAVY)
    columns(s, [("Proactive rather than reactive", "Reserving support space at LOD 300 inverts the usual order, in which the support system discovers that its space is already gone.", CYAN),
        ("Jurisdiction as data", "Clearance, spacing and angle limits are loaded from versioned JSON configs, so a new standard is a data addition rather than a code change.", BLUE),
        ("Measured at corpus scale", "100% geometry resolution over 49,736 elements across two IFC schemas and three toolchains, with schema twins as controls.", GREEN),
        ("A quantified sensitivity result", "The clearance-severity inversion is a reproducible finding about the metric itself, not about any one building.", RED)], h=3.10)

    s = slide(p, "Limitations", "Stated plainly", AMBER)
    cards(s, [
        ("Axis-aligned boxes overstate intersection", "A clash is an AABB overlap. Diagonal and non-convex members are over-approximated, so counts are an upper bound, not a defect list.", AMBER),
        ("Uniform buffer, not a brace-shaped envelope", "Real sway braces are diagonal members with a base plate. The wedge envelope is deferred until brace geometry exists to validate against.", AMBER),
        ("Severity is a spatial heuristic", "Overlap fraction of halo volume, not a standards-derived threshold. Table B.6 shows its sensitivity to the clearance input.", RED),
        ("One clearance regime per run", "The EN + DIN config assigns every brace variant the same clearance, so variant comparison is degenerate under that jurisdiction.", AMBER)], h=0.88, gap=0.12)

    s = slide(p, "Post-FMP roadmap", "R1 – R5, with the dependency each carries", BLUE)
    table(s, ["Ref", "Enhancement", "Dependency", "Target"],
        [["R1", "Angle-aware wedge envelope for diagonal bracing", "Brace geometry in the corpus to validate against", "Q1 2027"],
         ["R2", "Non-circular and rectangular halo profiles", "Profile data per brace family", "Q1 2027"],
         ["R3", "Cable sag modelling (catenary)", "Span and pretension inputs", "Q2 2027"],
         ["R4", "Severity model grounded in standards", "Clause basis for a non-ratio metric", "Q2 2027"],
         ["R5", "Seismic zone auto-population from site data", "Hazard map lookup and IFC round-trip", "Q3 2027"]],
        widths=[0.8, 4.4, 3.2, 1.1], row_h=0.31)
    note(s, "R4 is the item the sensitivity result argues for most directly.", y=3.35, bold=True)

    s = slide(p, "Standards compliance", "What each source supplies", NAVY)
    table(s, ["Standard", "Supplies", "Applied in"],
        [["EN 1998-1:2004+A2:2011", "Seismic restraint of non-structural elements", "Clearance and spacing, EU config"],
         ["DIN 4149:2005-04", "German regional seismic provisions", "Merged into the EU jurisdiction config"],
         ["ASCE 7-22", "US seismic design provisions", "US fallback config, 457.2 mm"],
         ["NFPA 13", "Sprinkler bracing and spacing", "US fallback config, fire systems"],
         ["SMACNA / MSS SP-58", "Sway bracing and hanger support practice", "Brace family footprints"],
         ["ISO 16739-1 / BCF 2.1", "IFC schema and issue exchange", "Input parsing and topic output"]],
        widths=[2.9, 3.5, 3.1], row_h=0.30)
    note(s, "Configs are generated from the research summary by script and carry their own data-gap list, so every value is either sourced or flagged as absent.", y=3.65)

    s = slide(p, "Jurisdiction as data, not as code", "How a new standard enters the system", GREEN)
    table(s, ["Config field", "EN 1998-1 + DIN 4149", "ASCE 7-22 + NFPA 13", "Resolution rule"],
        [["base_from_structure_mm", "200.0", "457.2", "Larger clearance governs"],
         ["spacing_transverse_m", "1.0", "1.016", "Tighter spacing governs"],
         ["pipe_diameter_mm", "63.0", "63.5", "Lower threshold governs"],
         ["angle range (deg)", "40 – 65", "30 – 60", "Intersection of both ranges"],
         ["hospital_addition_mm", ("0 — data gap", RED, False), ("0 — data gap", RED, False), "Absent from source research"]],
        widths=[2.6, 2.4, 2.3, 2.2], row_h=0.31)
    note(s, "Configs are generated from the standards research by script, never hand-edited. Each carries its own data-gap list, so a value that the source did not supply is flagged rather than invented — the hospital clearance addition above is recorded as absent rather than guessed.", y=3.30)
    note(s, "Adding a jurisdiction is a data change with a provenance record, not a code change.", y=4.35, bold=True)

    s = slide(p, "Integration into the compliance pipeline", "Where Blue Halo sits", BLUE)
    cards(s, [
        ("Input", "Normalised IFC geometry and property sets, plus the jurisdiction clearance config selected for the project.", CYAN),
        ("Output", "One BCF 2.1 topic per breach, carrying both GlobalIds, overlap volume, severity band and the clearance rule that produced the envelope.", BLUE),
        ("Model write-back", "Pset_HaloReservation on the braced element: brace type, rule variant, clearance applied, element and halo bounding boxes.", GREEN),
        ("Status", "Breaches present hold the container at S2. Resolution is either a service move or an accepted LOD 350 reservation recorded against the element.", NAVY)], h=0.88, gap=0.12)

    s = slide(p, "BCF output — what a reviewer receives", "Enough to act without opening the tool", NAVY)
    table(s, ["Field", "Content", "Source"],
        [["Topic title", "Brace type and source element class", "HaloVolume.brace_type"],
         ["Description", "Both GlobalIds, overlap volume in mm³, ratio", "ClashReport.description"],
         ["Priority", "Critical / Major / Minor", "Severity band"],
         ["Due date", "2, 7 or 21 days by severity", "Banding table"],
         ["Viewpoint", "Camera and component selection on the clash", "viewpoint.bcfv"],
         ["Labels", "blue_halo, seismic_bracing, brace type", "Topic labels"]],
        widths=[1.9, 4.2, 3.4], row_h=0.30)
    note(s, "37 of 37 archives validated: every part well-formed, every topic folder complete.", y=3.65, bold=True)

    s = slide(p, "Comparison to current practice", "The same conflict, found at two different prices", RED)
    columns(s, [("Reactive — today",
        "Model services at LOD 300. Design supports at LOD 350. Run clash detection. Discover the support has no room. Reroute services that are already coordinated, re-issue, re-review.", RED),
        ("Proactive — Blue Halo",
         "Model services at LOD 300. Compute the support envelope from the jurisdiction rule. Publish it as a reserved volume. Conflicts surface while services are still cheap to move.", GREEN),
        ("What changes",
         "Not the conflict — the timing. The same geometric fact is surfaced one design stage earlier, before the coordination effort that makes it expensive to undo.", NAVY)])
    note(s, "The corpus cannot price this: cost avoidance depends on project commercials the models do not carry. What it does establish is that the detection works at scale.", bold=True)

    s = slide(p, "RQ2 — the spatial component answered", "Can proactive reservation work on real federated models?", CYAN)
    metrics(s, [("YES", "demonstrated across\n37 models", GREEN),
                ("100%", "geometry resolution\nno fallback needed", CYAN),
                ("0.00% / 0.11%", "schema twin\ndeltas", BLUE),
                ("223,516", "clashes detected\nand exported", NAVY)])
    cards(s, [("What the evidence supports",
        "Halo generation and clash detection are deterministic, schema-independent and scale to the largest models in the corpus. What the corpus cannot yet support is brace-family differentiation, because the jurisdiction data does not distinguish clearance by hardware. The method is validated; that particular comparison is not.", CYAN)], y=3.05, h=1.10)

    s = slide(p, "Key findings", "What the corpus established", BLUE)
    cards(s, [
        ("Geometry is not the obstacle", "100% resolution across both IFC schemas and three authoring toolchains, using the full geometry iterator rather than a vertex shortcut.", GREEN),
        ("The result is schema-independent", "Same-building twins in IFC2x3 and IFC4 produced identical and near-identical clash counts — 0.00% and 0.11% apart.", CYAN),
        ("Clearance choice dominates the outcome", "A 2× clearance change moves total clashes by 2× and Critical count in the opposite direction. Jurisdiction selection is the most consequential input.", RED),
        ("Severity needs a standards basis", "Overlap ratio is defensible as triage and indefensible as a verdict. R4 addresses it.", AMBER)], h=0.88, gap=0.12)

    closing(p, "Blue Halo Clearance Algorithm", "Questions?")

    out = OUT_DIR / "BIMGUARD_FMP_B_Blue_Halo.pptx"
    p.save(str(out))
    return out

if __name__ == "__main__":
    print(f"  {build()}")
