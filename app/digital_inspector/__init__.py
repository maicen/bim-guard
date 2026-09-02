"""Digital Inspector — a LangGraph agent for interactive compliance queries.

Separate from `app/agent/` (a generic OpenRouter/LiteLLM coding-assistant
with file/shell tools and its own `bim-guard-agent` CLI) — this package is
domain-specific: it coordinates IFC/database/bSDD/validation tool calls to
answer ad-hoc questions about a project ("why did element X fail", "look up
bSDD class for this pipe"), a different use case from the deterministic
batch pipeline in `app.modules.orchestrator.orchestrate_workflow`, which
remains the default synchronous compliance run.
"""
