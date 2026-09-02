-- Migration: create_github_repositories
-- Description: Adds github_repositories table to store project storage source repositories and seeds bimguard-test-models.

CREATE TABLE IF NOT EXISTS public.github_repositories (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name TEXT NOT NULL,
    owner TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    branch TEXT NOT NULL DEFAULT 'main',
    description TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for lookup by url
CREATE INDEX IF NOT EXISTS idx_github_repositories_url ON public.github_repositories(url);
CREATE INDEX IF NOT EXISTS idx_github_repositories_owner_name ON public.github_repositories(owner, name);

-- Seed default test models repository
INSERT INTO public.github_repositories (name, owner, url, branch, description)
VALUES (
    'bimguard-test-models',
    'maicen',
    'https://github.com/maicen/bimguard-test-models',
    'main',
    'Official BIM-Guard test models repository containing architectural, structural, HVAC, electrical, and plumbing IFC models.'
)
ON CONFLICT (url) DO NOTHING;

-- The app uses the service-role key, which bypasses RLS; enabling it denies
-- anon/authenticated clients by default (see client_documents migration).
-- This was missing from the original migration, flagged by the Supabase
-- linter's rls_disabled_in_public ERROR once the table went live.
ALTER TABLE public.github_repositories ENABLE ROW LEVEL SECURITY;
