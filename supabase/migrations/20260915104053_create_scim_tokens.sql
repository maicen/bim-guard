-- Migration: create_scim_tokens
-- Description: One rotatable bearer token per organization, used to
-- authenticate SCIM 2.0 provisioning requests from an external IdP (Okta,
-- Azure AD, ...) against /api/scim/v2/* -- a materially different scheme
-- from Supabase-JWT human auth (see app/scim_auth.py). Only the SHA-256
-- hash of the token is ever persisted; the raw value is shown once, at mint
-- time, by POST /api/organizations/{organization_id}/scim-token.

create table if not exists public.scim_tokens (
    id bigint generated always as identity primary key,
    organization_id bigint not null references public.organizations(id) on delete cascade,
    token_hash text not null,
    created_at timestamptz not null default now(),
    last_used_at timestamptz,
    revoked_at timestamptz,
    constraint scim_tokens_org_key unique (organization_id)
);

create index if not exists idx_scim_tokens_org
    on public.scim_tokens (organization_id);

-- The app uses the service-role key, which bypasses RLS; enabling it denies
-- anon/authenticated clients by default (matches role_permissions).
alter table public.scim_tokens enable row level security;

revoke all privileges on table public.scim_tokens from anon, authenticated;
grant select, insert, update, delete on table public.scim_tokens to service_role;

revoke usage on sequence public.scim_tokens_id_seq from anon, authenticated;
grant usage on sequence public.scim_tokens_id_seq to service_role;
