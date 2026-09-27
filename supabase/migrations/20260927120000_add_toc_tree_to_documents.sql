-- Migration: Add toc_tree column to documents table
-- Date: 2026-09-27
-- Purpose: Persist Smart Table of Contents (TOC) tree and metadata in documents table
-- so it does not recalculate on every request unless explicit regeneration is triggered.

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS toc_tree JSONB;

COMMENT ON COLUMN public.documents.toc_tree IS 'Cached Smart Table of Contents (TOC) tree, sections, and metadata';
