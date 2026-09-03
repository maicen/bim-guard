# Worked example — the SS316 rule-extraction feedback loop

**What this document is.** A single specification clause, followed end-to-end through the
extraction → validation → expert review → correction loop described in
[`expert_review_process.md`](expert_review_process.md), with the concrete artefact at every step.
It exists because earlier drafts described that loop only in the abstract ("every extracted rule
carries a `needs_review` flag and a source-clause reference, shown to a human reviewer"), which
does not show what the loop actually *catches*, or how a correction propagates back into the
system.

**Provenance — read this before citing any figure below.** Three classes of content appear here,
and they are marked throughout:

* **[verified]** — produced by executing or statically evaluating the current codebase. Every
  claim about `CODE_TO_IFC_MAP`, `IFC_PROPERTY_SET_MAP`, the crevice-engine alias table, the
  CC-001 weights and bands, and the `PipingElement` fixture is in this class, and each is
  reproducible from the file and symbol cited.
* **[designed]** — the LLM responses at each iteration. No live LLM call was made for this
  document: the API-key-dependent path cannot run in the analysis environment. These are the
  failure modes the loop exists to catch, written to the schema the real prompt enforces. They are
  illustrative of the mechanism, not a transcript of a measured run.
* **[open]** — steps of the loop that are specified but not yet implemented in code.

The SS316 clause was chosen because it is the one place where all three components collide: it is
a *rule* (Component 1 extracts it), it is *checkable* (Component 2 evaluates it), and the same
element is independently scored by the *corrosion engine* (Component 3) — which, as the loop
discovers, reaches the opposite conclusion.

---

## 0. The source clause

From a pool and leisure-centre MEP specification, section 23 21 13 (Hydronic Piping):

> **2.4.3** Pool circulation pipework within plant rooms shall be stainless steel to
> ASTM A312 Grade TP316L. Flanged joints shall be full-face gasketed. Pipework shall be
> installed with a minimum 500 mm clearance to permit seismic bracing and maintenance access.

One sentence, three requirements, two of which are not what they appear to be. This is the whole
difficulty of the interpretation gap in miniature.

---

## 1. Iteration 1 — the rule that could not be checked

**LLM output [designed]:**

```json
{
  "ref": "2.4.3",
  "desc": "Pool circulation pipework in plant rooms must be stainless steel 316L",
  "source_text": "Pool circulation pipework within plant rooms shall be stainless steel to ASTM A312 Grade TP316L.",
  "target": "pipework in the pool plant room",
  "property_set": null,
  "property_name": "Material",
  "rule_type": "standard_conformance",
  "operator": "conforms_to",
  "check_value": "ASTM A312 TP316L",
  "unit": null,
  "severity": "mandatory",
  "keyword": "shall",
  "confidence": 0.91,
  "needs_review": false
}
```

**What the system did next [verified].** `RuleGenerator._enrich_target()` walks
`CODE_TO_IFC_MAP` in insertion order and returns on the *first* substring match. Statically
evaluating that map against this target string:

```
_enrich_target('pipework in the pool plant room')  ->  'IfcSpace'
_enrich_target('stainless steel pipework')         ->  'IfcPipeSegment'
```

The key `"room"` sits at index 39 of the 81-entry map; `"pipe"` sits at index 79. First-match-wins
ordering therefore means **any clause whose target text mentions a room resolves to `IfcSpace`
before the pipe keyword is ever reached.** The rule was silently retargeted from the pipework to
the room containing it.

`_enrich_property_set()` then looked up `IfcSpace` in `IFC_PROPERTY_SET_MAP` and filled in the
space Pset. `_validate()` passed — `standard_conformance` requires only `target` and `desc`
(`RULE_TYPE_REQUIRED_FIELDS`, `app/modules/config.py`) — so the rule was saved with
`confidence: 0.91` and `needs_review: false`, and became eligible for evaluation.

**What Component 2 produced.** `NO_ELEMENTS` on every run: no `IfcSpace` in the model carries a
`Material` property matching a pipe specification. A mandatory material requirement was silently
not checked, in exactly the way §1.2.5 of the main report describes for mis-classified elements.

**Expert Review verdict.** Rubric scores T5 · S4 · **M1** · **X1** · C3 → **Rejected**, class
`F3-MAPPING`. The expert's rationale is the important part: *"the rule is semantically right and
structurally useless."* No test would have caught this — the rule is schema-valid, executable,
high-confidence, and wrong.

**Corrective actions.**

| Action | Owner | Status |
|---|---|---|
| Order `CODE_TO_IFC_MAP` longest-key-first, or match on word boundaries, so a specific keyword cannot be pre-empted by a generic one | Process Owner → `app/modules/config.py` | **[open]** — the defect is verified and unfixed |
| Add MEP property sets (`Pset_PipeSegmentTypeCommon`, `Pset_DuctSegmentTypeCommon`, `Pset_ValveTypeCommon`, `Pset_PumpTypeCommon`, `Pset_PipeFittingTypeCommon`) to `IFC_PROPERTY_SET_MAP`, which today carries **no property set for any distribution element** [verified] | Process Owner | **[open]** — work order in `docs/defects/defect_report_map_ordering.md` |
| Instruct the LLM to emit a bare element noun as `target`, never a locative phrase | Prompt | **[designed]** |

---

## 2. Iteration 2 — the rule that checked the wrong thing

With the target corrected to `IfcPipeSegment`, the second output was structurally sound:

**LLM output [designed]:**

```json
{
  "ref": "2.4.3",
  "target": "IfcPipeSegment",
  "property_set": "Pset_PipeSegmentTypeCommon",
  "property_name": "Material",
  "rule_type": "standard_conformance",
  "operator": "conforms_to",
  "check_value": "ASTM A312 TP316L",
  "applies_when": {"building_use": "any", "location": "any"},
  "exceptions": [],
  "confidence": 0.93,
  "needs_review": false
}
```

**Expert Review verdict.** T5 · S4 · M4 · X4 · **C2** → **Amended**, class `F4-SCOPE`. Two
qualifications present in the clause had been dropped: *within plant rooms* (a location scope) and
the full-face-gasket joint requirement (a second, separable rule). `applies_when.location: "any"`
turns a scoped requirement into a blanket one, which in a real coordination review generates false
failures on every pipe in the building and destroys reviewer trust in the tool faster than a
missed check does.

The expert amended `applies_when.location` to `"plant_room"` and raised a second rule for the
gasket requirement. Per the state machine, an `AMENDED` record requires a second independent
reviewer, so the amendment did not self-approve.

**Corrective action.** The clause was added as a RAG few-shot example, so that
`RuleStore.get_rules_sample()` serves it back into `RAG_SYSTEM_PROMPT` on subsequent extractions —
the `F2`/`F4` route in the failure taxonomy. **[open]:** this is a manual step today; nothing
automatically promotes an expert-amended rule into the RAG example pool.

---

## 3. Iteration 3 — where the loop earned its keep

The third iteration passed the rubric and was published. Component 2 then evaluated it against the
plant-room pipework and returned **PASS**: the modelled material is SS316L, exactly as specified.

At the same time, Component 3 scored the same element. Using the `PipingElement` fixture
`example_ss316_pipe_in_plant_room()` [verified, `app/modules/ifc_reader/piping_schema.py`]:

| Field | Value |
|---|---|
| `material` / `material_raw` | `SS316` / "Stainless Steel, Grade 316" |
| `pren` | **25.2** |
| `system` | `PipingSystem.POOL_CIRCULATION` |
| `environment_class` | `EnvironmentClass.T3_CHLORIDE` |
| `operating_temperature_c` | 28.0 |
| `joint_type` | `JT004_FLANGED_FULL_GASKET` |
| `wetted_surface_area_m2` | 8.45 |

CC-001 scores this as `0.35·geometry + 0.40·CCT-adequacy + 0.25·environment`, with bands
Low < 0.30 / Medium / High / Critical > 0.80 [verified, `app/engines/bimguard_crevice_engine.py`].
A full-face gasketed flange in a chloride environment is a textbook crevice geometry, and the
engine's own validation suite carries the directly comparable scenario **CC-VAL-001, "SS316
weld-neck flange in pool plant room, 35°C — expected: Critical"** [verified].

**So the two components disagreed on the same element.** The specification-derived rule says
*compliant*. The standards-derived engine says *Critical*. Neither is malfunctioning:

* Component 2 is correct — the contractor has installed exactly what the specification demanded.
* Component 3 is correct — SS316 at PREN 25.2 is under-specified for chloride service; IMOA
  guidance and the CCT tables place 316 well below what a pool plant room needs, which is why the
  engine's mitigation path recommends duplex 2205 for `swimming_pool` and `coastal` environments
  [verified, `_mitigation()` in `compliance_runner.py`].

**The specification itself is the defect.** This is the single most valuable output the platform
produced in this example, and it is only visible because the two components were kept separate
(§1.3.3, decision 2). A single merged pipeline that treated the specification as ground truth
would have returned PASS and stopped.

**Expert Review verdict on the finding (review object B).** Input fidelity 5 · Term plausibility 5
· Band credibility 5 · Action proportionality 4 → **Approved**, escalated to the design team as an
RFI against clause 2.4.3 rather than as a model defect.

---

## 4. Iteration 4 — the correction that closed the loop

The design team's response was to revise the specification to a performance requirement. The
revised clause was re-extracted, and the loop converged:

**LLM output, approved and published [designed]:**

```json
{
  "ref": "2.4.3r1",
  "desc": "Pool circulation pipework in plant rooms must have PREN >= 32 (duplex 2205 or better)",
  "source_text": "Pool circulation pipework within plant rooms shall be austenitic-ferritic stainless steel with a pitting resistance equivalent number (PREN) of not less than 32.",
  "target": "IfcPipeSegment",
  "property_set": "Pset_PipeSegmentTypeCommon",
  "property_name": "PREN",
  "fallback_property": "Material",
  "rule_type": "numeric_comparison",
  "operator": ">=",
  "check_value": 32,
  "unit": "ratio",
  "applies_when": {"building_use": "any", "location": "plant_room"},
  "exceptions": ["Pipework downstream of the final dechlorination stage"],
  "severity": "mandatory",
  "confidence": 0.88,
  "needs_review": true,
  "extraction_method": "llm"
}
```

Three things changed structurally, and they are the reusable lesson:

1. **`standard_conformance` became `numeric_comparison`.** A named grade is a proxy for a
   property; the property is what is actually checkable. `conforms_to` can only ever be evaluated
   by string matching, and a rule that can only string-match cannot detect an under-specification.
2. **`fallback_property` was populated.** Most IFC exports will not carry a `PREN` property, so
   the rule degrades to a material-name check rather than to `MISSING_DATA` — the same
   property-then-geometry fallback philosophy `ifc_geometry.py` applies to architectural
   dimensions (§1.2.5).
3. **`needs_review` was set `true` despite `confidence: 0.88`.** The expert set it manually on
   the grounds that the exception clause is a judgement call. This is the one place where the
   human overrides the model's own confidence in the *conservative* direction, and the state
   machine supports it — though **[open]**, today the flag does not gate evaluation.

Re-running Component 3 against the amended element (duplex 2205, PREN 35) moves the CC-001 band
from Critical to Medium, consistent with the engine's own `CC-VAL-003` scenario ("Duplex 2205 butt
weld, coastal, 20°C — expected: Medium") [verified].

---

## 5. What the loop produced, summarised

| Iteration | Rubric outcome | Failure class | What it changed |
|---|---|---|---|
| 1 | Rejected (M1, X1) | `F3-MAPPING` | Exposed a verified ordering defect in `CODE_TO_IFC_MAP`; MEP Psets absent from `IFC_PROPERTY_SET_MAP` |
| 2 | Amended (C2) | `F4-SCOPE` | Location scope restored; gasket requirement split into its own rule; clause added as a RAG example |
| 3 | Approved (rule) + Approved (finding) | `F6-ENGINE` (raised, not upheld) | Surfaced the component disagreement; RFI raised against the specification itself |
| 4 | Approved, published | — | Grade-based rule replaced by a property-based rule with a fallback and an explicit exception |

**Three transferable findings:**

1. **A rule can be schema-valid, high-confidence and useless.** Iteration 1 passed every automated
   check the system has. The only thing standing between it and a silently unchecked mandatory
   requirement was a human asking "can this be checked against the model?" — which is why
   IFC-mappability is a distinct rubric dimension with its own veto holder.
2. **The most valuable output was a disagreement, not a failure.** Keeping specification-derived
   rules and standards-derived scoring as separate components is what made it visible. This is the
   strongest available evidence for design decision 2 in §1.3.3.
3. **`standard_conformance` rules are a smell.** Every clause naming a grade, product or standard
   should be interrogated for the underlying measurable property. Where one exists, extracting it
   as `numeric_comparison` against that property yields a rule that can detect the case the
   grade-based rule cannot: correct compliance with an incorrect specification.

**And one uncomfortable one:** the loop as exercised here depended at four separate points on a
human doing something the codebase does not yet record — assigning a review, scoring a rubric,
tagging a failure class, and promoting an amended rule into the RAG pool. Those four gaps are
precisely the "minimum viable implementation" list in section 6 of the Expert Review process
document, and this case study is the argument for building them. The two enrichment defects it
exposed are written up separately as [`defect_report_map_ordering.md`](defects/defect_report_map_ordering.md),
with a runnable reproduction, a staged fix and the invariants that would stop them recurring.
