-- Correct the BIMGUARD-GC-001 (galvanic) citation metadata: the stored
-- ruleset:BIMGUARD-GC-001 static asset and the rules rows seeded from it.
--
-- Four defects, all in citation text. No potential, threshold, weight, band
-- cut-off, multiplier or score is touched by this migration.
--
-- 1. The standard's title is wrong. The payload calls NASA-STD-6012 "Corrosion
--    Control and Treatment for Aerospace Vehicles". NASA-STD-6012 is "Corrosion
--    Protection for Space Flight Hardware" (standards.nasa.gov), which qualifies
--    surface treatments and finishes for space flight hardware. It does not
--    dimension a building-services E1-E7 environment taxonomy.
--
-- 2. "NASA-STD-6012 Table 1" names a table nobody read. The environment voltage
--    thresholds are authored calibration, so the locator is fabricated in the
--    same way as the SB-001 clause references corrected on 2026-09-13.
--    docs/planning/corrosion_provenance_2026-09-13.md §8 prescribes the fix used
--    here: governing_reference plus provenance, and no table named until one has
--    been read.
--
-- 3. "Euro Inox (2025)" names an edition that does not exist. 2025 is the
--    worldstainless.org upload path the PDF is served from. The document is
--    Materials and Applications Series Volume 10, ISBN 978-2-87997-263-3,
--    (c) Euro Inox 2009, adapted from Merkblatt 829 (4th edition 2005). It is
--    now held, at
--    docs/scraped_standards/corrosion_euro_inox_vol10_contact_other_metals.md.
--
-- 4. The galvanic series declares a reference electrode it contradicts. The
--    payload states reference_electrode "Ag/AgCl" and reference_electrolyte
--    "Seawater at ambient temperature", then lists every metal at a positive
--    potential, zinc at +0.80 V and magnesium at +0.95 V. Against Ag/AgCl in
--    seawater both are strongly negative. The payload's own note ("Lower
--    potential = more noble") documents an inverted, all-positive scale, which
--    no electrode measurement produces. The values are an authored ranking
--    index, and the electrode keys are replaced by keys that say so. THE VALUES
--    THEMSELVES ARE NOT CHANGED: whether to replace the index with measured
--    potentials is an engineering decision, and it would move every score.
--
-- 20260806180500 is applied and is not edited. The seeder inserts only and skips
-- references already stored, so a code change alone cannot reach stored rows;
-- they are corrected here. app/services/ruleset_seeder.py carries the same two
-- strings for fresh seeds (_GC001_ENV_SOURCE_TEXT, _GC001_SERIES_SOURCE_TEXT),
-- and tests/test_gc001_citation_provenance.py holds the two together.
--
-- Every statement matches only while the superseded text is still exactly as
-- seeded, so a row edited by hand is left alone and a second run changes
-- nothing.

-- ── 1. Seeded rules rows ─────────────────────────────────────────────────────

UPDATE public.rules
SET source_text = 'Source: NASA-STD-6012, governing standard for the mechanism only (no table of it has been read); threshold is GC-001 authored calibration',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-GC-001'
  AND rule_type = 'environment_class'
  AND source_text = 'Source: NASA-STD-6012 Table 1';

UPDATE public.rules
SET source_text = 'Source: WorldStainless / Euro Inox Vol. 10 (2009) and AUCSC Basic Corrosion Course (2024), ordering only; potential is GC-001 authored calibration',
    updated_at = NOW()::text
WHERE ruleset_id = 'BIMGUARD-GC-001'
  AND rule_type = 'galvanic_series_entry'
  AND source_text = 'Source: WorldStainless / Euro Inox (2025) and AUCSC Basic Corrosion Course (2024)';

-- ── 2. Stored static asset payload ───────────────────────────────────────────
--
-- content_json is the compact payload the loader decodes; content_text is the
-- pretty-printed copy of the same object. Both carry the same strings, so both
-- are rewritten, key by key so the replacement holds whatever the line breaks
-- are. content_sha256 is then recomputed the way StaticDataService writes it:
-- sha256 of content_json, a newline, then content_text.

