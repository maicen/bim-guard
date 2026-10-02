-- Migration: Add doc_type to public.documents and expand public.client_documents categories
-- Date: 2026-08-31
-- Purpose: Support document types (Code, Specification, Manual, Standard, Drawing, Schedule, Assessment, Report, Other)
--          across both global document library and project client documents.

BEGIN;

-- 1. Add doc_type to public.documents
ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS doc_type TEXT NOT NULL DEFAULT 'Specification';

CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON public.documents(doc_type);

COMMENT ON COLUMN public.documents.doc_type IS
    'Document classification type: Code, Specification, Manual, Standard, Drawing, Schedule, Assessment, Report, Other';

-- 2. Update client_documents category constraint to include expanded types
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'client_documents_category_check'
          AND conrelid = 'public.client_documents'::regclass
    ) THEN
        ALTER TABLE public.client_documents
            DROP CONSTRAINT client_documents_category_check;
    END IF;
END $$;

ALTER TABLE public.client_documents
    ADD CONSTRAINT client_documents_category_check
    CHECK (category IN (
        'Specification',
        'Code',
        'Manual',
        'Standard',
        'Drawing',
        'Schedule',
        'O&M Manual',
        'Warranty',
        'Assessment',
        'Report',
        'RFI Log',
        'Other'
    ));

COMMIT;
