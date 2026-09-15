-- Migration: add_organization_id_to_parsing_engine_instances
-- Description: Make parsing_engine_instances a two-tier registry, mirroring
-- llm_provider_instances -- organization_id IS NULL is the existing
-- platform-wide tier (today's rows, today's behavior, superadmin-managed);
-- a non-null organization_id is a new org-scoped tier an org's own
-- owner/admin can manage, used in preference to the platform default when
-- present. Per-name uniqueness and single-default enforcement move from
-- global to per-scope (per-org, or platform-wide for NULL).

alter table public.parsing_engine_instances
    add column organization_id bigint references public.organizations(id) on delete cascade;

-- Drop the old global uniqueness/single-default constraints...
alter table public.parsing_engine_instances
    drop constraint parsing_engine_instances_name_key;

drop index public.parsing_engine_instances_single_default;

-- ...replace with scope-aware equivalents: unique per (org, name) or
-- globally unique among platform rows; at most one default per org, and at
-- most one default among platform rows.
create unique index parsing_engine_instances_org_name_key
    on public.parsing_engine_instances (organization_id, name)
    where organization_id is not null;

create unique index parsing_engine_instances_platform_name_key
    on public.parsing_engine_instances (name)
    where organization_id is null;

create unique index parsing_engine_instances_single_default_per_org
    on public.parsing_engine_instances (organization_id)
    where is_default and organization_id is not null;

create unique index parsing_engine_instances_single_default_platform
    on public.parsing_engine_instances (is_default)
    where is_default and organization_id is null;

create index idx_parsing_engine_instances_org
    on public.parsing_engine_instances (organization_id);
