"""Deck D — Integrated Overview (24 slides)."""
try:
    from build_fmp_decks import *  # noqa: F403
except ImportError:
    from scripts.build.build_fmp_decks import *  # noqa: F403

def build():
    p = new_deck()

    title_slide(p, "BIMGUARD AI",
        "Automated OpenBIM Compliance Across Disciplines",
        "OpenBIM  ·  IFC ISO 16739-1  ·  BCF 2.1  ·  ISO 19650  ·  Building Safety Act 2022",
        "Five corrosion engines  ·  One spatial engine  ·  Validated across 37 models from 8 repositories")

    s = slide(p, "The problem BIM cannot currently solve", "Corrosion is predictable, preventable, and unchecked", RED)
    metrics(s, [("3.4%", "of global GDP lost to\ncorrosion annually", NAVY),
                ("6–10×", "cost multiplier: field\nversus design-stage fix", BLUE),
                ("0", "existing BIM tools that\ncheck corrosion in IFC", RED),
                ("0 pts", "Golden Thread evidence\nwithout this work", AMBER)])
    note(s, "Clash detection resolves geometry. Two touching elements of incompatible material, or a stainless grade wrong for its environment, produce a clash-free model and a failure in service.", y=3.05)
    note(s, "BIMGUARD AI closes that gap using data already present in the model at LOD 300 — no additional modelling effort required.", y=4.00, bold=True)

    s = slide(p, "Three research questions", "The academic scope", BLUE)
    cards(s, [
        ("RQ1  —  Detection from existing IFC data",
         "Can corrosion risk in MEP services be reliably identified from material, spatial and zone metadata already present at LOD 300?", CYAN),
        ("RQ2  —  Simultaneous multi-mechanism checking",
         "Can several mechanisms be evaluated in one pass, each reporting failures the others cannot see, rather than collapsing into a single score?", BLUE),
        ("RQ3  —  OpenBIM cross-platform deployment",
         "Can a checker operating purely on IFC input and BCF output work across authoring tools with no vendor plugin or proprietary API?", NAVY)])

    s = slide(p, "The compliance pipeline", "Five stages, each failing independently and saying why", NAVY)
    table(s, ["Stage", "Function", "Status"],
        [["1", "Geometry normalisation and spatial filter", ("Implemented, 100% resolution", GREEN, False)],
         ["2", "Blue Halo clearance envelope (LOD 350 reservation)", ("Implemented, validated", GREEN, False)],
         ["3", "Corrosion engines: GC-001, CC-001, MC-001, MM-001, XM-001", ("3 of 5 execute; 2 not wired", AMBER, False)],
         ["4", "Resolution hierarchy and mitigation ranking", ("Designed", AMBER, False)],
         ["5", "Reporting: BCF 2.1, Pset write-back, ISO 19650 status", ("Implemented, 37/37 valid", GREEN, False)]],
        widths=[0.7, 5.6, 3.2], row_h=0.33)
    note(s, "The architectural ruleset (AR-001 – AR-006) is specified as a sixth family and is not implemented; it is presented separately as design scope.", y=3.30)
    note(s, "Stage 3's status is stated in thesis §13.9: the MM-001 and XM-001 packs are approved but not wired into the comparator.", y=4.10, bold=True)

    s = slide(p, "Engine A — GC-001 galvanic corrosion", "Material incompatibility at a joint", CYAN)
    formula(s, "Score  =  (0.50 × voltage)  +  (0.30 × area ratio)  +  (0.20 × environment)", y=1.40, h=0.72)
    columns(s, [("Specified", "22-material electrochemical series, 7 environment classes, PREN adequacy for stainless grades. Thresholds from NASA-STD-6012, WorldStainless and IMOA.", CYAN),
                ("Implemented", "Executes on all 37 models. Produces bands and writes BCF topics and Pset_CorrosionRisk.", GREEN),
                ("Measured", "0 of 116,006 elements flagged. Required inputs present on 8 elements — 0.007% coverage.", RED)], y=2.35, h=1.45)
    note(s, "The single-element entry point pairs each element with itself, so no couple is ever formed. Recorded as a specification-against-implementation gap.", y=3.95, bold=True)

    s = slide(p, "Engine B — CC-001 crevice corrosion", "Geometry the galvanic check cannot see", BLUE)
    formula(s, "Score  =  (0.35 × geometry)  +  (0.40 × CCT margin)  +  (0.25 × environment)", y=1.40, h=0.72)
    columns(s, [("Specified", "Crevice Corrosion Temperature table from SS304 to Titanium Gr 2; 14-type joint geometry library from butt weld to threaded connection.", CYAN),
                ("Implemented", "Executes on all 37 models and emits its own BCF topics, independent of GC-001.", GREEN),
                ("Measured", "116,006 of 116,006 flagged — 100%. Band floor is Medium; an absent material scores High.", RED)], y=2.35, h=1.45)
    note(s, "A 100% flag rate with 0% input coverage is the same fact twice: the coercer substitutes a default and the engine scores the default, uniformly.", y=3.95, bold=True)

    s = slide(p, "Engine C — Blue Halo spatial reservation", "The engine the corpus validates cleanly", GREEN)
    metrics(s, [("49,736", "MEP elements\n100% geometry", GREEN),
                ("223,516", "clashes detected\nand exported", CYAN),
                ("37 / 37", "BCF archives\nfully valid", BLUE),
                ("0.00%", "schema twin\ndelta", NAVY)])
    cards(s, [("Why this one holds up",
        "Blue Halo depends on geometry, which real exports reliably carry, rather than on semantic property data, which they do not. Every MEP element resolved. Same-building twins in IFC2x3 and IFC4 produced identical and near-identical clash counts, so the result is schema-independent.", GREEN)], y=3.05, h=1.10)

    s = slide(p, "Engines D and E — MM-001 and XM-001", "Approved specification, not wired to the comparator", RED)
    cards(s, [
        ("What is approved", "MM-001 holds a 12-material by 8-media compatibility matrix; XM-001 scores the galvanic couple at a joint between dissimilar modelled elements. Both packs are reviewed at v1.0 with recorded amendments.", CYAN),
        ("What executes", "Neither. load_rule_pack() rejects the approved packs because the shipped comparators validate an earlier schema — MM-001 on compatibility_matrix, media, environments and materials; XM-001 on couples, materials and environment_thresholds.", RED),
        ("Corroborated independently", "The unit suites fail at fixture setup for the same reason: 3 of 29 MM-001 tests and 1 of 39 XM-001 tests execute. The validation sweep and the test suite reached the same conclusion by different routes.", RED),
        ("Recorded, not concealed", "Thesis §13.9 and Table 13.13 state this term by term: 'no claim in this chapter should be read as asserting' that the wiring exists.", NAVY)], h=0.88, gap=0.12)

    s = slide(p, "When mechanisms disagree", "Why separate engines rather than one score", BLUE)
    metrics(s, [("0.00", "GC-001 band\nno couple exists", GREEN),
                ("0.89", "CC-001 band\nchloride at the gasket", RED),
                ("E7", "pool plant\n1.8× multiplier", AMBER),
                ("CRITICAL", "combined band\nhigher of the two", RED)])
    cards(s, [("SS316 flange in a pool plant room",
        "A single material, so no galvanic couple and nothing for GC-001 to report. Under the gasket face, chloride concentrates in the crevice at E7 and CC-001 scores it Critical. One element, one engine correctly silent, the other decisive. A single combined score would have averaged the finding away.", RED)], y=3.05, h=1.10)

    s = slide(p, "Validation at corpus scale", "37 models, 8 repositories, two IFC schemas", CYAN)
    table(s, ["Measure", "Result", "Note"],
        [["Models processed", "37 of 38", "One IFC2X2_FINAL, unsupported by IfcOpenShell"],
         ["MEP elements", "49,736", "100% geometry resolution"],
         ["Structural elements", "26,970", "26,808 resolved (99.4%)"],
         ["Clashes detected", "223,516", "211,581 minor / 6,699 major / 5,236 critical"],
         ["Piping elements scored", "116,006", "38,012 carry material text"],
         ["Scoreable material", ("2,403 (2.07%)", RED, True), "Normalise to a canonical key"],
         ["BCF archives valid", "37 of 37", "Every XML part parsed, every topic complete"]],
        widths=[2.6, 2.3, 4.6], row_h=0.29)
    note(s, "Sweep wall-clock 3,594 s, mean 97 s per model.", y=3.75, bold=True)

    s = slide(p, "Material text is not material data", "The measurement that reframes the result", RED)
    metrics(s, [("116,006", "piping elements\nscored", NAVY),
                ("38,012", "carry some\nmaterial string", AMBER),
                ("2,403", "normalise to a\nscoreable key", RED),
                ("2.07%", "usable material\ncoverage", RED)])
    cards(s, [("The 16× gap",
        "35,609 elements carry material text the normaliser cannot map, so the engines still receive 'Unknown'. Reporting the 32.8% figure as coverage overstates usable data roughly sixteenfold. This distinction is the single easiest way to misread the corpus, and it is why every engine result is published beside its input coverage.", RED)], y=3.05, h=1.10)

    s = slide(p, "Standards sensitivity", "Jurisdiction choice dominates the outcome", AMBER)
    table(s, ["Clearance", "Jurisdiction", "Clashes", "Critical", "Ratio"],
        [["25 mm", "—", "30,332", "148", "0.29×"],
         ["100 mm", "—", "69,307", "38", "0.67×"],
         [("200 mm", NAVY, True), ("EN 1998-1 + DIN 4149", NAVY, True), ("104,144", NAVY, True), ("31", NAVY, True), ("1.00×", NAVY, True)],
         [("457.2 mm", RED, True), ("ASCE 7-22 + NFPA 13", RED, True), ("172,812", RED, True), ("16", RED, True), ("1.66×", RED, True)],
         ["600 mm", "—", "212,870", "11", "2.04×"]],
        widths=[1.4, 3.2, 1.8, 1.4, 1.4], row_h=0.31)
    note(s, "Moving from the European to the US standard produces 66% more clashes and 48% fewer Critical ones, because severity is an overlap ratio and a larger clearance inflates the denominator. Reproduced on two independent subsets.", y=3.45)

    s = slide(p, "Test evidence", "What runs, and what the failures mean", GREEN)
    table(s, ["Suite", "Result", "Interpretation"],
        [["Core suite (tests/)", "289 passed", "Piping, comparators, BCF, registry, environment"],
         ["Route suite (tests/test_routes.py)", "44 passed, 4 xfail", "HTTP layer; xfail records 404-vs-200 gaps"],
         ["Blue Halo harness", "11 of 11", "Config, geometry, clash, banding, export"],
         ["End-to-end IFC pipeline", "8 of 8", "Real IFC through halo, clash, BCF, Pset"],
         [("MM-001 / XM-001 suites", RED, True), ("69 failures / errors", RED, True), ("Signature mismatch — corroborates §13.9", RED, False)]],
        widths=[3.0, 2.2, 4.3], row_h=0.31)
    note(s, "The 69 failures are not noise to be silenced: they are executable evidence for the specification-against-implementation gap the thesis documents, which is why §13.9 can quote exact pass counts.", y=3.40, bold=True)

    s = slide(p, "Technology stack", "Deliberately vendor-neutral", NAVY)
    columns(s, [("Core", "Python 3.12.13, IfcOpenShell 0.8.5, uv-managed dependencies. Geometry through ifcopenshell.geom in world coordinates.", CYAN),
                ("Application", "FastHTML with MonsterUI, HTMX for partial updates, server-rendered from Python — no template files.", BLUE),
                ("Data", "Supabase Postgres and object storage, with a transparent local materialisation cache.", NAVY),
                ("Analytics", "Power BI PBIP project — TMDL semantic model plus report definition, consuming a versioned CSV contract.", GREEN)], h=3.10)
    note(s, "No Autodesk API, no proprietary plugin, no authoring-tool dependency anywhere in the compliance path.", bold=True)

    s = slide(p, "OpenBIM as an architectural decision", "Why vendor neutrality was not incidental", BLUE)
    cards(s, [
        ("IFC in, BCF out", "The tool reads ISO 16739-1 and writes BCF 2.1. Both are open, versioned and readable without the tool that produced them.", CYAN),
        ("Demonstrated across toolchains", "The corpus spans Revit, ArchiCAD and Autodesk exports in IFC2x3 and IFC4. Schema twins differed by 0.11% and 0.00%.", GREEN),
        ("Evidence outlives the tool", "Pset write-back means the finding travels in the model. An auditor needs an IFC reader, not a BIMGUARD licence.", NAVY),
        ("Portable across jurisdictions", "Clearance and threshold data live in versioned configs, so a new standard is a data addition rather than a code change.", BLUE)], h=0.88, gap=0.12)

    s = slide(p, "Golden Thread and the Building Safety Act", "Compliance evidence that persists", GREEN)
    table(s, ["Requirement", "How it is met", "Artefact"],
        [["Auditable decision record", "Every finding names clause, threshold and inference", "BCF topic + Issue citations"],
         ["Evidence travels with the asset", "Findings written back to the element", "Pset_CorrosionRisk, Pset_HaloReservation"],
         ["Readable without the tool", "Open formats throughout", "IFC, BCF 2.1"],
         ["Traceable workflow state", "ISO 19650 status on each container", "S2 / S4 / Status A"],
         ["Reproducible", "Harness, configs and corpus are versioned", "Appendix B, validation_sweep_summary.json"]],
        widths=[2.7, 3.6, 3.2], row_h=0.31)
    note(s, "Reproducibility is the claim most examiners can check directly: the sweep re-runs from a clean clone and regenerates every table and figure in Appendix B.", y=3.45)

    s = slide(p, "RQ1 — answered", "Detection from existing IFC data", CYAN)
    metrics(s, [("YES", "method demonstrated\nand reproducible", GREEN),
                ("100%", "geometry resolution\n49,736 elements", CYAN),
                ("2.07%", "elements carrying\nscoreable material", RED),
                ("37 / 38", "models processed\nend to end", BLUE)])
    cards(s, [("The qualified answer",
        "Where an element carries a mappable material and a resolvable neighbour, risk is detected and scored deterministically from data already in the model. The constraint is the corpus, not the method: real federated models rarely carry the semantic inputs. Measuring that distance is itself a contribution, and it separates a demonstrated method from a deployed one.", CYAN)], y=3.05, h=1.10)

    s = slide(p, "RQ2 — answered", "Simultaneous multi-mechanism checking", BLUE)
    cards(s, [
        ("Architecturally — yes", "Engines register independently, share one mechanism-agnostic Issue contract, and emit separate BCF topics. Three execute together on every model in the corpus.", GREEN),
        ("Demonstrated by non-overlap", "The SS316 pool-plant case shows one engine correctly silent while another reports Critical — the behaviour a single combined score would destroy.", CYAN),
        ("Two of five do not participate", "MM-001 and XM-001 are approved but unwired, so the full five-mechanism claim is not supported by this run.", RED),
        ("Honest form of the answer", "Simultaneous checking works and is demonstrated at three engines. Five is specified, not shown.", NAVY)], h=0.88, gap=0.12)

    s = slide(p, "RQ3 — answered", "OpenBIM cross-platform deployment", NAVY)
    metrics(s, [("YES", "no vendor API\nanywhere in the path", GREEN),
                ("2", "IFC schemas\n2x3 and IFC4", CYAN),
                ("8", "independent source\nrepositories", BLUE),
                ("37 / 37", "BCF archives\nvalid", GREEN)])
    cards(s, [("What the corpus established",
        "Models exported from three authoring toolchains, in two schema versions, from eight repositories, processed by one pipeline with no per-tool special-casing. The two same-building schema twins are the strongest control: identical inputs through different exporters produced clash counts 0.00% and 0.11% apart.", GREEN)], y=3.05, h=1.10)

    s = slide(p, "Academic contributions", "Five, stated at the level the evidence supports", NAVY)
    table(s, ["Contribution", "Evidence"],
        [["A reproducible method for corrosion assessment from IFC metadata", "37-model sweep, regenerable from a clean clone"],
         ["Quantification of the semantic data gap in federated models", "2.07% scoreable material across 116,006 elements"],
         ["Blue Halo: proactive LOD 350 reservation at LOD 300", "100% geometry resolution, schema-independent"],
         ["White-box auditability as a design constraint", "Every finding carries clause, threshold and inference"],
         ["A clearance-severity inversion in ratio-based banding", "1.66× clashes, 0.52× Critical, on two subsets"]],
        widths=[5.4, 4.1], row_h=0.36)
    note(s, "Each is stated as what was measured, not as what was hoped. The gaps — two unwired engines, an unimplemented ARCH ruleset — are documented in §13.9 rather than omitted.", y=3.60)

    s = slide(p, "Limitations", "Carried openly", AMBER)
    cards(s, [
        ("Two engines are not wired in", "MM-001 and XM-001 hold approved packs the comparators cannot load. 69 unit failures and 24 unavailable models corroborate the same gap.", RED),
        ("Input availability limits every corrosion result", "At 2.07% scoreable material, flag rates describe the coercers' defaults more than the buildings.", RED),
        ("Clash counts are geometric upper bounds", "AABB intersection over-approximates diagonal and non-convex members.", AMBER),
        ("Severity banding lacks a standards basis", "An overlap ratio is defensible as triage and not as a verdict; the sensitivity result argues for replacing it.", AMBER)], h=0.88, gap=0.12)

    s = slide(p, "Post-FMP roadmap", "Seven enhancements, ordered by dependency", BLUE)
    table(s, ["Ref", "Enhancement", "Why it ranks here", "Target"],
        [["R1", "Wire MM-001 and XM-001 to the approved packs", "Closes the largest documented gap", "Q1 2027"],
         ["R2", "Widen the material normaliser rule table", "Converts 35,609 unusable strings into input", "Q1 2027"],
         ["R3", "Standards-grounded severity model", "Replaces the ratio heuristic", "Q2 2027"],
         ["R4", "Angle-aware halo envelope", "Needs brace geometry to validate", "Q2 2027"],
         ["R5", "Implement ARCH rules AR-001 and AR-004", "Extends method to code compliance", "Q2 2027"],
         ["R6", "Galvanic current and time-to-perforation", "Needs conductivity and rate data", "Q3 2027"],
         ["R7", "Labelled validation corpus", "Prerequisite for any accuracy claim", "Q3 2027"]],
        widths=[0.7, 4.1, 3.6, 1.1], row_h=0.29)
    note(s, "R2 is the highest measured value for the least effort: the corpus already quantifies exactly how much input it would unlock.", y=3.50, bold=True)

    s = slide(p, "What the corpus established", "Findings across all engines", GREEN)
    cards(s, [
        ("Geometry generalises; semantics do not", "100% geometry resolution against 2.07% scoreable material. The spatial engine works on real models; the corrosion engines are starved of input.", CYAN),
        ("Independent engines catch independent failures", "The pool-plant case is the proof: one engine silent, another Critical, on the same element.", BLUE),
        ("The result is schema-independent", "Two IFC versions, three toolchains, eight repositories, one pipeline — twins 0.00% and 0.11% apart.", GREEN),
        ("Reporting coverage beside findings is essential", "Without it, a 100% flag rate reads as a result rather than as an artefact of absent data.", RED)], h=0.88, gap=0.12)

    closing(p, "BIMGUARD AI", "Questions?")

    out = OUT_DIR / "BIMGUARD_FMP_D_Integrated_Overview.pptx"
    p.save(str(out))
    return out

if __name__ == "__main__":
    print(f"  {build()}")
