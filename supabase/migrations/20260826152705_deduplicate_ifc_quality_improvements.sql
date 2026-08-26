alter table public.model_enhancement_lineage
add column source_sha256 text;

alter table public.model_enhancement_lineage
add constraint model_enhancement_lineage_source_sha256_format_check
check (source_sha256 is null or source_sha256 ~ '^[0-9a-f]{64}$');

create unique index model_enhancement_lineage_project_source_sha256_key
on public.model_enhancement_lineage (project_id, source_sha256)
where source_sha256 is not null;