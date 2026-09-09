"""Reports which documented environment variables are loaded, without exposing their values.

Backs the admin "Environment" tab (superadmin-only, see app/api/settings.py)
so missing config is visible at a glance instead of surfacing later as an
opaque 401/500 from whichever provider needed it. `ENV_VAR_REGISTRY` is
maintained by hand alongside app/modules/config.py and the other modules
that read `os.environ`/`os.getenv` directly -- add an entry here whenever a
new one is introduced.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EnvVarSpec:
    name: str
    category: str
    description: str
    required: bool = False


ENV_VAR_REGISTRY: list[EnvVarSpec] = [
    # ── Supabase (database, auth, storage) ──────────────────────────────────
    EnvVarSpec("SUPABASE_URL", "Supabase", "Project REST/Auth base URL.", required=True),
    EnvVarSpec(
        "SUPABASE_SERVICE_ROLE_KEY",
        "Supabase",
        "Service-role key used for backend persistence & object storage.",
        required=True,
    ),
    EnvVarSpec("SUPABASE_KEY", "Supabase", "Fallback key read when SUPABASE_SERVICE_ROLE_KEY is unset."),
    EnvVarSpec("SUPABASE_JWKS_URL", "Supabase", "JWKS endpoint used to verify user JWTs (app/auth.py)."),
    EnvVarSpec("SUPABASE_STORAGE_BUCKET", "Supabase", "Object storage bucket for uploaded documents/artifacts."),
    EnvVarSpec("SUPABASE_STORAGE_PREFIX", "Supabase", "Optional key prefix within the storage bucket."),
    # ── LLM providers ────────────────────────────────────────────────────────
    # DB llm_provider_instances rows take precedence over all of these -- see
    # app/modules/llm_providers/key_resolver.py. They're only the fallback
    # used when an org has no matching instance configured.
    EnvVarSpec("OPENROUTER_API_KEY", "LLM Providers", "Fallback OpenRouter key when no DB provider instance is configured."),
    EnvVarSpec("OPENROUTER_APP_NAME", "LLM Providers", "App-name header OpenRouter shows against usage."),
    EnvVarSpec("OPENAI_API_KEY", "LLM Providers", "Fallback OpenAI key when no DB provider instance is configured."),
    EnvVarSpec("OPENAI_MODEL", "LLM Providers", "Default OpenAI model id."),
    EnvVarSpec("GEMINI_API_KEY", "LLM Providers", "Fallback Gemini key when no DB provider instance is configured."),
    EnvVarSpec("ANTHROPIC_API_KEY", "LLM Providers", "Fallback Anthropic key when no DB provider instance is configured."),
    EnvVarSpec("OLLAMA_API_BASE", "LLM Providers", "Base URL of a self-hosted Ollama server."),
    EnvVarSpec("BIM_GUARD_LLM_MODEL", "LLM Providers", "Default LiteLLM model route (e.g. openrouter/auto)."),
    # ── Document parsing ─────────────────────────────────────────────────────
    # Seed-only: parsing_engine_instances DB rows are the source of truth once
    # they exist -- see app/modules/config.py's own comments on these.
    EnvVarSpec("UNSTRUCTURED_API_KEY", "Document Parsing", "Seeds the hosted Unstructured parsing_engine_instances row on first boot."),
    EnvVarSpec("UNSTRUCTURED_API_URL", "Document Parsing", "Seeds the hosted Unstructured parsing_engine_instances row on first boot."),
    EnvVarSpec("UNSTRUCTURED_STRATEGY", "Document Parsing", "Default Unstructured parsing strategy."),
    EnvVarSpec("UNSTRUCTURED_LOCAL_URL", "Document Parsing", "Seeds a self-hosted Unstructured parsing_engine_instances row on first boot."),
    EnvVarSpec("DOCLING_SERVICE_URL", "Document Parsing", "Seeds the hosted Docling parsing_engine_instances row on first boot."),
    EnvVarSpec("DOCLING_API_KEY", "Document Parsing", "Seeds the hosted Docling parsing_engine_instances row on first boot."),
    EnvVarSpec("DOCLING_LOCAL_URL", "Document Parsing", "Seeds a self-hosted Docling parsing_engine_instances row on first boot."),
    # ── Integrations ─────────────────────────────────────────────────────────
    EnvVarSpec("GOOGLE_DRIVE_API_KEY", "Integrations", "API-key-only access to public Google Drive file imports."),
    EnvVarSpec("GITHUB_TOKEN", "Integrations", "Token for GitHub repository sync/import."),
    EnvVarSpec("BSDD_API_BASE_URL", "Integrations", "buildingSMART Data Dictionary API base URL (has a working default)."),
    # ── Server / app ─────────────────────────────────────────────────────────
    EnvVarSpec("PORT", "Server", "HTTP port uvicorn binds to."),
    EnvVarSpec("BIM_GUARD_ALLOWED_ORIGINS", "Server", "Comma-separated CORS allow-list."),
    EnvVarSpec("BIM_GUARD_LOG_LEVEL", "Server", "Log verbosity override."),
    EnvVarSpec("BIM_GUARD_LOG_FILE", "Server", "Optional log file path."),
    EnvVarSpec("BIM_GUARD_VERBOSITY", "Server", "CLI/agent verbosity level."),
    # ── Feature flags ────────────────────────────────────────────────────────
    EnvVarSpec("FEATURE_PATH_B_MM", "Feature Flags", "Enables the MM-001 comparator."),
    EnvVarSpec("FEATURE_PATH_B_XM", "Feature Flags", "Enables the XM-001 (DRAFT) comparator."),
    EnvVarSpec("FEATURE_XM_GEOMETRIC_ADJACENCY", "Feature Flags", "Enables Tier-3 tessellated-surface adjacency for XM-001."),
    # ── AI module (experimental orchestrator, app/ai/) ──────────────────────
    EnvVarSpec("AI_FEATURE_ENABLED", "AI Module", "Master switch for the app/ai orchestrator module."),
    EnvVarSpec("AI_VLM_ENABLED", "AI Module", "Enables vision-language-model features."),
    EnvVarSpec("AI_AGENT_ORCHESTRATOR_ENABLED", "AI Module", "Enables the AI agent orchestrator."),
    EnvVarSpec("AI_DEFAULT_LLM", "AI Module", "Default LLM backend id for the AI module."),
    EnvVarSpec("AI_DEFAULT_VISION", "AI Module", "Default vision backend id for the AI module."),
    EnvVarSpec("AI_PREDICTIVE_BACKEND", "AI Module", "Default predictive-model backend id."),
    # ── Agent CLI (app/agent) ────────────────────────────────────────────────
    EnvVarSpec("BIM_GUARD_AGENT_MODEL", "Agent CLI", "Model used by the standalone agent CLI."),
    EnvVarSpec("BIM_GUARD_AGENT_MAX_STEPS", "Agent CLI", "Max reasoning steps per agent CLI run."),
    EnvVarSpec("BIM_GUARD_AGENT_MAX_COST", "Agent CLI", "Max USD cost per agent CLI run."),
    EnvVarSpec("BIM_GUARD_AGENT_SESSION_DIR", "Agent CLI", "Session/transcript storage directory."),
    EnvVarSpec("BIM_GUARD_AGENT_WEB_SEARCH", "Agent CLI", "Enables the web search tool for the agent CLI."),
]


def get_env_status() -> list[dict]:
    """Return {name, category, description, required, is_set} for every registered var.

    Never returns the variable's value -- only whether it is set to a
    non-empty string in this process's environment.
    """
    return [
        {
            "name": spec.name,
            "category": spec.category,
            "description": spec.description,
            "required": spec.required,
            "is_set": bool(os.environ.get(spec.name, "").strip()),
        }
        for spec in ENV_VAR_REGISTRY
    ]
