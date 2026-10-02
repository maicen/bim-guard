-- Migration: create_llm_task_model_assignments
-- Description: Per-organization curated model shortlists per LLM-consuming
-- task (e.g. "rule_extraction"). Task keys are owned by LLM_TASKS
-- (app/modules/llm_providers/tasks.py) in application code, not a CHECK
-- constraint, mirroring how llm_provider_instances.kind is validated. Each
-- row caches the model's name/context/pricing at shortlist time so the
-- shortlist renders instantly without re-fetching a provider's live
-- catalogue, and survives that catalogue changing later.

create table if not exists public.llm_task_model_assignments (
    id bigint generated always as identity primary key,
    organization_id bigint not null references public.organizations(id) on delete cascade,
    task_key text not null,
    provider_instance_id bigint not null references public.llm_provider_instances(id) on delete cascade,
    model_id text not null,
    model_name text not null,
    context_length integer,
    input_price_per_million numeric,
    output_price_per_million numeric,
    is_default boolean not null default false,
    created_at timestamptz not null default now(),
    constraint llm_task_model_assignments_key unique (organization_id, task_key, provider_instance_id, model_id)
);

-- At most one default model per organization+task.
create unique index if not exists llm_task_model_assignments_single_default_per_task
    on public.llm_task_model_assignments (organization_id, task_key)
    where is_default;

create index if not exists idx_llm_task_model_assignments_org_task
    on public.llm_task_model_assignments (organization_id, task_key);

-- The app uses the service-role key, which bypasses RLS; enabling it denies
-- anon/authenticated clients by default (matches llm_provider_instances).
alter table public.llm_task_model_assignments enable row level security;

revoke all privileges on table public.llm_task_model_assignments from anon, authenticated;
grant select, insert, update, delete on table public.llm_task_model_assignments to service_role;

revoke usage on sequence public.llm_task_model_assignments_id_seq from anon, authenticated;
grant usage on sequence public.llm_task_model_assignments_id_seq to service_role;
