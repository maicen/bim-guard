# Defect report — element-name enrichment silently resolves MEP clauses to architectural IFC classes

| Field | Value |
|---|---|
| **ID** | BG-DEF-001 |
| **Component** | Component 1 — rule extraction (Module 3) |
| **Files** | `app/modules/rule_builder/rule_generator.py` (`_enrich_target`, `_enrich_property_set`), `app/modules/config.py` (`CODE_TO_IFC_MAP`, `IFC_PROPERTY_SET_MAP`) |
| **Severity** | High — produces silent false negatives in a compliance tool |
| **Status** | Open. Verified present at commit `f8d9f34`. **No code change has been made**: `app/` is locked while engine work is in flight, so this document is the work order. |
| **Discovered by** | The SS316 feedback-loop worked example (`docs/ss316_feedback_loop_case_study.md`, §1.3.4 of the submission draft) |
| **Related** | Submission draft §1.4.6, limitations 21 and 22 |

---

## 1. Summary

`RuleGenerator._enrich_target()` converts a free-text element name from an LLM-extracted rule into
an IFC class by taking the **first substring match** over `CODE_TO_IFC_MAP`, iterated in dictionary
insertion order. The map is grouped by discipline with architectural keywords first and the handful
of MEP keywords appended last, so **a generic or architectural keyword occurring anywhere in the
target string pre-empts the specific MEP keyword that names the actual element.**

The consequence is not a visible error. The mis-targeted rule passes validation, saves with high
confidence, and is evaluated forever after against the wrong IFC class — where it matches nothing
and reports `NO_ELEMENTS`. A mandatory requirement is silently never checked. For a tool whose
central claim is auditable compliance, a false negative that produces no error, no log line and no
review flag is the worst available failure mode.

A second, compounding defect: `IFC_PROPERTY_SET_MAP` contains **no property set for any
distribution element**, so even a correctly-targeted MEP rule cannot have its `property_set`
auto-filled.

---

## 2. Minimal reproduction

Reproducible without network access or credentials, by evaluating the maps statically. `config.py`
performs I/O at import time, so the reproduction reads the literals with `ast` rather than
importing the module; the resolution loop below is a line-for-line transcription of
`_enrich_target()`.

The script below is checked in at [`repro_bg_def_001.py`](repro_bg_def_001.py) and exits non-zero
while the defect is present, so it doubles as a regression gate:

```console
$ uv run python docs/defects/repro_bg_def_001.py ; echo "exit=$?"
...
BG-DEF-001 present: 7 failing check(s)
exit=1
```

```python
# docs/defects/repro_bg_def_001.py (abridged)
import ast

tree = ast.parse(open("app/modules/config.py").read())
maps = {
    n.targets[0].id: [
        (ast.literal_eval(k), ast.literal_eval(v))
        for k, v in zip(n.value.keys, n.value.values)
    ]
    for n in tree.body
    if isinstance(n, ast.Assign)
    and isinstance(n.targets[0], ast.Name)
    and n.targets[0].id in ("CODE_TO_IFC_MAP", "IFC_PROPERTY_SET_MAP")
    and isinstance(n.value, ast.Dict)
}

def enrich_target(target: str) -> str:
    """Transcription of RuleGenerator._enrich_target()."""
    if target.startswith("Ifc"):
        return target
    lowered = target.lower()
    for keyword, ifc_class in maps["CODE_TO_IFC_MAP"]:
        if keyword in lowered:          # first match wins, insertion order
            return ifc_class
    return target

for t in [
    "pipework in the pool plant room",
    "plant room pipework",
    "duct in the riser room",
    "valve in the plant room",
    "pump in the tank room",
    "stainless steel pipework",
]:
    print(f"{t!r:36} -> {enrich_target(t)!r}")
```

### Observed output (verified at `f8d9f34`)

```
'pipework in the pool plant room'     -> 'IfcSpace'
'plant room pipework'                 -> 'IfcSpace'
'duct in the riser room'              -> 'IfcStairFlight'
'valve in the plant room'             -> 'IfcSpace'
'pump in the tank room'               -> 'IfcSpace'
'stainless steel pipework'            -> 'IfcPipeSegment'
```

