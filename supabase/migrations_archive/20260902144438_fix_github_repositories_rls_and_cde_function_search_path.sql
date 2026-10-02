-- Migration: Harden github_repositories RLS and pin the CDE trigger search_path
-- Date: 2026-09-02
-- Purpose: Resolve two Supabase security advisors raised after the ISO 19650 /
--          CDE schema landed:
--            1. public.github_repositories was created without RLS enabled.
--            2. public.prevent_published_cde_mutation() had a mutable
--               search_path (SECURITY-relevant for a trigger function).
--
-- Applied to the remote project on 2026-09-02; recorded here so the local
-- migrations directory matches remote migration history.

ALTER TABLE public.github_repositories ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.prevent_published_cde_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    IF OLD.cde_state IN ('PUBLISHED', 'ARCHIVED') THEN
        IF NEW.cde_state = OLD.cde_state AND (
            NEW.name IS DISTINCT FROM OLD.name OR
            NEW.ifc_file_path IS DISTINCT FROM OLD.ifc_file_path OR
            NEW.revision_code IS DISTINCT FROM OLD.revision_code
        ) THEN
            RAISE EXCEPTION 'Cannot modify % project record in state %', OLD.id, OLD.cde_state;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
