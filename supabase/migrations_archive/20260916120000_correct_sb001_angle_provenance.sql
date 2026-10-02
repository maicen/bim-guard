-- Re-source the BIMGUARD-SB-001 brace angle rule (SB-001.05).
--
-- The stored angle range was 40-65 degrees from horizontal, described as BIMGUARD
-- screening calibration. That description was wrong: the range was not authored by
-- BIMGUARD. It was the surviving output of an unverified AI-assisted research
-- summary (docs/validation/data/hermes_standards_research_summary.json), whose
-- invented "DIN 4149:2022-03" entry read "40-65 degrees from horizontal" and whose
-- invented "EN 1998-1:2020" entry read "35-70 degrees"; the generator intersected
-- the two and computed the midpoint and half-range from the result.
--
-- The angle is now sourced to a held document: the Hilti Seismic Manual,
-- Earthquake-resistant design of MEP supports, MT System (05/2022), Annex A
-- "Tilt angle - for all bracings", which states a nominal brace tilt angle of
-- 45 degrees +/- 15 degrees on the horizontal level. That gives 30-60 degrees from
-- horizontal. The datum is unchanged; the manual uses the same convention the
-- configuration does. See data/rulesets/sb001_seismic_clearance.json (schema
-- 1.2.0, changelog entry 1.2.0).
--
-- Two generations of stored rows are corrected: the pre-2026-09-13 rows that still
-- carry 35-70 degrees, and the 2026-09-13 rows that carry 40-65 degrees. Every
-- UPDATE matches a field only while it still holds one of those exact superseded
-- values, so a rule edited by hand since seeding is left as it is, and running this
-- twice changes nothing the second time. No threshold other than the brace angle
-- changes, and no SB-001 code path evaluates a modelled brace angle at this commit,
-- so no stored finding is invalidated by this migration.
--
-- 20260913131052_correct_sb001_seeded_rule_provenance.sql is applied and is not
-- edited; the rows it wrote are superseded here.

-- 1. The rule description.
UPDATE public.rules
SET description = 'Seismic brace installation angle — permissible range 30° to 60° from horizontal (45° ± 15°), Hilti Seismic Manual 05/2022',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.05'
  AND description IN (
    'Seismic brace installation angle — permissible range 35° to 70° from horizontal',
    'Seismic brace installation angle — permissible range 40° to 65° from horizontal, BIMGUARD SB-001 screening calibration (authored, not a code value)'
  );

-- 2. The bounds: 35-70 (pre-2026-09-13) and 40-65 (2026-09-13) -> 30-60.
UPDATE public.rules
SET value_min = '30.0',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.05'
  AND btrim(value_min, '"') IN ('35', '35.0', '40', '40.0');

UPDATE public.rules
SET value_max = '60.0',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.05'
  AND btrim(value_max, '"') IN ('70', '70.0', '65', '65.0');

-- 3. The provenance text, which still claims the value is authored calibration.
UPDATE public.rules
SET source_text = 'Sourced to the Hilti Seismic Manual – Earthquake-resistant design of MEP supports, MT System (05/2022), Annex A "Tilt angle – for all bracings": nominal brace tilt angle 45° ± 15° on the horizontal level, i.e. 30-60° from horizontal. Lower bound of the source''s stated 45° ± 15° band (45 - 15). Datum: degrees from horizontal, the same convention the source uses. Replaces the former 40.0, which came from an unverified AI research summary; see changelog 1.2.0. FEMA E-74 contains no brace angle for pipe or duct. A vendor design manual, not a code.',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.05'
  AND (
    btrim(coalesce(source_text, '')) = ''
    OR btrim(source_text) = 'BIMGUARD SB-001 authored calibration. Authored. No source. FEMA E-74 contains no brace angle for pipe or duct. Datum: degrees from horizontal.'
  );
