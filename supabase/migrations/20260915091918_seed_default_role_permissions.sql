-- Migration: seed_default_role_permissions
-- Description: Seed the platform-default row (organization_id NULL) for
-- every action defined in app.modules.permissions.Action, reproducing
-- today's hardcoded "owner or admin only" behavior exactly. Nothing changes
-- functionally until a superadmin edits the matrix.

insert into public.role_permissions (organization_id, action, min_role) values
    (null, 'manage_org_members', 'admin'),
    (null, 'manage_llm_providers', 'admin'),
    (null, 'manage_project_bindings', 'admin'),
    (null, 'manage_parsing_engines', 'admin')
on conflict do nothing;
