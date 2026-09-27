"""Dashboard stats, application settings, environment variables, and LLM/parsing configurations."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.modules.contracts.base import TimestampFields

__all__ = ['DashboardStatsResponse', 'SettingItemContract', 'SettingsResponseContract', 'SettingsUpdateRequestContract', 'EnvVarStatusItem', 'EnvVarStatusResponse', 'ParsingEngineInstanceCreateRequest', 'ParsingEngineInstanceUpdateRequest', 'ParsingEngineInstanceResponse', 'ParsingEngineInstanceTestResponse', 'ParsingEngineKindResponse', 'PermissionActionResponse', 'RolePermissionResponse', 'RolePermissionSetRequest', 'ScimTokenStatusResponse', 'ScimTokenMintResponse', 'AuditLogEntryResponse', 'AuditLogListResponse', 'LLMCallLogEntryResponse', 'LLMCallLogListResponse', 'LLMProviderInstanceCreateRequest', 'LLMProviderInstanceUpdateRequest', 'LLMProviderInstanceResponse', 'LLMProviderInstanceTestResponse', 'LLMProviderTestConnectionRequest', 'LLMProviderKindResponse', 'LLMProviderModelResponse', 'LLMTaskResponse', 'LLMTaskAssignmentModelInput', 'LLMTaskAssignmentSetRequest', 'LLMTaskModelAssignmentResponse']

class DashboardStatsResponse(BaseModel):
    """Dashboard connectivity/health status.

    Previously also carried total_projects/total_documents/total_rules/
    issues_found -- dropped along with the dashboard stat tiles that
    rendered them (see DashboardView.svelte); nothing reads them anymore.
    """

    db_ok: bool = Field(True, description="Database connection health status")
    db_backend: str = Field("SUPABASE", description="Primary database backend (SUPABASE)")

class SettingItemContract(BaseModel):
    """Single application runtime configuration setting."""

    key: str = Field(..., description="Configuration key")
    value: str = Field(..., description="Configuration value")
    description: str = Field("", description="Setting purpose or documentation")

class SettingsResponseContract(BaseModel):
    """Response container for runtime settings and active database backend."""

    settings: list[SettingItemContract] = Field(default_factory=list)
    active_log_level: str = Field("INFO", description="Current logging level")
    db_backend: str = Field("SUPABASE", description="Active database backend")

class SettingsUpdateRequestContract(BaseModel):
    """Payload for batch updating application settings."""

    settings: dict[str, str] = Field(..., description="Map of setting key to new value")

class EnvVarStatusItem(BaseModel):
    """Whether one documented environment variable is loaded -- never its value."""

    name: str = Field(..., description="Environment variable name")
    category: str = Field(..., description="Grouping shown in the admin UI (e.g. 'LLM Providers')")
    description: str = Field("", description="What this variable controls")
    required: bool = Field(False, description="Whether the app expects this to always be set")
    is_set: bool = Field(..., description="True when set to a non-empty value in this process's environment")

class EnvVarStatusResponse(BaseModel):
    """Response container for the admin Environment tab's loaded/missing report."""

    variables: list[EnvVarStatusItem] = Field(default_factory=list)

# ==============================================================================
# Parsing Engine Instance Contracts
# ==============================================================================
#
# `kind` is deliberately a plain `str`, not a Literal enumerating known
# values: the set of valid kinds is owned by ParsingEngineRegistry
# (app/modules/document_parsing/engines), which can grow without touching
# this contract. ParsingEngineInstancesService validates a submitted kind
# against the registry at request time; GET /api/parsing-engines/kinds
# (ParsingEngineKindResponse) is the discoverable source of truth for what's
# currently valid, and is what the Settings UI renders its kind selector from.


class ParsingEngineInstanceCreateRequest(BaseModel):
    """Payload for registering a new document-parsing engine instance."""

    name: str = Field(..., min_length=1, description="Unique display name, e.g. 'local', 'hosted-1', 'docling'")
    kind: str = Field(
        ..., min_length=1, description="A registered engine kind — see GET /api/parsing-engines/kinds"
    )
    api_url: str = Field(..., min_length=1, description="Base URL of the parsing engine server")
    api_key: Optional[str] = Field(
        None, description="API key — required for kinds where GET /api/parsing-engines/kinds reports requires_api_key"
    )
    strategy: Optional[str] = Field(
        "auto",
        description="Partition strategy (only meaningful for kinds where supports_strategy is true, e.g. auto, fast, hi_res, ocr_only)",
    )
    is_default: Optional[bool] = Field(False, description="Use this instance when none is explicitly selected")
    is_enabled: Optional[bool] = Field(True, description="Whether this instance is selectable")
    notes: Optional[str] = Field("", description="Optional free-text notes")

