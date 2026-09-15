-- Migration: create_audit_log
-- Description: Append-only record of sensitive mutations (role changes,
-- permission matrix edits, document/project deletion, etc.) for security
-- audit trail purposes (SOC 2 / ISO 27001 evidence). Written exclusively by
-- AuditLogService via the service-role key; RLS denies anon/authenticated
-- direct access entirely, matching the role_permissions/parsing_engine_instances
-- pattern -- reads go through the superadmin-gated /api/audit-log endpoint,
-- never direct table access from the client.

create table if not exists public.audit_log (
    id bigint generated always as identity primary key,
    occurred_at timestamptz not null default now(),
    actor_id text not null,
    actor_email text,
    organization_id bigint references public.organizations(id) on delete set null,
    action text not null,
    resource_type text not null,
    resource_id text,
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_audit_log_occurred_at on public.audit_log (occurred_at desc);
create index if not exists idx_audit_log_organization on public.audit_log (organization_id);
create index if not exists idx_audit_log_actor on public.audit_log (actor_id);

-- The app uses the service-role key, which bypasses RLS; enabling it denies
-- anon/authenticated clients by default (matches role_permissions).
alter table public.audit_log enable row level security;

-- Insert-only from the app's perspective: no update/delete grant to
-- service_role either, so even a compromised backend process cannot tamper
-- with existing entries -- only append new ones and select them back.
revoke all privileges on table public.audit_log from anon, authenticated;
grant select, insert on table public.audit_log to service_role;

revoke usage on sequence public.audit_log_id_seq from anon, authenticated;
grant usage on sequence public.audit_log_id_seq to service_role;
