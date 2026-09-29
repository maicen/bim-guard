"""rule_builder/_extraction_prompts.py.

Prompt templates and KG-context formatter for the LlamaIndex rule extraction
engine (Module 3). Kept as a Python sibling module — not an external text file
— so that:

  1. Python str.format() escaping (``{{...}}``) stays visible next to the
     ``_RULE_PROMPT.format(...)`` call site that consumes it.
  2. ``_format_kg_context`` is directly unit-testable as a pure function
     without mocking the LLM program or ClauseGroundingIndex.
  3. ``_LLMRuleCandidate`` field descriptions and the corresponding prompt
     bullets live in the same repository, making schema/prompt drift
     detectable via code review rather than a runtime surprise.

When this module grows large enough to warrant further split (e.g. separate
prompts per rule domain, or per language), individual prompt constants can be
broken into ``prompts/`` sub-package files — still Python, never raw text.
"""

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a BIM compliance rule extraction engine for building regulations.

Judge each clause on its actual regulatory meaning, not on surface wording
alone. Never invent a target_ifc_class or property_name that isn't either
(a) one of the KNOWN-GOOD CANDIDATES you are shown for this clause, when any
are shown, or (b) a well-known IFC entity/property you are confident about
from the clause's own text. When candidates are shown and one plainly fits,
prefer it over guessing a different spelling or class — record which one you
used in kg_candidate_used (its uri), or "" if you used none of them (either
because none fit, or none were shown). Respond with strict, valid JSON
matching the requested schema only — no commentary, no markdown fences.
"""

# ── User/rule prompt ──────────────────────────────────────────────────────────
# Template variables (filled by LlamaIndex ChatPromptTemplate):
#   {kg_context}   — KG-grounded candidate block, or "" when no index exists
#   {check_category_context} — allowed check categories block, or "" when none are configured
#   {clause_text}  — The raw clause text to analyse

RULE_PROMPT = """\
Read the clause text below and extract every discrete, checkable
requirement it expresses (a numeric limit, a required property, a
classification, a presence check, or a required count of elements) against
an IFC element. A single clause commonly expresses more than one rule (for
example a base threshold plus an exception that changes it) — extract each
as its own entry in "rules". If the text expresses no checkable requirement
at all (e.g. it is a definition, example, or purely descriptive text),
return an empty "rules" array.
{kg_context}
For each rule found, fill in:
- rule_id: a short identifier, e.g. the clause reference if present, else
  "REQ-AI-<short-slug>"
- description: short plain-English rule description
- mechanism: "CODE"
- target_ifc_class: the IFC entity type the rule applies to, e.g. "IfcDoor",
  "IfcSpace", "IfcStairFlight" — required for every rule, since it is what
  lets a rule be checked against a model and exported to IDS
- property_set: IFC Pset name. ALWAYS supply this from the IFC standard for the
  chosen target_ifc_class — do NOT leave it blank. For IfcSign use
  "Pset_SignCommon"; for IfcDoor use "Pset_DoorCommon"; for IfcStairFlight use
  "Pset_StairFlightCommon", etc. If you are uncertain of the exact Pset, supply
  the standard "Pset_<ClassName without Ifc>Common" pattern.
- property_name: The exact IFC property (attribute or Pset property) that the
  rule measures or checks. NEVER leave this blank for numeric_range,
  numeric_comparison, or spatial_clearance rules — without it the engine has no
  target to evaluate. Choose the most specific standard IFC property name:
  e.g. for glass panel thickness → "Thickness"; for panel area → "PanelArea";
  for sign projection depth → "ProjectionDistance"; for overall sign thickness
  → "OverallThickness". Prefer well-known Pset properties over custom names.
- rule_type: "numeric_range" | "exists_check" | "count_check" | "classification"
  — use "count_check" for requirements on how many of an element are present
  (e.g. "two exits shall be provided"), not "numeric_range"
- operator: one of ">=", "<=", "==", "!=", "between", "exists", "matches"
- check_value: the target value as a string (numeric values as their string form), or empty
- value_min / value_max: string bounds for "between", or empty
- value_min_property / value_max_property: when the bound is not a fixed
  number but another property of the SAME element, optionally scaled and/or
  offset (e.g. "riser height shall not exceed one-half of the tread going"
  -> value_max_property="TreadGoing", value_max_scale="0.5"), the name of
  that property — else empty. Only use this for a property on the SAME
  element the rule targets; never for a property of a different element
  (a room, the building) — leave those to needs_review instead, see below.
- value_min_scale / value_max_scale: the multiplier on value_min_property /
  value_max_property (e.g. "0.5" for "one-half of"), as a string — default
  "1" (leave empty) when the clause has no multiplier, i.e. the bound is the
  referenced property plus/minus a fixed amount only.
- value_min_offset / value_max_offset: a fixed amount added after the scale
  above (e.g. "25" for "...plus 25mm"), as a string — default "0" (leave
  empty) when there is no such fixed amount.
- unit: "mm" | "m" | "m2" | "deg" | "ratio" | "" (empty if not applicable)
- severity: "mandatory" if the clause uses "shall"/"must", "recommended" if
  "should", else "recommended"
