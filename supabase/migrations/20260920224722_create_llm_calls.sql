-- Migration: create_llm_calls
-- Description: Append-only record of every LLM API call made by the app
-- (deontic extraction, rule generation, Digital Inspector, the coding
-- agent) for R&D purposes -- comparing models, inspecting prompts/outputs,
-- and tracking token usage/latency/cost over time. Written exclusively by
-- LLMCallLogService via the service-role key (see
-- app/services/llm_logging_callback.py, registered on litellm.callbacks at
-- bootstrap); RLS denies anon/authenticated direct access entirely, matching
-- the audit_log pattern -- reads go through the superadmin-gated
-- /api/llm-calls endpoint, never direct table access from the client.

create table if not exists public.llm_calls (
    id bigint generated always as identity primary key,
    occurred_at timestamptz not null default now(),
    organization_id bigint references public.organizations(id) on delete set null,
    project_id bigint references public.projects(id) on delete set null,
    run_key text,
    context text not null,
    provider text,
    model text not null,
    input jsonb not null default '[]'::jsonb,
    output text,
    status text not null default 'success',
    error text,
    input_tokens integer,
    output_tokens integer,
    total_tokens integer,
    cost numeric,
    latency_ms integer,
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_llm_calls_occurred_at on public.llm_calls (occurred_at desc);
create index if not exists idx_llm_calls_organization on public.llm_calls (organization_id);
create index if not exists idx_llm_calls_project on public.llm_calls (project_id);
create index if not exists idx_llm_calls_context on public.llm_calls (context);

-- The app uses the service-role key, which bypasses RLS; enabling it denies
-- anon/authenticated clients by default (matches audit_log).
alter table public.llm_calls enable row level security;

-- Insert-only from the app's perspective: no update/delete grant to
-- service_role either, so even a compromised backend process cannot tamper
-- with existing entries -- only append new ones and select them back.
revoke all privileges on table public.llm_calls from anon, authenticated;
grant select, insert on table public.llm_calls to service_role;

revoke usage on sequence public.llm_calls_id_seq from anon, authenticated;
grant usage on sequence public.llm_calls_id_seq to service_role;
