-- Migration: Add ISO 19650 Suitability/Revision Code CHECK Constraints
-- Purpose: suitability_code and revision_code are validated only at parse
--          time in application code (app/modules/document_parsing/iso_validator.py);
--          the columns themselves are free-text with no database-level
--          guard, so a direct write (application bug, manual SQL, another
--          service) can store a value the ISO 19650-2 naming standard does
--          not recognize. Adds the same code sets/pattern the application
--          validator already enforces as CHECK constraints on projects,
--          documents, and project_ifc_files.
--
-- Suitability codes: S0-S7 (WIP/unclassified), A1-A4 / B1-B4 (Published
-- contractual), CR -- matches VALID_SUITABILITY_CODES in iso_validator.py.
-- Revision codes: Pnn(.nn)? / Cnn / Dnn -- matches REVISION_CODE_REGEX.
--
-- Existing rows are validated by the constraint on creation (NOT VALID +
-- VALIDATE, run in two steps) so a currently-invalid row already present
-- does not block this migration from applying; it surfaces as a validation
-- failure to fix separately rather than an irrecoverable deploy error.

BEGIN;

ALTER TABLE public.projects
    ADD CONSTRAINT projects_suitability_code_check
        CHECK (suitability_code IN ('S0','S1','S2','S3','S4','S5','S6','S7','A1','A2','A3','A4','B1','B2','B3','B4','CR'))
        NOT VALID,
    ADD CONSTRAINT projects_revision_code_check
        CHECK (revision_code ~* '^(P[0-9]{2}(\.[0-9]{2})?|C[0-9]{2}|D[0-9]{2})$')
        NOT VALID;

ALTER TABLE public.documents
    ADD CONSTRAINT documents_suitability_code_check
        CHECK (suitability_code IN ('S0','S1','S2','S3','S4','S5','S6','S7','A1','A2','A3','A4','B1','B2','B3','B4','CR'))
        NOT VALID,
    ADD CONSTRAINT documents_revision_code_check
        CHECK (revision_code ~* '^(P[0-9]{2}(\.[0-9]{2})?|C[0-9]{2}|D[0-9]{2})$')
        NOT VALID;

ALTER TABLE public.project_ifc_files
    ADD CONSTRAINT project_ifc_files_suitability_code_check
        CHECK (suitability_code IN ('S0','S1','S2','S3','S4','S5','S6','S7','A1','A2','A3','A4','B1','B2','B3','B4','CR'))
        NOT VALID,
    ADD CONSTRAINT project_ifc_files_revision_code_check
        CHECK (revision_code ~* '^(P[0-9]{2}(\.[0-9]{2})?|C[0-9]{2}|D[0-9]{2})$')
        NOT VALID;

-- Validate against existing data now, inside the same transaction. If any
-- existing row fails, the whole migration rolls back with a clear error
-- naming the offending constraint rather than silently leaving NOT VALID
-- constraints that only bite on the next write.
ALTER TABLE public.projects VALIDATE CONSTRAINT projects_suitability_code_check;
ALTER TABLE public.projects VALIDATE CONSTRAINT projects_revision_code_check;
ALTER TABLE public.documents VALIDATE CONSTRAINT documents_suitability_code_check;
ALTER TABLE public.documents VALIDATE CONSTRAINT documents_revision_code_check;
ALTER TABLE public.project_ifc_files VALIDATE CONSTRAINT project_ifc_files_suitability_code_check;
ALTER TABLE public.project_ifc_files VALIDATE CONSTRAINT project_ifc_files_revision_code_check;

COMMIT;
