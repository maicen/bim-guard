-- Migration: seed_manage_scim_permission
-- Description: Seed the platform-default row (organization_id NULL) for the
-- new `manage_scim` action (app.modules.permissions.Action.MANAGE_SCIM),
-- gating who can mint/rotate/revoke an organization's SCIM provisioning
-- token. Matches the existing default of 'admin' used for every other
-- role-gated action seeded in 20260915091918_seed_default_role_permissions.sql.

insert into public.role_permissions (organization_id, action, min_role) values
    (null, 'manage_scim', 'admin')
on conflict do nothing;
