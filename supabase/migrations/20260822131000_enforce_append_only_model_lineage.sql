revoke all privileges on table public.model_enhancement_lineage from service_role;
grant select, insert on table public.model_enhancement_lineage to service_role;

revoke all privileges on sequence public.model_enhancement_lineage_id_seq from service_role;
grant usage on sequence public.model_enhancement_lineage_id_seq to service_role;