Only the last line is correct, and only because it happens to contain no architectural keyword.

`'duct in the riser room' -> 'IfcStairFlight'` is the clearest illustration: **"riser" is a stair
keyword at index 3 and a services term in every MEP specification ever written.** A duct rule
becomes a stair-flight rule.

---

## 3. Root cause

```python
# rule_generator.py — _enrich_target(), current behaviour
target_lower = target.lower()
for keyword, ifc_class in CODE_TO_IFC_MAP.items():
    if keyword in target_lower:
        rule["target"] = ifc_class
        return rule
```

Three independent problems compose:

**3.1 Resolution order is an accident of file layout.** Python dictionaries preserve insertion
order, and `CODE_TO_IFC_MAP`'s 81 entries are grouped by discipline for human readability — stairs,
doors, windows, glazing, ramps, railings, walls, ceilings, roofs, slabs, spaces, then, at indices
77–80, the four MEP keywords. Resolution priority is therefore whatever order made the file easiest
to read. Verified indices:

| Keyword | Index | Resolves to |
|---|---:|---|
| `riser` | 3 | `IfcStairFlight` |
| `space` | 38 | `IfcSpace` |
| `room` | 39 | `IfcSpace` |
| `sprinkler` | 77 | `IfcFlowTerminal` |
| `diffuser` | 78 | `IfcFlowTerminal` |
| `pipe` | 79 | `IfcPipeSegment` |
| `duct` | 80 | `IfcDuctSegment` |

Any target naming the room an element sits in resolves to the room, because `room` is at 39 and
`pipe` is at 79.

**3.2 Matching is unanchored substring containment.** `keyword in target_lower` matches inside
words as well as across them, so `"flooring"` matches `floor`, `"doorway"` matches `door` (harmless
here, but by luck), and `"riser room"` matches `riser`. Nothing requires the match to fall on a
word boundary, let alone on the head noun.

**3.3 Ambiguity is resolved silently.** When several keywords match, the function picks one and
returns. It records nothing: no `needs_review`, no confidence penalty, no log line, no list of the
alternatives it discarded. This is the defect that turns a mis-resolution into a *silent* one, and
it is the most important of the three to fix.

### 3.4 The compounding defect — no MEP property sets

`_enrich_property_set()` fills `property_set` by looking the resolved IFC class up in
`IFC_PROPERTY_SET_MAP`. That map holds 20 entries at `f8d9f34`:

```
IfcStairFlight, IfcDoor, IfcWindow, IfcRailing, IfcRamp, IfcRampFlight, IfcSlab,
IfcWall, IfcCurtainWall, IfcSpace, IfcCovering, IfcRoof, IfcColumn, IfcBeam,
IfcMember, IfcFooting, IfcSanitaryTerminal, IfcAlarm, IfcSensor, IfcFlowTerminal
```

Four of those (`IfcSanitaryTerminal`, `IfcAlarm`, `IfcSensor`, `IfcFlowTerminal`) are MEP terminals
added upstream since this defect was first recorded, so the earlier characterisation of the map as
"entirely architectural" is no longer accurate and should be read as superseded by this document.
The gap that remains is specific and unchanged: **no distribution element has a property set.**
`IfcPipeSegment` and `IfcDuctSegment` are both reachable from `CODE_TO_IFC_MAP` and neither has an
entry here, and `IfcValve`, `IfcPump` and `IfcPipeFitting` are absent from both maps. A
correctly-targeted `IfcPipeSegment` rule still gets no property set. The reproduction script checks
this automatically, so the two maps can no longer drift apart unnoticed.

### 3.5 Keywords that are absent entirely

`valve`, `fitting`, `pump` and `flange` do not appear in `CODE_TO_IFC_MAP` at all. A clause about a
valve can only ever resolve via some other word in its target string — which, per 3.1, will
usually be the room.

---

## 4. Impact

**Blast radius.** Every LLM-extracted rule whose target text names a location — which is most MEP
clauses, because specifications are written as *"pipework within plant rooms shall…"* — and every
rule about a valve, fitting, pump or flange.

