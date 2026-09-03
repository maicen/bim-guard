-- Migration: rename_to_parsing_engine_instances
-- Description: Rename unstructured_instances -> parsing_engine_instances now
-- that the registry covers Docling instances too, and drop the kind CHECK
-- constraint — the set of valid kinds is now owned by ParsingEngineRegistry
-- (app/modules/document_parsing/engines) in application code, which the
-- service validates against at request time. This lets a new engine kind
-- be added without a schema migration.

ALTER TABLE public.unstructured_instances RENAME TO parsing_engine_instances;

ALTER TABLE public.parsing_engine_instances
    RENAME CONSTRAINT unstructured_instances_pkey TO parsing_engine_instances_pkey;

ALTER TABLE public.parsing_engine_instances
    RENAME CONSTRAINT unstructured_instances_name_key TO parsing_engine_instances_name_key;

ALTER TABLE public.parsing_engine_instances
    DROP CONSTRAINT unstructured_instances_kind_check;

ALTER INDEX public.unstructured_instances_single_default
    RENAME TO parsing_engine_instances_single_default;

ALTER INDEX public.idx_unstructured_instances_enabled
    RENAME TO idx_parsing_engine_instances_enabled;
