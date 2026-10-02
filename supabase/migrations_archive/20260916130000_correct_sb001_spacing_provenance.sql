-- Re-source the BIMGUARD-SB-001 brace spacing rules (SB-001.03, SB-001.04) and
-- correct the pipe diameter rule's (SB-001.01) provenance label.
--
-- The stored transverse/longitudinal brace spacing was 1.0 m / 1.5 m, described
-- as BIMGUARD screening calibration. That description was wrong, the same way
-- the pre-2026-09-16 brace angle description was wrong: the values were not
-- authored by BIMGUARD. They are the surviving output of the same unverified
-- AI-assisted research summary (docs/validation/data/hermes_standards_research_summary.json),
-- compounded by a feet-written-as-inches unit error. That summary's invented
-- entries gave the same spacing figure twice, once in metres and once
-- (corrupted, feet mistaken for inches) in inches; the metric pair survived a
-- min() merge across the two entries. The real value the corrupted figure
-- belongs to is 40 ft transverse / 80 ft longitudinal (12.19 m / 24.38 m).
--
-- Both spacings are now sourced to a held document: the Hilti Seismic Manual,
-- Earthquake-resistant design of MEP supports, MT System (05/2022), which
-- reports sprinkler pipe restraint spacing of 12 m transverse / 24 m
-- longitudinal, citing NFPA 13 / EN 12845 Annex E. See
-- data/rulesets/sb001_seismic_clearance.json (schema 1.3.0, changelog entry
-- 1.3.0) and D:/claude-workspace/hilti-seismic/sb001_spacing_investigation.md.
--
-- The pipe diameter threshold (SB-001.01, 63.0 mm) was cross-checked against the
-- same fabrication signature (EN 63 mm ~= 2.48 in ~= NFPA's reported ~2.5 in)
-- and found to carry it, but no document held gives a sourced pipe-diameter
-- seismic-bracing exemption threshold to replace it with. Its value is
-- therefore left unchanged; only its source_text is corrected here, from a
-- "BIMGUARD SB-001 authored calibration" label (also wrong -- 63.0 was never a
-- BIMGUARD choice) to one that plainly says the value is unsourced/placeholder.
--
-- Two generations of the spacing rows are corrected: the pre-2026-09-13 rows
-- that still attribute the spacing to "EN 1998-1 / DIN 4149", and the
-- 2026-09-13 rows that carry the "BIMGUARD SB-001 screening calibration" label.
-- Every UPDATE matches a field only while it still holds one of those exact
-- superseded values, so a rule edited by hand since seeding is left as it is,
-- and running this twice changes nothing the second time. No SB-001 code path
-- evaluates a modelled brace spacing or pipe diameter against a real pipe run
-- beyond the SB-001.01/.03/.04 seeded numeric-comparison rules, so no other
-- stored finding is invalidated by this migration.
--
-- 20260913131052_correct_sb001_seeded_rule_provenance.sql and
-- 20260916120000_correct_sb001_angle_provenance.sql are applied and are not
-- edited; the rows they wrote are superseded here.

-- 1. SB-001.03 (transverse spacing): description.
UPDATE public.rules
SET description = 'Maximum transverse seismic brace spacing — 12 m, Hilti Seismic Manual 05/2022 (NFPA 13 / EN 12845 Annex E)',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.03'
  AND description IN (
    'Maximum transverse seismic brace spacing — 1.0 m per EN 1998-1 / DIN 4149',
    'Maximum transverse seismic brace spacing — 1.0 m, BIMGUARD SB-001 screening calibration (authored, not a code value)'
  );

-- 2. SB-001.03: the value, 1.0 -> 12.0.
UPDATE public.rules
SET check_value = '12.0',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.03'
  AND btrim(check_value, '"') IN ('1.0', '1');

-- 3. SB-001.03: the provenance text.
UPDATE public.rules
SET source_text = 'Sourced to the Hilti Seismic Manual – Earthquake-resistant design of MEP supports, MT System (05/2022), citing NFPA 13 / EN 12845 Annex E: transverse restraint spacing 12 m. Sourced. Replaces the former 1.0, which was not BIMGUARD calibration: it was the same unverified Hermes research pass that produced the fabricated brace angle, with an additional feet-written-as-inches unit corruption -- the same figure, stated once in metres and once (corrupted) in inches by that pass''s two invented per-standard entries, survived a min() merge across them. The real value the corrupted figure belongs to is 40 ft (12.19 m), which this source states directly as 12 m. See changelog 1.3.0 and D:/claude-workspace/hilti-seismic/sb001_spacing_investigation.md.',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.03'
  AND (
    btrim(coalesce(source_text, '')) = ''
    OR btrim(source_text) = 'BIMGUARD SB-001 authored calibration. Authored conservative calibration. Upstream reference: FEMA E-74 App. A §3.9.D.6-7 gives maxima of 40 ft (12.19 m) for ductile and 20 ft (6.10 m) for nonductile pipe, from a sample specification intended to be customised. BIMGUARD''s value is approximately 6-12× tighter and is a screening threshold, not a code requirement. Not applicable to ducts: E-74 gives no duct brace spacing.'
  );

-- 4. SB-001.04 (longitudinal spacing): description.
UPDATE public.rules
SET description = 'Maximum longitudinal seismic brace spacing — 24 m, Hilti Seismic Manual 05/2022 (NFPA 13 / EN 12845 Annex E)',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.04'
  AND description IN (
    'Maximum longitudinal seismic brace spacing — 1.5 m per EN 1998-1 / DIN 4149',
    'Maximum longitudinal seismic brace spacing — 1.5 m, BIMGUARD SB-001 screening calibration (authored, not a code value)'
  );

-- 5. SB-001.04: the value, 1.5 -> 24.0.
UPDATE public.rules
SET check_value = '24.0',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.04'
  AND btrim(check_value, '"') IN ('1.5');

-- 6. SB-001.04: the provenance text.
UPDATE public.rules
SET source_text = 'Sourced to the Hilti Seismic Manual – Earthquake-resistant design of MEP supports, MT System (05/2022), citing NFPA 13 / EN 12845 Annex E: longitudinal restraint spacing 24 m. Sourced. Replaces the former 1.5, from the same fabricated Hermes pass as the transverse value, with an extra digit change (the real 80 ft became 60 in before conversion to 1.5 m). The real NFPA 13 value is 80 ft (24.38 m), which this source states directly as 24 m. See changelog 1.3.0 and D:/claude-workspace/hilti-seismic/sb001_spacing_investigation.md.',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.04'
  AND (
    btrim(coalesce(source_text, '')) = ''
    OR btrim(source_text) = 'BIMGUARD SB-001 authored calibration. Authored conservative calibration. Upstream: FEMA E-74 App. A §3.9.D.6 gives 80 ft (24.38 m) ductile / 40 ft (12.19 m) nonductile. Same screening rationale as the transverse value. Not applicable to ducts.'
  );

-- 7. SB-001.01 (pipe diameter): correct only the provenance label. The value
--    (63.0) does not change -- no sourced replacement was found.
UPDATE public.rules
SET source_text = 'Unsourced placeholder. Not a BIMGUARD authored calibration and not a stated standard value: this is an unverified figure carried over from the same fabricated Hermes research pass that produced the brace angle and brace spacing values (see changelog 1.2.0 and 1.3.0), flagged by the same unit-mirroring signature (EN 63 mm ≈ 2.48 in, close to NFPA''s reported ≈2.5 in). Falls within the ASCE 7-10 exemption band FEMA E-74 §6.4.3.1 reports (roughly 1 to 3 in / 25.4-76.2 mm depending on seismic design category and occupancy), but that band does not fix a single threshold, so it does not confirm the value. No document in D:/claude-workspace/hilti-seismic/sources (NFPA 13, UFGS 23 05 48.19, Hilti Seismic Manual) states a pipe-diameter seismic-bracing exemption threshold, so no sourced replacement is available; the value is left at 63.0 pending one and is marked unsourced/placeholder rather than authored.',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.01'
  AND (
    btrim(coalesce(source_text, '')) = ''
    OR btrim(source_text) = 'BIMGUARD SB-001 authored calibration. Within the ASCE 7-10 exemption band as reported by FEMA E-74 §6.4.3.1: roughly 1 to 3 in (25.4-76.2 mm) depending on seismic design category and occupancy. 63 mm ≈ 2.48 in falls inside that band. Not a stated standard value.'
  );
