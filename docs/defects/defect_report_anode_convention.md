# Defect Report — Galvanic Anode Convention Contradiction

**Status:** RESOLVED — verified against data, both engines corrected, regression tests added.
**Severity as found:** HIGH if the live engine had been wrong. It was not.
**Evidence level:** **verified against the seeded GC-001 payload** (recovered from git history),
not inference. See [Verification](#verification--run-and-decisive) for the drift caveat.

---

## Verdict

**The live engine was right. The dormant one was wrong.** This is the opposite of what the first
version of this report concluded from circumstantial evidence, and the correction is recorded in
full below rather than quietly replaced.

| Location | Convention it applied | Verdict |
|---|---|---|
| [`bimguard_corrosion_engine.py:353`](../../app/engines/bimguard_corrosion_engine.py) — **live** | more positive = anodic | **CORRECT** |
| [`galvanic.py:190`](../../app/modules/comparator/galvanic.py) — dormant, Path B | more negative = anodic | **WRONG — fixed** |

Because the wrong engine was never wired up, **no user-facing galvanic finding ever named the wrong
material**, and no previously issued report needs reissuing. The earlier draft's worst case did not
happen.

A **separate, real defect in the live engine** was found while confirming this, and is fixed here
too: the anode/cathode swap moved materials, potentials and GUIDs but left the surface areas
behind, inverting the area ratio. See [The area defect](#the-area-defect--separate-and-real).

---

## Summary of the original contradiction

Two engines read the **same** galvanic series and applied **opposite** conventions for deciding
which material is the anode. They could not both be right.

The anode is the material that **corrodes**. Naming it backwards inverts the finding: the report
tells the engineer to protect or substitute the component that was never at risk, while the one
actually dissolving is described as the safe half of the couple.

---

## Verification — run, and decisive

```bash
uv run python scripts/verify_anode_convention.py --from-seeder
```

### Provenance of the data

`ruleset_seeder.py` holds **no series literals**. It calls
`StaticDataService().get_asset_json("ruleset:BIMGUARD-GC-001")`, so it consumes the same database
asset the engines read rather than defining it. The origin of that asset is the JSON payload
uploaded to it, checked in at `data/rulesets/galvanic_corrosion_ruleset.json` until it was deleted
from the tree in commit `ebb0e83`. The script recovers it from git at `ebb0e83^`.

> **Drift caveat.** This is the payload as last committed. If anyone edited the database asset
> after seeding, the engines read something else and this verdict does not describe the running
> system. The live-database mode of the script (no `--from-seeder`) settles that when credentials
> are available, and remains in place for exactly that purpose. Nothing observed suggests drift —
> the recovered payload's own note matches the live engine's behaviour — but it has not been
> excluded.

### The series is an anodic index, not an electrode-potential table

This is what the first version of this report got wrong. All 20 entries are **positive**, ascending
from platinum at 0.00 to magnesium at 0.95, and the payload carries its own convention note:

> `"note": "Lower potential = more noble (cathodic). Higher potential = more active (anodic) — corrodes preferentially."`

### Check 1 — the `noble` flag

| Group | n | Mean potential |
|---|---:|---:|
| noble (cathodic) | 9 | **+0.100 V** |
| active (anodic) | 11 | **+0.577 V** |

Active materials sit **higher**. → more positive is anodic.

### Check 2 — zinc against copper (physics anchor)

| Material | Potential | Role |
|---|---:|---|
| `zinc` | **+0.800 V** | known anode — galvanising sacrifices it |
| `copper` | **+0.280 V** | known cathode |

The known anode sits **higher**. → more positive is anodic.

Both checks agree: **`more_positive_is_anodic`**.

### Why the original inference was wrong

The first version argued that WorldStainless / Euro Inox and AUCSC publish galvanic series as
electrode potentials in seawater, where more negative is more anodic — which is true of those
publications. The reasoning failed at the next step: **the table in this project is not in the form
its sources publish.** Whoever authored it converted the ordering into an all-positive ascending
index and wrote a note saying so. The cited source tells you where the ordering came from, not what
sign convention the transcription used. Reading the note, or the values, would have settled it in
seconds; reading the citation could not.

The lesson generalises past this defect: for a table whose convention is ambiguous, the data
carries the answer and the provenance does not.

---

## A genuine inconsistency in the series, recorded

One adjacent pair disagrees with itself:

| Material | Potential | `noble` |
|---|---:|---|
| `ss316_active` | +0.22 | `false` (active) |
| `copper` | +0.28 | `true` (noble) |

By the potential ordering, copper (0.28) is **more anodic** than active 316 (0.22). By the flags,
active 316 is the anodic one. For this specific couple the two discriminators give opposite
answers.

This does not affect the verdict — the group means are far apart (0.100 against 0.577) and the
zinc/copper anchor is unambiguous — but it does mean the series has a narrow overlap band where the
flag and the number disagree. It is logged here as a data-quality finding for the corrosion
reviewer, not fixed: changing a published series entry is an engineering decision, not a code fix.

It also **vindicates XM-001's design**. `cross_material.py` resolves the anode from the `noble`
flag first and only falls back to the declared convention, so it is unaffected by this overlap
where a potential-sign comparison would silently pick the wrong side.

---

## Fixes applied

### 1. `galvanic.py` — wrong convention (dormant Path B comparator)

```python
# Before — assumed an electrode-potential series
if v_a < v_b:
    anode, cathode = element_a, element_b
    voltage_v = abs(v_b - v_a)
else:
    anode, cathode = element_b, element_a
    voltage_v = abs(v_a - v_b)

# After — the series is an anodic index; higher is the anode
if v_a > v_b:
    anode, cathode = element_a, element_b
else:
    anode, cathode = element_b, element_a
voltage_v = abs(v_a - v_b)
```

The magnitude is hoisted out of the branches: `abs()` makes it convention-independent, so it should
never have been computed twice. The comment that asserted the old convention was replaced, not
left standing — it was the claim under test.

**The area ratio needed no separate fix here.** `_compute_area_ratio(anode, cathode)` reads the
areas off the resolved element *objects*, so correcting the direction carries the areas with it.

### 2. `bimguard_corrosion_engine.py` — the area defect (live engine)

See below. One addition to the existing swap block.

### 3. Regression tests

`tests/test_anode_convention.py`, 8 tests:

| Test | Pins |
|---|---|
| `test_galvanised_steel_is_the_anode_against_copper` (×2 orders) | The physics anchor, independent of argument order |
| `test_copper_is_the_anode_against_stainless` | A second pair, so it cannot pass by always picking one material |
| `test_voltage_gap_is_direction_independent` | Magnitude does not depend on order |
| `test_area_ratio_follows_the_resolved_anode` | The ratio tracks the resolved anode, not the caller's labelling |
| `test_seeded_series_still_says_higher_is_anodic` | The convention **at the data**, so re-authoring the series in the other convention fails the build |
| `test_verify_script_runs_and_reports_the_expected_convention` | The verification script's own verdict |
| `test_live_engine_swaps_areas_with_materials` | The area fix — skips without database credentials |

The last test asserts on the **resolved** anode after the engine's internal swap, not on the input
ordering, or it would pass regardless of the bug.

### 4. `tests/test_cross_material.py` — fixture authored in the wrong convention

Approving the pack turned one XM-001 test red, which is exactly what an approval should do if
something downstream disagreed with it. `TEST_SERIES` was authored in electrode-potential form —
all negative, galvanised steel at −1.00 down to titanium at 0.00 — the opposite convention from the
data the engines read.

The relative ordering was right, so every verdict in the file held and nothing was mis-tested. But
**a fixture in the wrong convention cannot catch a convention defect**, which is the one thing that
file most needs to catch. It was re-authored onto the real values (galvanised steel 0.82 down to
titanium 0.05), and all 39 tests in the file passed unchanged — confirming the ordering, not the
signs, was carrying them.

Three tests keep deliberately contrary-signed local series, now commented as such:
`test_convention_direction_is_honoured` proves the resolver follows the pack's declaration rather
than any property of the numbers, and two others rely only on `abs(gap)` and the noble flags. Those
are correct as contrived values.

---

## The area defect — separate, and real

Found while confirming the convention. Independent of it, and in the **live** engine.

`assess_galvanic_risk()` reorders the couple when the caller's labelling disagrees with the series.
It swapped the material keys, the potentials and the GUIDs — but not the areas:

```python
anode_key, cathode_key = cathode_key, anode_key
anode_potential, cathode_potential = cathode_potential, anode_potential
element.global_id_anode, element.global_id_cathode = (...)
# element.anode_area_m2 / cathode_area_m2 left untouched
...
ar_band, ar_risk = classify_area_ratio(element.anode_area_m2, element.cathode_area_m2)
```

After a swap the areas belong to the original assignment while the materials belong to the swapped
one, so `classify_area_ratio()` receives the ratio inverted. A small anode against a large cathode
is the dangerous case and carries the highest area-ratio risk; inverted, it reports as the safe
one. Because area ratio carries a **0.30 weight** in the GC-001 composite, this moves the *score*
and therefore the risk band, not just a label.

**Fix:** swap the areas alongside everything else.

```python
element.anode_area_m2, element.cathode_area_m2 = (
    element.cathode_area_m2,
    element.anode_area_m2,
)
```

**Live exposure is currently limited but not zero.** `compliance_runner.py` builds every `GCElement`
from a single `ServiceElement`, with `global_id_anode == global_id_cathode` and both areas taken
from the same element, so today the swap usually moves identical values. The moment real pairwise
data flows — which is exactly what `piping_producer` plus XM-001 deliver — the two areas differ and
the defect bites. Fixing it now is cheaper than finding it then.

---

## Consequences for XM-001

`series_convention` in [`xm_001_cross_material.json`](../../data/rulesets/xm_001_cross_material.json)
is set to `more_positive_is_anodic`, its `MUST_VERIFY` note replaced by the verification record,
and the pack moved from DRAFT to APPROVED v1.0 with the drift caveat carried as a limitation.

XM-001's behaviour is unchanged by all of this: it resolves direction from the `noble` flag and
takes magnitude from `abs(gap)`, both convention-independent. The declared convention is only the
tiebreaker for couples where both materials carry the same flag.

---

*Raised during XM-001 implementation. Verified and fixed once the seeded payload was recovered from
git history, after the live database proved unreachable.*
