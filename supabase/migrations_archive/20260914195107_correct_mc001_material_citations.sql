-- Correct the BIMGUARD-MC-001 (MIC) material-susceptibility rows seeded from the
-- ruleset:BIMGUARD-MC-001 static asset.
--
-- The startup seeder (app/services/ruleset_seeder.py, _seed_mc001) writes
-- source_text = 'Source: <reference>' for each material_susceptibility entry.
-- The payload seeded by 20260806180500_seed_static_data_assets.sql gives seven of
-- them a reference to "ASTM G-187" (a soil-resistivity practice with no bearing on
-- MIC) or "NACCE TPC 11" (a misspelt, unverified NACE document). Neither is the
-- source of any MC-001 score: the scores are BIMGUARD authored calibration. See
-- docs/planning/corrosion_provenance_2026-09-13.md §12.2, whose wording is used
-- verbatim below.
--
-- 20260806180500 is applied and is not edited. The insert pass skips existing
-- references, so a code change cannot reach rows already stored; they are
-- corrected here.
--
-- Every UPDATE matches one reference while its source_text still holds the exact
-- seeded value. A rule edited by hand since seeding is left as it is, and running
-- this twice changes nothing the second time. Only source_text changes: no score,
-- threshold, weight or parameters value is touched.

UPDATE public.rules
SET source_text = 'Source: AMPP (formerly NACE) industry practice, MIC mechanism only; score is MC-001 authored calibration',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-MC-001'
  AND reference = 'MC-001.MAT.CARBON_STEEL'
  AND source_text = 'Source: ASTM G-187 / NACCE TPC 11';

UPDATE public.rules
SET source_text = 'Source: AMPP (formerly NACE) industry practice, MIC mechanism only; score is MC-001 authored calibration',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-MC-001'
  AND reference = 'MC-001.MAT.CAST_IRON'
  AND source_text = 'Source: NACCE TPC 11';

UPDATE public.rules
SET source_text = 'Source: AMPP (formerly NACE) industry practice, MIC mechanism only; score is MC-001 authored calibration',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-MC-001'
  AND reference = 'MC-001.MAT.GALV_STEEL'
  AND source_text = 'Source: NACCE TPC 11';

UPDATE public.rules
SET source_text = 'Source: AMPP (formerly NACE) industry practice, MIC mechanism only; score is MC-001 authored calibration',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-MC-001'
  AND reference = 'MC-001.MAT.SS304'
  AND source_text = 'Source: ASTM G-187';

UPDATE public.rules
SET source_text = 'Source: AMPP (formerly NACE) industry practice, MIC mechanism only; score is MC-001 authored calibration',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-MC-001'
  AND reference = 'MC-001.MAT.SS316'
  AND source_text = 'Source: ASTM G-187';

UPDATE public.rules
SET source_text = 'Source: AMPP (formerly NACE) industry practice, MIC mechanism only; score is MC-001 authored calibration',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-MC-001'
  AND reference = 'MC-001.MAT.DUPLEX2205'
  AND source_text = 'Source: NACE / ASTM G-187';

UPDATE public.rules
SET source_text = 'Source: AMPP (formerly NACE) industry practice, MIC mechanism only; score is MC-001 authored calibration',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-MC-001'
  AND reference = 'MC-001.MAT.TITANIUM'
  AND source_text = 'Source: ASTM G-187 — exceptional MIC resistance';

-- Verification (run by hand after apply; not executed by this migration).
--
-- 1. Rows still holding a superseded citation. Expected after apply: no rows.
--
-- SELECT id, reference, source_text
-- FROM public.rules
-- WHERE ruleset_id = 'BIMGUARD-MC-001'
--   AND (reference, source_text) IN (
--     ('MC-001.MAT.CARBON_STEEL', 'Source: ASTM G-187 / NACCE TPC 11'),
--     ('MC-001.MAT.CAST_IRON',    'Source: NACCE TPC 11'),
--     ('MC-001.MAT.GALV_STEEL',   'Source: NACCE TPC 11'),
--     ('MC-001.MAT.SS304',        'Source: ASTM G-187'),
--     ('MC-001.MAT.SS316',        'Source: ASTM G-187'),
--     ('MC-001.MAT.DUPLEX2205',   'Source: NACE / ASTM G-187'),
--     ('MC-001.MAT.TITANIUM',     'Source: ASTM G-187 — exceptional MIC resistance')
--   );
--
-- 2. The seven rows with their corrected text. Expected after apply: 7 rows.
--
-- SELECT id, reference, source_text
-- FROM public.rules
-- WHERE ruleset_id = 'BIMGUARD-MC-001'
--   AND reference IN (
--     'MC-001.MAT.CARBON_STEEL', 'MC-001.MAT.CAST_IRON', 'MC-001.MAT.GALV_STEEL',
--     'MC-001.MAT.SS304', 'MC-001.MAT.SS316', 'MC-001.MAT.DUPLEX2205',
--     'MC-001.MAT.TITANIUM'
--   )
--   AND source_text = 'Source: AMPP (formerly NACE) industry practice, MIC mechanism only; score is MC-001 authored calibration'
-- ORDER BY reference;
