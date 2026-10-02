-- Migration: Add DocLang XML and Bounding Box (bbox) support
-- Date: 2026-09-09
-- Purpose: Persist canonical DocLang XML (with OTSL tables) in public.documents,
-- and store element bounding boxes (bbox) in public.document_nodes and
-- public.rule_extraction_drafts for visual source grounding in the PDF viewer.
--
-- Idempotent: safe to re-run.

BEGIN;

-- 1. Add doclang_xml column to public.documents
ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS doclang_xml TEXT NOT NULL DEFAULT '';

COMMENT ON COLUMN public.documents.doclang_xml IS
    'Canonical DocLang XML export (including OTSL table definitions) produced by Docling extraction';

-- 2. Add bbox column to public.document_nodes
ALTER TABLE public.document_nodes
    ADD COLUMN IF NOT EXISTS bbox JSONB DEFAULT NULL;

COMMENT ON COLUMN public.document_nodes.bbox IS
    'Bounding box coordinates on the source page: {l, t, r, b, coord_origin}';

-- 3. Add bbox column to public.rule_extraction_drafts
ALTER TABLE public.rule_extraction_drafts
    ADD COLUMN IF NOT EXISTS bbox JSONB DEFAULT NULL;

COMMENT ON COLUMN public.rule_extraction_drafts.bbox IS
    'Source clause bounding box coordinates on the page for visual highlighting in PDF viewer: {l, t, r, b, coord_origin}';

COMMIT;
