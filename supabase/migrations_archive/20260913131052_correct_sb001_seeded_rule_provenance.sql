-- Correct the BIMGUARD-SB-001 (Blue Halo seismic) rows seeded before 2026-09-13.
--
-- The startup seeder (app/services/ruleset_seeder.py, seed_seismic_rules) wrote
-- descriptions attributing SB-001's brace spacing to "EN 1998-1 / DIN 4149" and an
-- installation angle range of 35-70 degrees. Both came from an unverified
-- AI-assisted research summary (docs/validation/data/hermes_standards_research_summary.json).
-- EN 1998-1 and its German National Annex give no MEP brace spacing, and 35-70 was
-- that summary's EN-only figure, not the 40-65 degrees the SB-001 configuration
-- applies. The thresholds are BIMGUARD screening calibration; see
-- data/rulesets/sb001_seismic_clearance.json (schema 1.1.0) and
-- docs/planning/sb001_provenance_2026-09-13.md.
--
-- 20260830001000_ruleset_categories.sql wrote the folder description
-- "... requirements per EN 1998-1 / DIN 4149". That migration is applied and is
-- not edited; its text is corrected here.
--
-- Every UPDATE matches a field only while it still holds the exact superseded
-- value (or, for source_text, is still empty). A rule edited by hand since seeding
-- is left as it is, and running this twice changes nothing the second time.
-- No threshold value other than the angle range changes.

-- 1. Descriptions that attributed authored spacing to EN 1998-1 / DIN 4149.
UPDATE public.rules
SET description = 'Maximum transverse seismic brace spacing — 1.0 m, BIMGUARD SB-001 screening calibration (authored, not a code value)',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.03'
  AND description = 'Maximum transverse seismic brace spacing — 1.0 m per EN 1998-1 / DIN 4149';

UPDATE public.rules
SET description = 'Maximum longitudinal seismic brace spacing — 1.5 m, BIMGUARD SB-001 screening calibration (authored, not a code value)',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.04'
  AND description = 'Maximum longitudinal seismic brace spacing — 1.5 m per EN 1998-1 / DIN 4149';

-- 2. The brace angle range: 35-70 degrees -> 40-65 degrees, matching the configuration.
UPDATE public.rules
SET description = 'Seismic brace installation angle — permissible range 40° to 65° from horizontal, BIMGUARD SB-001 screening calibration (authored, not a code value)',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.05'
  AND description = 'Seismic brace installation angle — permissible range 35° to 70° from horizontal';

UPDATE public.rules
SET value_min = '40.0',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.05'
  AND btrim(value_min, '"') IN ('35', '35.0');

UPDATE public.rules
SET value_max = '65.0',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.05'
  AND btrim(value_max, '"') IN ('70', '70.0');

-- 3. Record each threshold's provenance where the row carries none.
UPDATE public.rules
SET source_text = 'BIMGUARD SB-001 authored calibration. Within the ASCE 7-10 exemption band as reported by FEMA E-74 §6.4.3.1: roughly 1 to 3 in (25.4-76.2 mm) depending on seismic design category and occupancy. 63 mm ≈ 2.48 in falls inside that band. Not a stated standard value.',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.01'
  AND btrim(coalesce(source_text, '')) = '';

UPDATE public.rules
SET source_text = 'BIMGUARD SB-001 authored calibration. Authored. No source. Also the value of brace_types[*].clearance_mm, which the loader applies in preference. FEMA E-74 App. A §3.9.D.9 gives a related rule, horizontal clearance of at least 2/3 the hanger length, but only for unbraced (exempt) piping. No braced-service clearance dimension exists in any source held.',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.02'
  AND btrim(coalesce(source_text, '')) = '';

UPDATE public.rules
SET source_text = 'BIMGUARD SB-001 authored calibration. Authored conservative calibration. Upstream reference: FEMA E-74 App. A §3.9.D.6-7 gives maxima of 40 ft (12.19 m) for ductile and 20 ft (6.10 m) for nonductile pipe, from a sample specification intended to be customised. BIMGUARD''s value is approximately 6-12× tighter and is a screening threshold, not a code requirement. Not applicable to ducts: E-74 gives no duct brace spacing.',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.03'
  AND btrim(coalesce(source_text, '')) = '';

UPDATE public.rules
SET source_text = 'BIMGUARD SB-001 authored calibration. Authored conservative calibration. Upstream: FEMA E-74 App. A §3.9.D.6 gives 80 ft (24.38 m) ductile / 40 ft (12.19 m) nonductile. Same screening rationale as the transverse value. Not applicable to ducts.',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.04'
  AND btrim(coalesce(source_text, '')) = '';

UPDATE public.rules
SET source_text = 'BIMGUARD SB-001 authored calibration. Authored. No source. FEMA E-74 contains no brace angle for pipe or duct. Datum: degrees from horizontal.',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND reference = 'SB-001.05'
  AND btrim(coalesce(source_text, '')) = '';

-- 4. The ruleset folder description written by 20260830001000_ruleset_categories.sql.
UPDATE public.rule_folders
SET description = 'Blue Halo seismic bracing clearance and buffer volume screening rules — BIMGUARD SB-001 authored calibration, not code values (FEMA E-74 where sourced)',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-SB-001'
  AND description = 'Blue Halo seismic bracing clearance and buffer volume requirements per EN 1998-1 / DIN 4149';
