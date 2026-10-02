-- Migration: create_llm_provider_instances
-- Description: Registry of configured LLM provider instances (OpenAI,
-- Anthropic, Gemini, OpenRouter, a self-hosted Ollama server, ...), scoped
-- per organization -- each org brings its own API keys. Mirrors
-- parsing_engine_instances (a platform-wide equivalent for document
-- parsing) but adds organization_id and enforces "one default per org"
-- rather than one default globally. `kind` has no CHECK constraint: the set
-- of valid kinds is owned by LLMProviderRegistry (app/modules/llm_providers)
-- in application code, which the service validates against at request time.

create table if not exists public.llm_provider_instances (
    id bigint generated always as identity primary key,
    organization_id bigint not null references public.organizations(id) on delete cascade,
    name text not null,
    kind text not null,
    api_key text not null default '',
    api_base text not null default '',
    is_default boolean not null default false,
    is_enabled boolean not null default true,
    notes text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint llm_provider_instances_org_name_key unique (organization_id, name)
);

-- At most one default instance per organization.
create unique index if not exists llm_provider_instances_single_default_per_org
    on public.llm_provider_instances (organization_id)
    where is_default;

create index if not exists idx_llm_provider_instances_org
    on public.llm_provider_instances (organization_id);

-- The app uses the service-role key, which bypasses RLS; enabling it denies
-- anon/authenticated clients by default (matches parsing_engine_instances).
alter table public.llm_provider_instances enable row level security;

revoke all privileges on table public.llm_provider_instances from anon, authenticated;
grant select, insert, update, delete on table public.llm_provider_instances to service_role;

revoke usage on sequence public.llm_provider_instances_id_seq from anon, authenticated;
grant usage on sequence public.llm_provider_instances_id_seq to service_role;
