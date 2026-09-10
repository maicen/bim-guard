-- Migration: Add per-element bbox storage to public.documents
-- Date: 2026-09-10
-- Purpose: Persist a per-rendered-block (heading/paragraph/table/picture)
-- bounding-box list alongside each document's DocLang XML, keyed by the
-- stable element ids injected into that XML at extraction time (see
-- app/modules/document_parsing/doclang_element_ids.py). Previously this data
-- was computed transiently during extraction and discarded -- nothing
-- persisted it, so `GET /documents/{id}/element-bboxes` had no source to
-- read from.
--
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS element_bboxes JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.documents.element_bboxes IS
    'Per-element bbox records aligned to <custom><bg_element_id value="..."/></custom> '
    'ids injected into doclang_xml at extraction time: '
    '[{element_id, kind, page_number, bbox, order}, ...]. Empty for documents '
    'whose DocLang XML predates this feature or came from a raw .dclg/.dclx import.';

COMMIT;
