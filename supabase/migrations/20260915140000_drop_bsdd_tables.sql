-- Migration: drop_bsdd_tables
-- Description: Drop bsdd_classes, bsdd_properties, and bsdd_class_properties tables.
-- bSDD reference ontologies are now stored locally as high-performance bundled JSON in data/reference/bsdd/
-- and cached locally in data/cache/bsdd/, eliminating remote database reliance and startup query overhead.

DROP TABLE IF EXISTS public.bsdd_class_properties CASCADE;
DROP TABLE IF EXISTS public.bsdd_properties CASCADE;
DROP TABLE IF EXISTS public.bsdd_classes CASCADE;
