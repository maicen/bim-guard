-- Migration: Add doclang_archive_path to public.documents
-- Description: Tracks persistent Supabase Storage reference (sb://bucket/doclang/...) for pre-packaged .dclx archives

ALTER TABLE IF EXISTS public.documents
    ADD COLUMN IF NOT EXISTS doclang_archive_path TEXT DEFAULT NULL;

COMMENT ON COLUMN public.documents.doclang_archive_path IS
    'Storage URI (sb://bucket/doclang/...) for pre-generated DocLang .dclx zip archives';
