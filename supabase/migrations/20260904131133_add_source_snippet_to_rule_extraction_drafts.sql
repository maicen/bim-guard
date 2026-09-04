-- Migration: Add source_snippet to public.rule_extraction_drafts
-- Date: 2026-09-04
-- Purpose: rule_extraction_drafts.clause (ClauseMetadata JSON) carries only
-- provenance (clause id, page number, section path) — never the originating
-- node's actual text. promote_draft() therefore had nothing to write into
-- rules.source_text but an empty string. This column carries the node's text
-- forward from extraction through review to promotion.
--
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE public.rule_extraction_drafts
    ADD COLUMN IF NOT EXISTS source_snippet TEXT;

COMMENT ON COLUMN public.rule_extraction_drafts.source_snippet IS
    'The originating DocumentNodeContract.text, carried forward so promote_draft() can populate rules.source_text';

COMMIT;

-- Verify:
--   SELECT column_name, data_type
--     FROM information_schema.columns
--    WHERE table_schema='public' AND table_name='rule_extraction_drafts' AND column_name='source_snippet';
