-- Migration: add_docling_kind_to_unstructured_instances
-- Description: Broaden unstructured_instances.kind to also allow 'docling',
-- so a hosted Docling Serve instance can be registered as a parsing engine
-- alongside local/hosted Unstructured instances.

ALTER TABLE public.unstructured_instances
    DROP CONSTRAINT unstructured_instances_kind_check;

ALTER TABLE public.unstructured_instances
    ADD CONSTRAINT unstructured_instances_kind_check
    CHECK (kind IN ('local', 'hosted', 'docling'));
