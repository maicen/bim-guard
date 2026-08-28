"""Deck C — Architectural Code Analysis Engine: specification and design (24 slides).

Framed as a design proposal, not validated results: no ARCH engine exists in
the codebase. A search for AR-001 through AR-006 returns nothing, and the
route layer contains no architectural rule module. The brief's accuracy
figures ("12 models, 84-100%") are therefore not reproduced — there is
nothing that could have produced them. The ruleset itself is preserved in
full as the designed specification, with implementation status stated on
every slide that would otherwise imply a measurement.
"""
from build_fmp_decks import *  # noqa: F403

def build():
    p = new_deck()

    title_slide(p, "Architectural Code Analysis",
        "Building Envelope and Spatial Compliance — Specification and Design",
        "IBC  ·  ADA  ·  EN 17210  ·  ASTM E814  ·  NFPA 272  ·  UL 1479",
        "AR-001 – AR-006  ·  Designed ruleset  ·  Not implemented — post-FMP scope")

    s = slide(p, "Status of this work", "What is designed, and what is not built", RED)
    cards(s, [
        ("The ruleset is specified", "Six rules, each with its query path through the IFC schema, its threshold basis in a cited code, and its output contract. That specification is the contribution presented here.", CYAN),
        ("The engine is not implemented", "No ARCH module exists in the codebase. A search for AR-001 through AR-006 returns nothing, and no architectural rule appears in the compliance runner or the engine registry.", RED),
        ("No accuracy figure is claimed", "Precision, recall and per-rule accuracy would require an implementation and a labelled corpus. Neither exists, so no such figure appears in this deck.", RED),
        ("Why it is presented anyway", "The design demonstrates that the method generalises beyond corrosion, and it is the concrete scope for the next phase. Presenting a specification as a specification costs nothing; presenting it as a result would.", GREEN)], h=0.88, gap=0.12)

    s = slide(p, "Scope of architectural analysis", "Four families of check", BLUE)
    columns(s, [("Fire rating continuity", "Whether a compartment boundary actually holds: wall and slab ratings, and the sealing rating of everything that passes through them.", RED),
                ("Egress verification", "Travel distance to exit, door width and swing direction, dead-end limits, exit count against occupancy.", AMBER),
                ("Accessible routes", "Clear width, running slope and cross-slope along circulation paths; turning and approach space at fixtures.", BLUE),
                ("Spatial adjacency", "Whether incompatible uses are separated by the rating their combination demands.", NAVY)], h=3.10)

    s = slide(p, "The six designed rules", "Each with a query path and a threshold basis", NAVY)
    table(s, ["Ref", "Rule", "Primary IFC query", "Threshold basis"],
        [["AR-001", "Fire rating continuity", "Pset_WallCommon.FireRating", "IBC compartmentation"],
         ["AR-002", "Accessible route geometry", "Circulation IfcSpace boundaries", "ADA / EN 17210"],
         ["AR-003", "Egress path verification", "IfcDoor + IfcSpace topology", "IBC travel distance"],
         ["AR-004", "Penetration sealing", "IfcOpeningElement + seal Pset", "ASTM E814 / NFPA 272"],
         ["AR-005", "Barrier-free space", "IfcSpace geometry, fixture clearance", "ADA clear floor area"],
         ["AR-006", "Spatial adjacency separation", "IfcRelSpaceBoundary", "IBC use separation"]],
        widths=[1.0, 2.6, 3.1, 2.8], row_h=0.31)
    note(s, "Every rule resolves to a query the IFC schema can answer and a threshold a code clause supplies. That is the test a rule must pass to enter the set.", y=3.35)

    s = slide(p, "AR-001 — fire rating continuity", "The check that compartmentation actually holds", RED)
    cards(s, [
        ("Query", "All IfcWall and IfcSlab carrying Pset_WallCommon.FireRating or the slab equivalent; then every IfcOpeningElement that passes through them.", CYAN),
        ("Evaluate", "For each penetration, compare the sealing system rating against the rating of the element it breaches. A 2-hour wall with a 1-hour sleeve is a 1-hour wall.", BLUE),
        ("Output", "Critical where seal rating is below element rating; Approved where equal or greater; data-quality issue where either rating is absent — which, on the corrosion corpus, was the common case.", RED),
        ("Why it matters", "This is the failure mode that is invisible in geometry and fatal in service. The model is clash-free and the compartment does not hold.", NAVY)], h=0.88, gap=0.12)

    s = slide(p, "AR-003 — egress path verification", "Geometry that determines whether people get out", AMBER)
    table(s, ["Step", "Operation", "Reference"],
        [["1", "Identify exits: IfcDoor with exit classification", "IBC Ch. 10"],
         ["2", "Build space topology from IfcRelSpaceBoundary", "ISO 16739-1"],
         ["3", "Compute travel distance from the farthest occupied point", "IBC common path"],
         ["4", "Compare against occupancy-dependent maximum", "IBC travel distance table"],
         ["5", "Check door clear width and swing direction", "IBC 1010, ADA 404"],
         ["6", "Verify exit count against occupant load", "IBC 1006"]],
        widths=[0.7, 5.4, 3.4], row_h=0.30)
    note(s, "Steps 1–4 are the ones that need real graph traversal rather than property lookup, and they are where the implementation effort concentrates.", y=3.55)

    s = slide(p, "AR-002 — accessible route geometry", "Dimensional compliance along circulation", BLUE)
    table(s, ["Dimension", "Requirement", "Standard"],
        [["Clear width, unobstructed", "≥ 915 mm (36 in)", "ADA 403.5 / EN 17210"],
         ["Running slope", "≤ 1:20 (5%) without ramp provisions", "ADA 403.3"],
         ["Cross slope", "≤ 1:48 (2%)", "ADA 403.3"],
         ["Passing space interval", "≤ 61 m (200 ft)", "ADA 403.5.3"],
         ["Changes in level", "≤ 6 mm without bevel", "ADA 303"]],
        widths=[3.0, 3.4, 3.1], row_h=0.32)
    note(s, "Width is measured at intervals along the path rather than once, because the binding constraint is usually a local pinch point — a column, a door leaf, a radiator — not the nominal corridor width.", y=3.45)

    s = slide(p, "AR-004 — penetration sealing", "Matching the seal to what it breaches", RED)
    table(s, ["Through-element", "Minimum seal rating", "Standard"],
        [["Duct through rated wall", "Equal to wall rating", "ASTM E814 / NFPA 272"],
         ["Pipe through rated slab", "Equal to slab rating", "ASTM E814 / NFPA 272"],
         ["Conduit through rated barrier", "Equal to barrier rating", "UL 1479 / ASTM E814"],
         ["Cable tray through rated wall", "Equal to wall rating, F and T rated", "UL 1479"]],
        widths=[3.2, 3.2, 3.1], row_h=0.32)
    note(s, "This is the rule with the clearest cross-discipline dependency: the penetrating element belongs to MEP, the barrier to architecture, and the seal to neither package until someone owns it. A federated check is the only place it can be caught.", y=3.30)

    s = slide(p, "AR-005 and AR-006", "Barrier-free space and use separation", NAVY)
    columns(s, [("AR-005 — barrier-free space",
        "Turning circle 1525 mm diameter or T-turn equivalent. Forward approach 760 mm wide by 1220 mm deep; side approach 1220 by 760. Knee clearance 685 mm high, 280 mm deep. Counter height 865 mm maximum at accessible positions.", BLUE),
        ("AR-006 — spatial adjacency",
         "Mechanical plant above a threshold input against residential occupancy: 1-hour minimum. Hazardous storage against occupancy: 2-hour. Exit stair enclosure against electrical switchroom: 1-hour. Evaluated by walking IfcRelSpaceBoundary and reading the separating element's rating.", NAVY)], h=3.10)

    s = slide(p, "How the rules would read the model", "Inputs the IFC must actually carry", CYAN)
    table(s, ["Rule", "Required input", "Availability in the corrosion corpus"],
        [["AR-001", "FireRating on walls and slabs", ("Rarely populated", RED, False)],
         ["AR-002", "Circulation space geometry", ("Present where IfcSpace is modelled", AMBER, False)],
         ["AR-003", "Door classification and space topology", ("Partially present", AMBER, False)],
         ["AR-004", "Penetration seal Pset", ("Effectively absent", RED, False)],
         ["AR-005", "Fixture and clear-space geometry", ("Present where modelled", AMBER, False)],
         ["AR-006", "Space use classification", ("Partially present", AMBER, False)]],
        widths=[1.0, 4.0, 4.5], row_h=0.30)
    note(s, "The corrosion sweep already measured what federated models carry, and the pattern generalises: geometry is reliably present, semantic property data is not. AR-001 and AR-004 would face the same input-availability wall that MM-001 and XM-001 hit.", y=3.55)

    s = slide(p, "What validation would require", "The work that has not been done", RED)
    cards(s, [
        ("An implementation", "Six comparator modules, each loading a versioned ruleset and emitting the standard Issue contract, wired into the engine registry.", RED),
        ("A labelled corpus", "Models where the correct answer is known independently — from an approved building-control submission, not from the tool itself. Without that, precision and recall have no referent.", RED),
        ("A method for spatial ground truth", "Egress distance and accessible width need a measured baseline. Corrosion could lean on material tables; geometry compliance cannot.", AMBER),
        ("Honest reporting of coverage", "The corrosion work showed that a 100% flag rate can mean zero input coverage. Any ARCH result must report coverage alongside findings from the first run.", NAVY)], h=0.88, gap=0.12)

    s = slide(p, "Design case 1 — isolation ward penetration", "Worked through the specification, not executed", AMBER)
    metrics(s, [("2 hr", "barrier rating\nIBC compartment", RED),
                ("600 mm", "oval duct\npenetration", BLUE),
                ("2 hr", "sleeve F-rating\nASTM E814", GREEN),
                ("PASS", "AR-004 as\nspecified", GREEN)])
    cards(s, [("What the rule would conclude",
        "Seal rating equals barrier rating, so the compartment holds and the penetration is compliant. The value of the check is not this case but its inverse: a 1-hour sleeve in the same opening produces a clash-free, geometrically valid model that fails compartmentation, and nothing in current tooling would say so.", AMBER)], y=3.05, h=1.10)

    s = slide(p, "Design case 2 — single-exit floor plate", "Where the rule earns its cost", RED)
    metrics(s, [("75 × 45 m", "floor plate\nfootprint", BLUE),
                ("118 m", "travel distance\nfarthest corner", RED),
                ("76 m", "IBC maximum\ncommon path", NAVY),
                ("FAIL", "AR-003 as\nspecified", RED)])
    cards(s, [("Why the timing matters more than the finding",
        "A 42 m overrun is not a detail to resolve in coordination; it requires a second stair core, which is structure, foundations and floor plate. Found at LOD 300 it is a design revision. Found at construction it is a redesign. The rule is cheap; the stage at which it runs is what makes it valuable.", RED)], y=3.05, h=1.10)

    s = slide(p, "Integration with the existing pipeline", "How ARCH would fit what already runs", BLUE)
    cards(s, [
        ("Same Issue contract", "ARCH rules would emit the mechanism-agnostic Issue used by every corrosion engine, so the reporter, BCF exporter and asset register need no change.", CYAN),
        ("Same engine registry", "Registration alongside GC-001, CC-001 and MC-001, so a run reports ARCH availability and coverage in the same status table.", BLUE),
        ("Cross-discipline by construction", "AR-004 reads MEP penetrations against architectural barriers — a check neither package can perform alone.", NAVY),
        ("Same honesty requirement", "Coverage reported beside findings from the first run, so an ARCH flag rate is never read without the input availability that produced it.", GREEN)], h=0.88, gap=0.12)

    s = slide(p, "Academic contribution of the specification", "What the design establishes", NAVY)
    columns(s, [("The method generalises", "The pattern — versioned ruleset, IFC query path, cited threshold, mechanism-agnostic Issue — transfers from corrosion to code compliance without modification.", CYAN),
        ("Cross-discipline checking has a home", "Penetration sealing belongs to no single package. A federated rule engine is the natural place for it, and AR-004 shows the shape.", BLUE),
        ("Input availability is predictable", "The corrosion corpus already measured what federated models carry. ARCH can predict its own coverage problem before implementation.", RED),
        ("Scope is bounded and costed", "Six rules, each with a defined query and threshold, is a specification a successor can implement against.", GREEN)], h=3.10)

    s = slide(p, "Limitations of the design", "Known before a line is written", AMBER)
    cards(s, [
        ("Prescriptive, not performance-based", "AR-004 compares ratings. It cannot evaluate an equivalent assembly that achieves the same performance by other means, which is how much real fire engineering is argued.", AMBER),
        ("Planar geometry assumptions", "Egress and accessible-route logic assumes floor-plan traversal. Split levels, ramps and mezzanines need vertical routing that the design does not yet cover.", AMBER),
        ("Dependent on absent property data", "AR-001 and AR-004 need ratings that the corrosion corpus showed are rarely populated. Implementation without a data strategy would reproduce the MM-001 outcome.", RED),
        ("Code scope is jurisdictional", "IBC and ADA thresholds are US. EN 17210 differs. The jurisdiction-config pattern from Blue Halo would need to carry across.", NAVY)], h=0.88, gap=0.12)

    s = slide(p, "Post-FMP roadmap", "R1 – R6 for the architectural engine", BLUE)
    table(s, ["Ref", "Enhancement", "Prerequisite", "Target"],
        [["R1", "Implement AR-001 and AR-004 (fire and sealing)", "Ruleset packs in the shipped schema", "Q1 2027"],
         ["R2", "Implement AR-003 egress with space-graph traversal", "Space topology extraction", "Q2 2027"],
         ["R3", "Implement AR-002 and AR-005 accessibility", "Circulation geometry extraction", "Q2 2027"],
         ["R4", "Labelled validation corpus", "Models with approved control submissions", "Q2 2027"],
         ["R5", "Jurisdiction configs (IBC / EN 17210)", "Standards research per Blue Halo pattern", "Q3 2027"],
         ["R6", "Performance-based equivalence for AR-004", "Assembly performance data", "Q3 2027"]],
        widths=[0.7, 4.6, 3.2, 1.0], row_h=0.29)
    note(s, "R4 is the gating item: without a labelled corpus, R1–R3 can be implemented but not validated, and the deck would face the same evidence problem it avoids today.", y=3.50, bold=True)

    s = slide(p, "Standards referenced", "Sources for each threshold", NAVY)
    table(s, ["Standard", "Supplies", "Rules"],
        [["IBC — International Building Code", "Compartmentation, travel distance, exit count", "AR-001, AR-003, AR-006"],
         ["ADA — Americans with Disabilities Act", "Route width, slope, clear space", "AR-002, AR-005"],
         ["EN 17210", "European accessibility equivalents", "AR-002, AR-005"],
         ["ASTM E814 / NFPA 272", "Penetration firestop test method", "AR-004"],
         ["UL 1479", "Through-penetration firestop systems", "AR-004"],
         ["ISO 16739-1", "IFC schema, spatial relationships", "All"]],
        widths=[3.0, 3.6, 2.9], row_h=0.30)
    note(s, "Each would be carried in a versioned pack rather than embedded in code, matching the corrosion and Blue Halo pattern.", y=3.65)

    s = slide(p, "Designed output contract", "What an ARCH finding would carry", CYAN)
    table(s, ["Field", "Content", "Why it is required"],
        [["rule_id", "AR-001 … AR-006", "Identifies the rule that fired"],
         ["element_id", "IFC GlobalId of the failing element", "Anchors the finding to the model"],
         ["band", "Critical / High / Medium / Low", "Triage order for the reviewer"],
         ["citations", "Standard and clause that set the threshold", "Makes the finding arguable on evidence"],
         ["metadata", "Measured value against required value", "Shows the margin, not just the verdict"],
         ["mechanism", "fire_rating, egress, accessibility …", "Keeps distinct failures separately actionable"]],
        widths=[1.7, 4.0, 3.8], row_h=0.30)
    note(s, "This is the existing Issue contract, unchanged. ARCH rules would populate the same structure the corrosion engines already use, which is why the reporter, BCF exporter and asset register need no modification to carry them.", y=3.55)

    s = slide(p, "Regulatory context", "Why an auditable trail matters here", GREEN)
    cards(s, [
        ("Building Safety Act 2022", "Requires demonstrable, auditable evidence that compliance was considered — not merely asserted at hand-over.", CYAN),
        ("Pset write-back", "An ARCH finding would attach to the element, so the compliance state travels with the object through federation and hand-over.", GREEN),
        ("BCF as the review record", "Each finding becomes a topic with a viewpoint, so the reviewer sees what the rule saw.", BLUE),
        ("ISO 19650 status codes", "S2 while unresolved, S4 with an NCR raised, Status A on acceptance — the same lifecycle the corrosion engines already use.", NAVY)], h=0.88, gap=0.12)

    s = slide(p, "Cross-discipline integration", "Where ARCH and the corrosion engines meet", BLUE)
    columns(s, [("ARCH reads MEP", "AR-004 evaluates MEP penetrations against architectural barriers. Neither discipline's model contains both halves.", CYAN),
                ("MEP reads ARCH", "Corrosion environment class is inferred from architectural spatial containment — space name, storey, zone.", BLUE),
                ("Findings stay separate", "One Issue per mechanism, because the mitigations differ. A firestop sleeve does not fix a galvanic couple.", NAVY)], h=3.10)
    note(s, "The dependency already runs in one direction today: environment classification reads architectural spatial data. AR-004 would close the loop.", bold=True)

    s = slide(p, "Honest summary", "What may and may not be claimed", RED)
    metrics(s, [("6", "rules fully\nspecified", CYAN),
                ("0", "rules\nimplemented", RED),
                ("0", "accuracy figures\nclaimed", RED),
                ("R1–R6", "roadmap with\nprerequisites", BLUE)])
    cards(s, [("The claim this deck makes",
        "That the compliance method demonstrated on corrosion extends to architectural code checking, and that the extension has been specified to the level of query path and cited threshold. It does not claim the engine exists, that any model has been checked, or that any accuracy has been measured. Those claims would need R1 and R4 first.", RED)], y=3.05, h=1.10)

    s = slide(p, "Key points", "What to take from this specification", BLUE)
    cards(s, [
        ("Code compliance is machine-checkable in principle", "Every one of the six rules resolves to an IFC query and a cited threshold. None requires judgement the schema cannot supply.", CYAN),
        ("Fire and egress carry the life-safety weight", "AR-001, AR-003 and AR-004 are the rules whose failure modes are fatal rather than costly, and they are first on the roadmap.", RED),
        ("Input availability will be the binding constraint", "The corrosion corpus already showed it. ARCH should measure coverage from its first run rather than discover it later.", AMBER),
        ("The architecture is already in place", "Issue contract, engine registry, BCF exporter and Pset write-back all exist and are engine-agnostic.", GREEN)], h=0.88, gap=0.12)

    closing(p, "Architectural Code Analysis", "Questions?")

    out = OUT_DIR / "BIMGUARD_FMP_C_Architectural_Analysis.pptx"
    p.save(str(out))
    return out

if __name__ == "__main__":
    print(f"  {build()}")