class ParsingEngineInstanceUpdateRequest(BaseModel):
    """Payload for updating an existing parsing-engine instance.

    `kind` cannot be changed after creation — register a new instance instead.
    """

    name: Optional[str] = Field(None, description="Updated display name")
    api_url: Optional[str] = Field(None, description="Updated server URL")
    api_key: Optional[str] = Field(None, description="Updated API key (omit to leave unchanged)")
    strategy: Optional[str] = Field(None, description="Updated partition strategy")
    is_default: Optional[bool] = Field(None, description="Make (or unmake) this the default instance")
    is_enabled: Optional[bool] = Field(None, description="Toggle whether this instance is selectable")
    notes: Optional[str] = Field(None, description="Updated notes")

class ParsingEngineInstanceResponse(TimestampFields):
    """Response contract for a registered parsing-engine instance.

    The stored api_key is never echoed back — only whether one is set.
    `organization_id` is null for the platform-wide tier (superadmin-managed)
    and set for an org-scoped instance (owner/admin-managed).
    """

    id: int
    organization_id: Optional[int] = None
    name: str
    kind: str
    api_url: str
    has_api_key: bool = False
    strategy: str = "auto"
    is_default: bool = False
    is_enabled: bool = True
    notes: str = ""

class ParsingEngineInstanceTestResponse(BaseModel):
    """Result of a connectivity check against a configured instance."""

    ok: bool
    detail: str = ""

class ParsingEngineKindResponse(BaseModel):
    """Metadata for one registered parsing-engine kind (a ParsingEngineDriver).

    Drives the Settings UI's kind selector — a new backend driver shows up
    there automatically, with no frontend changes.
    """

    kind: str
    family: str
    display_name: str
    description: str = ""
    requires_api_key: bool = False
    supports_strategy: bool = False
    url_placeholder: str = ""
    docs_url: str = ""

# ==============================================================================
# Role Permission Matrix Contracts (see app/modules/permissions, app/services/permission_service.py)
# ==============================================================================


class PermissionActionResponse(BaseModel):
    """One role-gated action from app.modules.permissions.Action."""

    action: str
    description: str = ""

class RolePermissionResponse(BaseModel):
    """The effective minimum role for one action in one scope.

    `is_override` is True when this reflects an org-specific row rather than
    the platform default falling through unmodified.
    """

    action: str
    min_role: str
    is_override: bool = False

class RolePermissionSetRequest(BaseModel):
    """Payload for setting an action's minimum role in a scope.

    `organization_id` omitted (or null) targets the platform default;
    otherwise it targets that organization's override.
    """

    organization_id: Optional[int] = Field(None, description="Target organization, or null for the platform default")
    min_role: str = Field(..., description="'owner', 'admin', or 'member'")

# ==============================================================================
# SCIM Token Contracts (see app/services/scim_token_service.py)
# ==============================================================================
#
# These are the human-facing REST contracts for managing a SCIM token
# (mint/status/revoke) -- the SCIM protocol's own wire format (Users,
# Groups, PATCH ops) lives separately in app/modules/scim_contracts.py.


class ScimTokenStatusResponse(BaseModel):
    """Metadata about an organization's SCIM provisioning token -- never the raw value."""

    configured: bool
    base_url: str
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    revoked: bool = False

class ScimTokenMintResponse(BaseModel):
    """The one-time response to minting or rotating a SCIM token.

    `token` is shown exactly once; only its hash is ever persisted (see
    app.services.scim_token_service.ScimTokenService).
    """

    token: str
    base_url: str

# ==============================================================================
# Audit Log Contracts (see app/services/audit_log_service.py)
# ==============================================================================


class AuditLogEntryResponse(BaseModel):
    """One recorded sensitive mutation."""

    id: int
    occurred_at: str
    actor_id: str
    actor_email: Optional[str] = None
    organization_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

class AuditLogListResponse(BaseModel):
    """A page of audit log entries, newest first."""

    entries: list[AuditLogEntryResponse]

# ==============================================================================
# LLM Call Log Contracts (see app/services/llm_call_log_service.py)
# ==============================================================================


class LLMCallLogEntryResponse(BaseModel):
    """One recorded LLM API call."""

    id: int
    occurred_at: str
    organization_id: Optional[int] = None
    project_id: Optional[int] = None
    run_key: Optional[str] = None
    context: str
    provider: Optional[str] = None
    model: str
    input: list[dict] = Field(default_factory=list)
    output: Optional[str] = None
    status: str
    error: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = None
    latency_ms: Optional[int] = None
    metadata: dict = Field(default_factory=dict)

class LLMCallLogListResponse(BaseModel):
    """A page of LLM call log entries, newest first."""

    entries: list[LLMCallLogEntryResponse]

