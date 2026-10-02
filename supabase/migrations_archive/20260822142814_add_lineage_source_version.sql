alter table public.model_enhancement_lineage
add column source_version bigint not null default 0
check (source_version >= 0);