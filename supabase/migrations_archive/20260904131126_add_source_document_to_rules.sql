-- Migration: Add source_document_id to public.rules
-- Date: 2026-09-04
-- Purpose: A promoted rule (via rule_extraction_drafts.promote_draft) never
-- kept a link back to the document it was extracted from — the draft row
-- carries source_document_id, but it was dropped on promotion. This closes
-- that gap so the rule-source annotation feature (GET /api/rules/{id}/source)
-- can resolve a canonical rule back to its origin document.
--
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE public.rules
    ADD COLUMN IF NOT EXISTS source_document_id BIGINT REFERENCES public.documents(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_rules_source_document_id
    ON public.rules(source_document_id);

COMMENT ON COLUMN public.rules.source_document_id IS
    'FK to public.documents.id — the document this rule was extracted from, when known (NULL for manually-authored rules)';

COMMIT;

-- Verify:
--   SELECT column_name, data_type
--     FROM information_schema.columns
--    WHERE table_schema='public' AND table_name='rules' AND column_name='source_document_id';