# ==============================================================================
# LLM Provider Instance Contracts (org-scoped — see app/modules/llm_providers)
# ==============================================================================


class LLMProviderInstanceCreateRequest(BaseModel):
    """Payload for registering a new LLM provider instance within an organization."""

    name: str = Field(..., min_length=1, description="Unique (per org) display name, e.g. 'openrouter-main'")
    kind: str = Field(
        ..., min_length=1, description="A registered provider kind — see GET .../llm-providers/kinds"
    )
    api_key: Optional[str] = Field(
        None, description="API key — required for kinds where GET .../llm-providers/kinds reports requires_api_key"
    )
    api_base: Optional[str] = Field(None, description="Override the provider's default API base URL")
    is_default: Optional[bool] = Field(False, description="Use this instance when none is explicitly selected")
    is_enabled: Optional[bool] = Field(True, description="Whether this instance is selectable")
    notes: Optional[str] = Field(None, description="Freeform notes")

class LLMProviderInstanceUpdateRequest(BaseModel):
    """Payload for updating an existing LLM provider instance.

    `kind` cannot be changed after creation — register a new instance instead.
    """

    name: Optional[str] = Field(None, description="Updated display name")
    api_key: Optional[str] = Field(None, description="Updated API key (omit to leave unchanged)")
    api_base: Optional[str] = Field(None, description="Updated API base URL override")
    is_default: Optional[bool] = Field(None, description="Make (or unmake) this the org's default instance")
    is_enabled: Optional[bool] = Field(None, description="Toggle whether this instance is selectable")
    notes: Optional[str] = Field(None, description="Updated notes")

class LLMProviderInstanceResponse(TimestampFields):
    """Response contract for a registered LLM provider instance.

    The stored api_key is never echoed back — only whether one is set.
    """

    id: int
    organization_id: int
    name: str
    kind: str
    api_base: str = ""
    has_api_key: bool = False
    is_default: bool = False
    is_enabled: bool = True
    notes: str = ""

class LLMProviderInstanceTestResponse(BaseModel):
    """Result of a connectivity check against an LLM provider instance or candidate credentials."""

    ok: bool
    detail: str = ""

class LLMProviderTestConnectionRequest(BaseModel):
    """Payload for testing connectivity before saving an LLM provider instance."""

    kind: str = Field(
        ..., min_length=1, description="A registered provider kind — see GET .../llm-providers/kinds"
    )
    api_key: Optional[str] = Field(None, description="API key to test against the provider")
    api_base: Optional[str] = Field(None, description="Candidate API base URL override")

class LLMProviderKindResponse(BaseModel):
    """Metadata for one registered LLM provider kind (an LLMProviderDriver).

    Drives the External Providers UI's kind selector — a new backend driver
    shows up there automatically, with no frontend changes.
    """

    kind: str
    display_name: str
    description: str = ""
    requires_api_key: bool = False
    default_api_base: str = ""
    url_placeholder: str = ""

class LLMProviderModelResponse(BaseModel):
    """One model available from a configured LLM provider instance.

    Pricing/context_length are only populated for drivers whose provider
    publishes them (OpenRouter, and context_length for Gemini) — null for
    the rest, an honest gap rather than a guess.
    """

    id: str
    name: str
    context_length: Optional[int] = None
    input_price_per_million: Optional[float] = Field(
        None, description="USD per 1,000,000 input tokens"
    )
    output_price_per_million: Optional[float] = Field(
        None, description="USD per 1,000,000 output tokens"
    )
    capabilities: list[str] = Field(default_factory=list)

class LLMTaskResponse(BaseModel):
    """One task an org can assign a curated model shortlist to."""

    key: str
    label: str
    description: str = ""

class LLMTaskAssignmentModelInput(BaseModel):
    """One shortlisted model in a PUT .../task-assignments/{task_key} request."""

    provider_instance_id: int
    model_id: str
    model_name: str
    context_length: Optional[int] = None
    input_price_per_million: Optional[float] = None
    output_price_per_million: Optional[float] = None

class LLMTaskAssignmentSetRequest(BaseModel):
    """Payload replacing an organization's whole model shortlist for one task."""

    models: list[LLMTaskAssignmentModelInput] = Field(default_factory=list)
    default_provider_instance_id: Optional[int] = Field(
        None, description="Must match one entry in `models`, or be omitted for no default"
    )
    default_model_id: Optional[str] = None

class LLMTaskModelAssignmentResponse(BaseModel):
    """One shortlisted model for a task, as returned to the frontend."""

    task_key: str
    provider_instance_id: int
    provider_instance_name: str
    model_id: str
    model_name: str
    context_length: Optional[int] = None
    input_price_per_million: Optional[float] = None
    output_price_per_million: Optional[float] = None
    is_default: bool = False