**Failure mode.** Silent. The mis-targeted rule:

1. passes `_validate()`, because `target` is non-empty and structurally valid;
2. saves with whatever confidence the LLM assigned (0.91 in the SS316 case);
3. does **not** set `needs_review`, so it never reaches the reviewer queue;
4. evaluates to `NO_ELEMENTS` on every run, which the comparator reports as an absence of
   applicable elements rather than as a failure.

**Why the existing safeguards do not catch it.** The `needs_review` flag keys off the LLM's own
confidence, and the model is legitimately confident — it extracted the clause correctly. The
corruption happens downstream, in enrichment. Traceability (`ref`, `source_text`) is intact and
correct, and points at the right clause. Every mechanism the platform has for catching bad rules
is looking somewhere else. In the SS316 case only a human asking "can this actually be checked
against the model?" caught it, which is why IFC-mappability is a distinct dimension in the Expert
Review rubric (`docs/expert_review_process.md`, section 4) with its own veto holder.

**Detecting rules already affected.** Any saved rule whose `target` is a spatial class while its
`source_text` names a distribution element is a candidate. A triage query over the rule store:

```sql
SELECT id, ref, target, property_name, source_text
FROM   rules
WHERE  target IN ('IfcSpace', 'IfcZone', 'IfcStairFlight')
AND    (source_text ILIKE '%pipe%' OR source_text ILIKE '%duct%'
     OR source_text ILIKE '%valve%' OR source_text ILIKE '%pump%'
     OR source_text ILIKE '%flange%' OR source_text ILIKE '%pipework%');
```

Every hit should be re-reviewed, not auto-corrected: the fix changes what the rule *checks*, which
is a decision for a Reviewing Expert under the process in `expert_review_process.md`.

---

## 5. Proposed fix

Ordered so that each step is independently shippable and testable. Steps 1–3 are the defect fix;
4–5 close the compounding gap; 6 is the durable guard.

### Step 1 — Match on word boundaries

Replace substring containment with a word-boundary regex, so `"flooring"` no longer matches
`floor`. Compile once at import; the map is static.

```python
_KEYWORD_PATTERNS = {kw: re.compile(rf"\b{re.escape(kw)}\b") for kw in CODE_TO_IFC_MAP}
```

### Step 2 — Resolve by specificity, not by file order

Collect **every** matching keyword, then rank. Two ranking keys, applied in order:

1. **Tier.** Spatial containers lose to the things inside them. A target that names both a
   distribution element and a room is a rule about the element.

   ```python
   CONTAINER_CLASSES = {"IfcSpace", "IfcZone", "IfcBuildingStorey"}
   tier = 0 if ifc_class in CONTAINER_CLASSES else 1
   ```

2. **Keyword length, descending.** Longest match wins within a tier, so a multi-word phrase
   (`"services riser"`) beats its own components (`"riser"`). This makes resolution independent of
   where an entry sits in the file — the property whose absence is the root cause.

Add the multi-word phrases the tiering needs, ahead of their components:
`"services riser"`, `"riser room"`, `"plant room"`, `"pipe riser"`, `"duct riser"`.

### Step 3 — Refuse to guess, and say so

When two keywords survive ranking at the same tier and length — `"duct in the riser room"` after
`riser room` is added, for example — **do not pick one**. Return the target unresolved and record
the ambiguity on the rule:

```python
rule["target"] = target                   # left unresolved, deliberately
rule["needs_review"] = True
rule["confidence"] = min(rule.get("confidence", 1.0), 0.5)
rule["review_note"] = f"Ambiguous element target: matched {sorted(candidates)}"
```

This is the change that converts a silent false negative into a visible review item, and it is
worth more than steps 1 and 2 combined. It also matches the platform's stated posture everywhere
else: surface ambiguity to a human rather than smoothing it away.

### Step 4 — Add the missing MEP keywords

