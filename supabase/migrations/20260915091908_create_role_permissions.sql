-- Migration: create_role_permissions
-- Description: Superadmin-configurable matrix of which org role (owner,
-- admin, member) a role-gated action requires. organization_id NULL is the
-- platform-default row for an action; a non-null organization_id is a
-- per-org override that wins when present, falling back to the platform
-- default otherwise -- the same two-tier idiom as parsing_engine_instances.
-- `action` has no CHECK/FK constraint: the set of valid actions is owned by
-- app.modules.permissions.Action in application code (mirrors how `kind` is
-- owned by ParsingEngineRegistry for parsing_engine_instances), which
-- PermissionService validates against at request time.

create table if not exists public.role_permissions (
    id bigint generated always as identity primary key,
    organization_id bigint references public.organizations(id) on delete cascade,
    action text not null,
    min_role text not null check (min_role in ('owner', 'admin', 'member')),
    updated_at timestamptz not null default now(),
    constraint role_permissions_scope_action_key unique nulls not distinct (organization_id, action)
);

create index if not exists idx_role_permissions_org
    on public.role_permissions (organization_id);

-- The app uses the service-role key, which bypasses RLS; enabling it denies
-- anon/authenticated clients by default (matches parsing_engine_instances).
alter table public.role_permissions enable row level security;

revoke all privileges on table public.role_permissions from anon, authenticated;
grant select, insert, update, delete on table public.role_permissions to service_role;

revoke usage on sequence public.role_permissions_id_seq from anon, authenticated;
grant usage on sequence public.role_permissions_id_seq to service_role;