- confidence: 0.0-1.0, your confidence this rule is correctly extracted
- needs_review: 1 if the text is ambiguous, if the threshold is looked up in
  a table you cannot see in full, or if the bound is computed from a
  metric belonging to a DIFFERENT element than the one the rule targets
  (e.g. "one-half of the diagonal dimension of the area served" — the
  diagonal belongs to the room/building, not to the exit door the rule
  targets) rather than a fixed value or a property of the same element — else 0
- applies_when_materials: if the clause narrows this rule to elements of a
  specific material (e.g. "gypsum board partitions", "steel pipework"), list
  the material keyword(s) here — else leave empty. Do not use this for
  conditions you cannot express this way (e.g. sprinkler exceptions, table
  lookups by occupancy) — leave those to needs_review instead of guessing.
- rase_requirement: the exact regulatory text representing the core obligation (e.g. "Doors shall have a clear width").
- rase_applicability: JSON object defining the CONDITIONS (range bounds, material, occupancy) that
  activate this rule. Building-code tables always express TIERED RANGES, not exact point values.
  Represent each tier as a range object with _min and _max keys, e.g.:
  {{"projection_mm_min": 0, "projection_mm_max": 305}} for "projection up to 305 mm",
  {{"projection_mm_min": 305, "projection_mm_max": 610}} for "305 mm < projection ≤ 610 mm".
  NEVER use a bare exact value like {{"projection_mm": 1520}} — that would only match signs
  projecting exactly 1520 mm. When no applicability condition exists, leave this empty.
- rase_selection: JSON object defining criteria for selecting specific targets, or empty.
- rase_exception: JSON object defining conditions excusing the requirement (e.g. {{"has_sprinkler": true}}), or empty.
- kg_candidate_used: the uri of the KNOWN-GOOD CANDIDATE (if any were shown
  above) that target_ifc_class came from, or "" if none were shown or none
  were used.
- check_category: the CHECK CATEGORY (if any are listed below) this rule
  belongs to, copied exactly from that list, or "" if none are listed or none
  fits.
{check_category_context}
CLAUSE TEXT:
{clause_text}
"""


# ── Check-category formatter ──────────────────────────────────────────────────


def format_check_category_context(*, categories: list[dict], section_heading: str | None) -> str:
    """Render the allowed check categories as a prompt block, or "" if there are none.

    Pure function, injected into ``{check_category_context}`` in ``RULE_PROMPT``.
    The clause's enclosing section heading is shown alongside because source
    documents commonly group their requirements under headings that name the
    category outright (e.g. "3. Fire and Smoke Protection").

    Args:
        categories: ``{name, description, target_ifc_classes}`` per allowed
            category, in display order; a category listing classes only fits
            rules on one of them.
        section_heading: Nearest enclosing section heading of the clause, if known.
    """
    if not categories:
        return ""
    lines = [
        "CHECK CATEGORIES (pick exactly one name for check_category, or \"\"; a",
        "category listed under an element type only fits rules targeting that type):",
    ]
    for classes in dict.fromkeys(tuple(c.get("target_ifc_classes") or ()) for c in categories):
        lines.append(f"  {', '.join(classes) or 'Any element type'}:")
        lines.extend(
            f"    - {c['name']}: {c['description']}" if c.get("description") else f"    - {c['name']}"
            for c in categories
            if tuple(c.get("target_ifc_classes") or ()) == classes
        )
    if section_heading:
        lines.append(f'The clause sits under the section heading: "{section_heading}".')
    lines.append("")
    return "\n".join(lines)


# ── KG-context formatter ──────────────────────────────────────────────────────


def format_kg_context(
    *,
    class_candidates: list[dict],
    property_hints: list[dict],
    dependencies: list[dict],
) -> str:
    """Render the clause's KG-grounded signal as a prompt block, or "" if there is none.

    Pure function (candidates/hints/dependencies in, string out) — directly
    unit-testable without mocking ClauseGroundingIndex or the LLM program.

    Args:
        class_candidates: Verified bSDD/ontology class candidates for the clause.
        property_hints:   Verified property candidates for the clause.
        dependencies:     Clause-dependency edges (exception/override relations).

    Returns:
        A formatted string block injected into ``{kg_context}`` in
        ``RULE_PROMPT``, or an empty string when no signal is available.
    """
    if not (class_candidates or property_hints or dependencies):
        return ""

    lines: list[str] = []
    if class_candidates:
        lines.append("\nKNOWN-GOOD CANDIDATES (from verified ontology grounding for this clause):")
        for c in class_candidates[:5]:
            lines.append(f"  - target_ifc_class candidate: {c.get('name')} ({c.get('code')}), uri={c.get('uri')}")
    if property_hints:
        for p in property_hints[:5]:
            lines.append(f"  - property candidate: {p.get('name')} ({p.get('code')})")
    if dependencies:
        lines.append("\nRELATED CLAUSES in this document (resolve exceptions/overrides against these, not blind):")
        for dep in dependencies[:3]:
            lines.append(f"  - [{dep.get('edge_type')}] {dep.get('target_ref')}: \"{dep.get('target_text_excerpt')}\"")
    lines.append("")
    return "\n".join(lines)
