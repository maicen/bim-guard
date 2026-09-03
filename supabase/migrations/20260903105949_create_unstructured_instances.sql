-- Migration: create_unstructured_instances
-- Description: Registry of configured Unstructured parsing-engine instances
-- (a local self-hosted Docker container and/or one or more hosted Platform
-- API accounts) that document extraction can pick between.

CREATE TABLE IF NOT EXISTS public.unstructured_instances (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('local', 'hosted')),
    api_url TEXT NOT NULL,
    api_key TEXT NOT NULL DEFAULT '',
    strategy TEXT NOT NULL DEFAULT 'auto',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- At most one default instance at a time.
CREATE UNIQUE INDEX IF NOT EXISTS unstructured_instances_single_default
    ON public.unstructured_instances (is_default)
    WHERE is_default;

CREATE INDEX IF NOT EXISTS idx_unstructured_instances_enabled
    ON public.unstructured_instances (is_enabled);

-- The app uses the service-role key, which bypasses RLS; enabling it denies
-- anon/authenticated clients by default (matches github_repositories).
ALTER TABLE public.unstructured_instances ENABLE ROW LEVEL SECURITY;
