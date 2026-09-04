-- Migration: index_bsdd_classes_class_type
-- Description: Index public.bsdd_classes.class_type so the bSDD ontology
-- browser (and any future server-side filter) can group/filter classes by
-- classType (Class vs GroupOfProperties -- Pset_/Qto_ definitions) without a
-- full-table scan, now that scripts/crawl_bsdd_ontology.py actually crawls
-- and tags GroupOfProperties classes alongside the IFC entity hierarchy.

CREATE INDEX IF NOT EXISTS idx_bsdd_classes_class_type ON public.bsdd_classes (class_type);
