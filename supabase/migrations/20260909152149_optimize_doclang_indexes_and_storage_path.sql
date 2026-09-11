-- Migration: Add DocLang storage path and optimize document node indexes
-- Date: 2026-09-09
-- Purpose: 
-- 1. Add doclang_storage_path to public.documents for offloading bulky DocLang XML/dclx archives to Object Storage.
-- 2. Add composite index on document_nodes(document_id, node_type) for rapid table/heading chunk lookups.
-- 3. Add GIN index on document_nodes.section_path for sub-millisecond JSONB hierarchy matching.
--
-- Idempotent: safe to re-run.

BEGIN;

-- 1. Add doclang_storage_path to public.documents
ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS doclang_storage_path TEXT DEFAULT NULL;

COMMENT ON COLUMN public.documents.doclang_storage_path IS
    'Storage URI (sb://bucket/doclang/...) for offloaded DocLang XML or .dclx archives';

-- 2. Add composite index on document_nodes(document_id, node_type)
CREATE INDEX IF NOT EXISTS idx_document_nodes_doc_type
    ON public.document_nodes(document_id, node_type);

-- 3. Add GIN index on document_nodes.section_path
CREATE INDEX IF NOT EXISTS idx_document_nodes_section_path
    ON public.document_nodes USING gin (section_path jsonb_path_ops);

COMMIT;
