-- Migration: Add value_min_scale / value_max_scale to public.rules
-- Date: 2026-09-25
-- Purpose: value_min_property/value_max_property already let a rule's bound
-- be another property on the same element plus a fixed offset (e.g. tread
-- depth between its own Run and Run + 25mm), but many code clauses express a
-- MULTIPLICATIVE relationship instead ("exit doors separated by not less
-- than one-half of the building's maximum diagonal"). There was no way to
-- express the "0.5 x" part, so extraction always fell back to needs_review
-- for this whole clause family. These columns close that gap: the resolved
-- bound becomes (referenced property x scale) + offset, and a scale of 1
-- (the default) reproduces today's offset-only behaviour exactly.
--
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE public.rules
    ADD COLUMN IF NOT EXISTS value_min_scale text NOT NULL DEFAULT '1',
    ADD COLUMN IF NOT EXISTS value_max_scale text NOT NULL DEFAULT '1';

COMMENT ON COLUMN public.rules.value_min_scale IS
    'Multiplier applied to value_min_property before value_min_offset is added: resolved_value_min = (property x scale) + offset. Default 1 (no-op).';
COMMENT ON COLUMN public.rules.value_max_scale IS
    'Multiplier applied to value_max_property before value_max_offset is added: resolved_value_max = (property x scale) + offset. Default 1 (no-op).';

COMMIT;

-- Verify:
--   SELECT column_name, data_type, column_default
--     FROM information_schema.columns
--    WHERE table_schema='public' AND table_name='rules'
--      AND column_name IN ('value_min_scale', 'value_max_scale');