To `CODE_TO_IFC_MAP`: `valve → IfcValve`, `fitting → IfcPipeFitting`, `pump → IfcPump`,
`flange → IfcPipeFitting`, `pipework → IfcPipeSegment`, `ductwork → IfcDuctSegment`.
With step 2 in place, the insertion position no longer matters.

### Step 5 — Add the missing MEP property sets

To `IFC_PROPERTY_SET_MAP`:

| IFC class | Property set | Note |
|---|---|---|
| `IfcPipeSegment` | `Pset_PipeSegmentTypeCommon` | Standard IFC4 |
| `IfcDuctSegment` | `Pset_DuctSegmentTypeCommon` | Standard IFC4 |
| `IfcValve` | `Pset_ValveTypeCommon` | Standard IFC4 |
| `IfcPump` | `Pset_PumpTypeCommon` | Standard IFC4 |
| `IfcPipeFitting` | `Pset_PipeFittingTypeCommon` | **See note below** |

> **Note on `Pset_FlangeTypeCommon`.** This was requested by name, but it is not a property set in
> the IFC4 schema, and `IfcFlange` is not an IFC entity. Flanged joints are modelled as
> `IfcPipeFitting` (or `IfcDiscreteAccessory` for the hardware), whose standard property set is
> `Pset_PipeFittingTypeCommon`. Adding a non-existent Pset name would reintroduce the same class of
> silent failure this report is about — the rule would validate and then match nothing — so the
> standard name is proposed instead. If a project genuinely carries a custom `Pset_FlangeTypeCommon`
> in its exports, it belongs in a project-specific override, not in the platform defaults. **This
> substitution should be confirmed against the project's actual IFC deliverables before the fix
> lands.**

### Step 6 — Make the maps self-checking

Add a consistency test (see 6.3) asserting that every distribution-element class reachable from
`CODE_TO_IFC_MAP` has an entry in `IFC_PROPERTY_SET_MAP`. The two maps are edited independently
today and drifted apart precisely because nothing tied them together.

---

## 6. Test cases that would pin the fix

To live in `tests/test_rule_enrichment.py`. They are written against `_enrich_target` and
`_enrich_property_set` directly; the modules under test must be importable without network access
for these to run in CI, which today they are not — see section 7.

### 6.1 Regression cases — the defect itself

| # | Input `target` | Current (broken) | Expected after fix |
|---|---|---|---|
| R1 | `"pipework in the pool plant room"` | `IfcSpace` | `IfcPipeSegment` |
| R2 | `"plant room pipework"` | `IfcSpace` | `IfcPipeSegment` |
| R3 | `"duct in the riser room"` | `IfcStairFlight` | ambiguous → unresolved + `needs_review` |
| R4 | `"valve in the plant room"` | `IfcSpace` | `IfcValve` |
| R5 | `"pump in the tank room"` | `IfcSpace` | `IfcPump` |
| R6 | `"flanged joint on the header"` | unresolved | `IfcPipeFitting` |
| R7 | `"services riser"` | `IfcStairFlight` | `IfcDuctSegment` or unresolved — **not** a stair |

### 6.2 Cases that must not regress

| # | Input `target` | Expected | Guards against |
|---|---|---|---|
| N1 | `"stair riser"` | `IfcStairFlight` | Over-correcting: a real stair keyword must still win |
| N2 | `"door"` | `IfcDoor` | Basic resolution |
| N3 | `"IfcPipeSegment"` | `IfcPipeSegment` | Early return for already-valid classes |
| N4 | `"corridor"` | existing behaviour | Architectural resolution unaffected |
| N5 | `"flooring finish"` | **not** `IfcSlab` via `floor` | Word-boundary matching (step 1) |
| N6 | `"curtain wall"` | `IfcCurtainWall`, not `IfcWall` | Longest-match ranking (step 2) |

N6 is worth keeping even though it passes today: it passes *by insertion order* (the comment in
`config.py` says "Multi-word phrases must come before their component words so they win first"),
and after step 2 it must pass *by rule*. A test that changes its reason for passing is exactly what
pins a refactor.

### 6.3 Invariants — the tests that stop this recurring

