-- Migration: add_docling_local_kind
-- Description: Broaden unstructured_instances.kind to also allow
-- 'docling-local', so a self-hosted docling-serve Docker container can be
-- registered alongside the hosted 'docling' kind (mirrors local/hosted for
-- Unstructured).

ALTER TABLE public.unstructured_instances
    DROP CONSTRAINT unstructured_instances_kind_check;

ALTER TABLE public.unstructured_instances
    ADD CONSTRAINT unstructured_instances_kind_check
    CHECK (kind IN ('local', 'hosted', 'docling', 'docling-local'));
