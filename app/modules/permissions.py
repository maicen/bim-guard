"""Catalogue of superadmin-configurable, role-gated actions.

Each `Action` names one place in the app where a caller's org role (owner /
admin / member) gates a mutation — today that's every hardcoded
"only an owner or admin can do this" check in app/api/organizations.py,
app/api/llm_provider_instances.py, and app/api/projects.py, plus the new
org-scoped parsing-engine management introduced alongside this module. Roles
are strictly hierarchical (owner > admin > member) for every one of these
checks, so PermissionService (app/services/permission_service.py) evaluates
each action as a *minimum role* rather than a per-role boolean grid.

Adding a new gated action means adding a member here, a default row in the
seed migration (supabase/migrations/..._seed_default_role_permissions.sql),
and a `permissions.require(...)` call at the route — never a new hardcoded
`role not in (...)` check.
"""

from __future__ import annotations

from enum import Enum


class Action(str, Enum):
    """A role-gated mutation, superadmin-tunable per organization."""

    MANAGE_ORG_MEMBERS = "manage_org_members"
    """Organization membership: roles, removal, invites, groups, group project grants."""

    MANAGE_LLM_PROVIDERS = "manage_llm_providers"
    """Create/update/delete/test an organization's LLM provider instances and task shortlists."""

    MANAGE_PROJECT_BINDINGS = "manage_project_bindings"
    """Change which rulesets/documents are bound to a project."""

    MANAGE_PARSING_ENGINES = "manage_parsing_engines"
    """Create/update/delete/test an organization's document-parsing engine instances."""


ACTION_DESCRIPTIONS: dict[Action, str] = {
    Action.MANAGE_ORG_MEMBERS: "Manage organization members, invites, and groups",
    Action.MANAGE_LLM_PROVIDERS: "Manage LLM provider instances and task model shortlists",
    Action.MANAGE_PROJECT_BINDINGS: "Change a project's bound rulesets and documents",
    Action.MANAGE_PARSING_ENGINES: "Manage document-parsing engine instances",
}

ROLE_RANK: dict[str, int] = {"member": 0, "admin": 1, "owner": 2}
"""Ordinal rank for the strict owner > admin > member hierarchy every gated action uses."""