| # | Property | Why |
|---|---|---|
| I1 | **Order independence.** Resolution results are unchanged when `CODE_TO_IFC_MAP` is rebuilt with its items shuffled (fixed seed). | Directly encodes the root cause. If this passes, the defect cannot come back. |
| I2 | **Map consistency.** Every distribution-element class in `CODE_TO_IFC_MAP.values()` has a key in `IFC_PROPERTY_SET_MAP`. | Stops the two maps drifting apart again (3.4). |
| I3 | **No silent container fallback.** For every target string containing both an element keyword and a container keyword, the result is never a container class. | The defect's signature, stated generally. |
| I4 | **Ambiguity is visible.** Any target that matches two same-tier, same-length keywords yields `needs_review == True` and a populated `review_note`. | Step 3 — the part that matters most. |
| I5 | **Pset names are real.** Every value in `IFC_PROPERTY_SET_MAP` matches `^Pset_[A-Za-z]+$` and appears in a checked-in list of IFC4 standard property sets. | Would have caught `Pset_FlangeTypeCommon` before it shipped. |

### 6.4 Suggested shape

```python
@pytest.mark.parametrize("target,expected", [
    ("pipework in the pool plant room", "IfcPipeSegment"),
    ("plant room pipework",             "IfcPipeSegment"),
    ("valve in the plant room",         "IfcValve"),
    ("pump in the tank room",           "IfcPump"),
    ("stair riser",                     "IfcStairFlight"),
    ("curtain wall",                    "IfcCurtainWall"),
])
def test_target_resolution(target, expected):
    assert RuleGenerator(None)._enrich_target({"target": target})["target"] == expected


def test_resolution_is_order_independent():
    """I1 — the root cause, stated as an executable property."""
    items = list(CODE_TO_IFC_MAP.items())
    random.Random(20260819).shuffle(items)
    shuffled = dict(items)
    for target, _ in CASES:
        assert resolve(target, CODE_TO_IFC_MAP) == resolve(target, shuffled)


def test_ambiguous_target_is_flagged_not_guessed():
    """I4 — the change that converts a silent failure into a review item."""
    rule = RuleGenerator(None)._enrich_target({"target": "duct in the riser room"})
    assert rule["needs_review"] is True
    assert "riser" in rule["review_note"]
```

---

## 7. Prerequisite, and why these tests cannot run today

`app/modules/config.py` performs network I/O at import time — it reads settings through
`PersistenceService`, which requires `SUPABASE_URL` and reaches Supabase. Importing it without
credentials raises `ValueError: SUPABASE_URL is required`; importing it with placeholder
credentials raises a proxy error. **Every test in section 6 is blocked on that**, which is why this
report's own reproduction reads the map literals with `ast` instead of importing them.

The fix is small and worth doing first: move the two literal maps (and the other pure constants) out
of `config.py` into a module with no imports beyond the standard library — `app/modules/ifc_maps.py`
— and have `config.py` re-export them. Pure data becomes importable, testable and CI-runnable, and
the settings/network concern stays where it belongs. This is a prerequisite for step 6 and for the
whole of section 6, and it is the reason the enrichment layer has no test coverage today.

---

## 8. Work order checklist

- [ ] Extract `CODE_TO_IFC_MAP` and `IFC_PROPERTY_SET_MAP` into an import-safe module (section 7)
- [ ] Step 1 — word-boundary matching
- [ ] Step 2 — tiered, longest-match-first resolution
- [ ] Step 3 — flag ambiguity instead of guessing (**highest value; do not defer**)
- [ ] Step 4 — add `valve`, `fitting`, `pump`, `flange`, `pipework`, `ductwork` keywords
- [ ] Step 5 — add MEP property sets, with `Pset_PipeFittingTypeCommon` confirmed against project deliverables
- [ ] Step 6 — invariants I1–I5 as tests, and make `repro_bg_def_001.py` exit zero
- [ ] Run the triage query in section 4 and re-review every affected saved rule through the Expert Review process
- [ ] Update submission draft §1.4.6 limitations 21 and 22, and `docs/ss316_feedback_loop_case_study.md`, once the fix lands