UPDATE public.static_data_assets
SET content_json = replace(
      replace(
        replace(
          replace(
            replace(
              replace(
                content_json,
                '"NASA-STD-6012 — Corrosion Control and Treatment for Aerospace Vehicles (voltage thresholds by environment class)"',
                '"NASA-STD-6012 — Corrosion Protection for Space Flight Hardware (named as the standard governing the mechanism; the environment thresholds are authored)"'
              ),
              '"WorldStainless / Euro Inox (2025) — Galvanic series and corrosion rate data"',
              '"WorldStainless / Euro Inox Vol. 10 (2009) — Galvanic series and corrosion rate data"'
            ),
            '"source": "NASA-STD-6012 Table 1"',
            '"governing_reference": "NASA-STD-6012", "provenance": "authored"'
          ),
          '"source": "WorldStainless / Euro Inox (2025) and AUCSC Basic Corrosion Course (2024)"',
          '"governing_reference": "WorldStainless / Euro Inox Vol. 10 (2009) and AUCSC Basic Corrosion Course (2024)", "provenance": "authored"'
        ),
        '"reference_electrode": "Ag/AgCl"',
        '"scale": "Authored ranking index in volt-like units; a higher value is more active. Not a measurement against any reference electrode."'
      ),
      '"reference_electrolyte": "Seawater at ambient temperature"',
      '"scale_provenance": "authored"'
    ),
    content_text = replace(
      replace(
        replace(
          replace(
            replace(
              replace(
                content_text,
                '"NASA-STD-6012 — Corrosion Control and Treatment for Aerospace Vehicles (voltage thresholds by environment class)"',
                '"NASA-STD-6012 — Corrosion Protection for Space Flight Hardware (named as the standard governing the mechanism; the environment thresholds are authored)"'
              ),
              '"WorldStainless / Euro Inox (2025) — Galvanic series and corrosion rate data"',
              '"WorldStainless / Euro Inox Vol. 10 (2009) — Galvanic series and corrosion rate data"'
            ),
            '"source": "NASA-STD-6012 Table 1"',
            '"governing_reference": "NASA-STD-6012", "provenance": "authored"'
          ),
          '"source": "WorldStainless / Euro Inox (2025) and AUCSC Basic Corrosion Course (2024)"',
          '"governing_reference": "WorldStainless / Euro Inox Vol. 10 (2009) and AUCSC Basic Corrosion Course (2024)", "provenance": "authored"'
        ),
        '"reference_electrode": "Ag/AgCl"',
        '"scale": "Authored ranking index in volt-like units; a higher value is more active. Not a measurement against any reference electrode."'
      ),
      '"reference_electrolyte": "Seawater at ambient temperature"',
      '"scale_provenance": "authored"'
    )
WHERE asset_key = 'ruleset:BIMGUARD-GC-001'
  AND (
    content_json LIKE '%Corrosion Control and Treatment for Aerospace Vehicles%'
    OR content_json LIKE '%NASA-STD-6012 Table 1%'
    OR content_json LIKE '%Euro Inox (2025)%'
    OR content_json LIKE '%reference_electrode%'
  );

UPDATE public.static_data_assets
SET content_sha256 = encode(sha256(convert_to(content_json || E'\n' || content_text, 'UTF8')), 'hex')
WHERE asset_key = 'ruleset:BIMGUARD-GC-001'
  AND content_sha256 <> encode(sha256(convert_to(content_json || E'\n' || content_text, 'UTF8')), 'hex');

-- Verification (run by hand after apply; not executed by this migration).
--
-- 1. Rows still holding a superseded citation. Expected after apply: no rows.
--
-- SELECT id, reference, source_text
-- FROM public.rules
-- WHERE ruleset_id = 'BIMGUARD-GC-001'
--   AND source_text IN (
--     'Source: NASA-STD-6012 Table 1',
--     'Source: WorldStainless / Euro Inox (2025) and AUCSC Basic Corrosion Course (2024)'
--   );
--
-- 2. The corrected rows. Expected after apply: 7 environment classes and 20
--    galvanic series entries, as seeded by 20260806180500.
--
-- SELECT rule_type, count(*)
-- FROM public.rules
-- WHERE ruleset_id = 'BIMGUARD-GC-001'
--   AND rule_type IN ('environment_class', 'galvanic_series_entry')
--   AND source_text LIKE '%authored calibration'
-- GROUP BY rule_type;
--
-- 3. The payload holds no superseded string. Expected after apply: no rows.
--
-- SELECT asset_key
-- FROM public.static_data_assets
-- WHERE asset_key = 'ruleset:BIMGUARD-GC-001'
--   AND (content_json LIKE '%Aerospace Vehicles%'
--     OR content_json LIKE '%NASA-STD-6012 Table 1%'
--     OR content_json LIKE '%Euro Inox (2025)%'
--     OR content_json LIKE '%reference_electrode%');
--
-- 4. The payload still decodes as JSON, and the checksum matches.
--
-- SELECT content_json::jsonb ? 'galvanic_series' AS decodes,
--        content_sha256 = encode(sha256(convert_to(content_json || E'\n' || content_text, 'UTF8')), 'hex') AS sha_ok
-- FROM public.static_data_assets
-- WHERE asset_key = 'ruleset:BIMGUARD-GC-001';
