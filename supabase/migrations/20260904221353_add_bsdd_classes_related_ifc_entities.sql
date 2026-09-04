-- Migration: add_bsdd_classes_related_ifc_entities
-- Description: Add a related_ifc_entities column to public.bsdd_classes so
-- the local ontology can persist which IFC entities a class applies to --
-- populated from bSDD's own relatedIfcEntities field for regular Class
-- entries, and (best-effort, see BSDDClient._bracket_ifc_refs) from
-- `[[IfcXxx]]` applicability references in the definition/description text
-- for GroupOfProperties classes (Pset_/Qto_ definitions), which carry no
-- structured applicability field of their own.

ALTER TABLE public.bsdd_classes
    ADD COLUMN IF NOT EXISTS related_ifc_entities JSONB NOT NULL DEFAULT '[]'::jsonb;
