# Defect Report — Galvanic Anode Convention Contradiction

**Status:** OPEN — reported, not fixed (fix deferred until XM-001 lands)
**Severity:** HIGH if confirmed — every GC-001 BCF issue would name the wrong victim
**Confidence:** Evidence is strong but **circumstantial**. The decisive check requires
database access and has not been run. See [Verification](#verification-not-yet-run).

---

## Summary

Two engines read the **same** galvanic series and apply **opposite** conventions for
deciding which material is the anode. They cannot both be right.

| Location | Logic | Implies |
|---|---|---|
| [`galvanic.py:190`](../../app/modules/module4_comparator/galvanic.py) | `if v_a < v_b: anode = a` — comment: "Identify anode (more negative)" | **more negative = anodic** |
| [`bimguard_corrosion_engine.py:353`](../../app/engines/bimguard_corrosion_engine.py) | swaps so `anode_potential > cathode_potential` — comment: "less noble = higher potential" | **more positive = anodic** |

The anode is the material that **corrodes**. Naming it backwards inverts the finding:
the report tells the engineer to protect or substitute the component that was never at
risk, while the one actually dissolving is described as the safe half of the couple.

## Why this matters more than a normal defect

`bimguard_corrosion_engine.py` is the **live** GC-001 engine. It is wired into
[`compliance_runner.py:112`](../../app/modules/module4_comparator/compliance_runner.py)
via `assess_galvanic_risk` and produces the BCF issues that reach users.

`galvanic.py` is the Path B comparator. Nothing calls it — no rule-pack loader exists
for it yet. It is dormant.

So the two outcomes are not symmetric:

- **If the live engine is right** — no user-facing defect. Dormant `galvanic.py` carries
  a latent bug to fix before Path B is wired up.
- **If the live engine is wrong** — every galvanic BCF issue ever exported names the
  wrong material. That is a pre-submission MUST-FIX, and previously issued reports may
  need reissuing.

## Evidence that the LIVE engine is the wrong one

This is the direction the available evidence points, and it is the worse case.

**1. The series source uses electrode potentials, not anodic indices.**

[`bimguard_corrosion_engine.py:6-8`](../../app/engines/bimguard_corrosion_engine.py)
names the series sources:

> WorldStainless / Euro Inox (2025) — galvanic series, corrosion rate data
> AUCSC Basic Corrosion Course (2024) — galvanic series, electrolyte conductivity

Both publish galvanic series as **electrode potentials measured in seawater**
(V vs SCE or Ag/AgCl), where **more negative is more anodic** — zinc around −1.0 V,
carbon steel around −0.6 V, copper around −0.36 V, passive 316 around −0.05 V.

[`ruleset_seeder.py:167`](../../app/services/ruleset_seeder.py) confirms the attribution:
`mat_src = gc["galvanic_series"].get("source", "WorldStainless / Euro Inox")`.

**2. NASA-STD-6012 is cited for thresholds only, not for the series.**

The engine header attributes NASA-STD-6012 specifically to "voltage thresholds by
environment class". NASA-STD-6012 / MIL-STD-889 use an *anodic index* where a **higher**
number is more anodic — the convention `bimguard_corrosion_engine.py:353` appears to
assume. But that standard is not the source of this table; the seeder attributes the
series to WorldStainless / Euro Inox.

**A plausible origin for the defect:** the author had NASA-STD-6012 open for the
threshold values and carried its anodic-index convention across to a table that is not
built on it.

**3. Material keys read as electrode potentials.**

Series keys are `ss316_passive`, `ss304_passive`
([`bimguard_corrosion_engine.py:47-70`](../../app/engines/bimguard_corrosion_engine.py)).
"Passive" describes a measured electrode state — the vocabulary of a potential series,
not of an anodic index table.

**Conclusion from evidence:** the table is most likely in electrode-potential convention
(more negative = anodic), which makes **`galvanic.py:190` correct** and the **live
`bimguard_corrosion_engine.py:353` wrong**.

**This remains an inference.** It has not been confirmed against the data.

## Verification (NOT YET RUN)

The check requires reading the series, which lives only in the Supabase static asset
`ruleset:BIMGUARD-GC-001`. It is in no repository file.

Attempted and failed:

```
uv run python -c "from app.services.corrosion_rule_catalog import load_gc_catalog; load_gc_catalog()"
ValueError: SUPABASE_URL is required
```

There is no `.env` in the repository, and placeholder credentials fail DNS resolution.

### Test 1 — the `noble` flag (decisive, no physics needed)

Every series entry carries **both** `potential_v` and a `noble` boolean
([`ruleset_seeder.py:169`](../../app/services/ruleset_seeder.py):
`noble_label = "noble (cathodic)" if mat.get("noble") else "active (anodic)"`).

`noble` states the answer directly. Whether noble materials hold higher or lower
`potential_v` settles the convention outright.

### Test 2 — zinc against copper (physics anchor)

Zinc sacrifices to copper. That is what galvanising *is*. Whichever sign reading names
zinc as the anode is the correct convention.

### Runnable check

With credentials present:

```bash
uv run python scripts/verify_anode_convention.py
```

The script is committed at
[`scripts/verify_anode_convention.py`](../../scripts/verify_anode_convention.py) and
prints the convention plus the observed values as evidence to paste back into this
report.

## Fix (one line, once verified)

If the live engine is confirmed wrong, at
[`bimguard_corrosion_engine.py:353-361`](../../app/engines/bimguard_corrosion_engine.py):

```python
# WRONG if series is in electrode-potential convention:
if anode_potential < cathode_potential:      # swaps so anode has HIGHER potential

# CORRECT for electrode-potential convention:
if anode_potential > cathode_potential:      # swaps so anode has LOWER (more negative) potential
```

Update the adjacent comment too — `"less noble = higher potential"` is the assertion
under test and must not survive the fix unchanged.

### Regression test to add

```python
def test_zinc_sacrifices_to_copper():
    """Physics anchor: galvanising works because zinc is anodic to copper.

    Pins the sign convention of the shared series. If this fails, every
    galvanic finding names the wrong victim.
    """
    result = assess_galvanic_risk(GCElement(
        material_anode="Zinc", material_cathode="Copper", ...
    ))
    assert result.anode_material == "Zinc"
```

The test must assert on the **resolved** anode after the engine's internal swap, not on
the input ordering, or it will pass regardless of the bug.

## Impact if confirmed

- Every galvanic BCF issue exported to date names the wrong material.
- Mitigation text is inverted — it recommends protecting the cathode.
- Area-ratio risk is computed from a swapped anode/cathode pair
  ([`_compute_area_ratio`](../../app/modules/module4_comparator/galvanic.py)), so the
  small-anode/large-cathode amplification is applied backwards, which changes the
  *score*, not only the label.
- Any reports already issued to a client would need reissuing.

## Not affected

**XM-001** ([`cross_material.py`](../../app/modules/module4_comparator/cross_material.py))
does not depend on the outcome. It resolves the anode from the `noble` flag first, which
is convention-independent, and falls back to a `series_convention` **declared in the rule
pack** rather than assumed in code. Magnitude uses `abs(gap)`, which is unaffected by
sign. Where neither discriminator resolves, XM-001 emits a data-quality issue instead of
guessing.

Once the convention is confirmed, `series_convention` in
[`xm_001_cross_material.json`](../../data/rulesets/xm_001_cross_material.json) must be
set to match and its `MUST_VERIFY` note cleared.

---

*Raised during XM-001 implementation. Fix deferred by agreement until XM-001 lands.*
