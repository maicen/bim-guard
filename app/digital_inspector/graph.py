"""Compiled LangGraph state machine for the Digital Inspector agent.

Built on LangGraph's prebuilt `create_react_agent`: a two-node state graph
(agent <-> tools) with conditional edges routing on whether the model's
last message requested a tool call, looping until it answers directly or a
step limit is hit. This is the "cyclical multi-tool execution" state
machine called for in TODO.md Priority 10 — using LangGraph's own
production-grade ReAct implementation rather than hand-rolling the same
routing logic.
"""

from __future__ import annotations

from functools import lru_cache

from app.digital_inspector.tools import DIGITAL_INSPECTOR_TOOLS

_SYSTEM_PROMPT = """\
You are the BIM-Guard Digital Inspector, an assistant that helps users
investigate a project's compliance status by calling the tools available
to you: looking up IFC model metadata, checking which rules already exist
for a ruleset, searching the buildingSMART Data Dictionary (bSDD), running
the compliance validation pipeline, and extracting rule drafts from
uploaded documents.

Always ground your answer in tool results — do not guess at rule IDs,
element GUIDs, or compliance outcomes. If a tool reports an error (e.g. a
missing project or document), report that plainly instead of inventing a
result.
"""


def _build_llm(organization_id: int | None = None):
    """Construct the LangChain-compatible LiteLLM chat model from shared app config.

    Args:
        organization_id: Resolves the API key from that org's configured
            LLM provider instance first, falling back to the provider's env
            var — see ``app.modules.llm_providers.key_resolver``.
    """
    from langchain_litellm import ChatLiteLLM

    from app.modules.config import COMPLIANCE_TEMPERATURE, DEFAULT_LLM_MODEL
    from app.modules.llm_providers.key_resolver import resolve_api_key

    provider = DEFAULT_LLM_MODEL.split("/", 1)[0] if "/" in DEFAULT_LLM_MODEL else "openrouter"
    api_key = resolve_api_key(provider, organization_id)

    return ChatLiteLLM(model=DEFAULT_LLM_MODEL, temperature=COMPLIANCE_TEMPERATURE, api_key=api_key)


@lru_cache(maxsize=None)
def build_digital_inspector_graph(organization_id: int | None = None):
    """Compile the Digital Inspector's ReAct graph, cached per organization.

    Compiling a LangGraph graph is cheap but not free; `ApplicationContainer`
    (see app.bootstrap) held this as a single process-wide singleton before
    per-org API keys existed. `lru_cache` now keys on `organization_id`
    instead, so each org's graph (and its resolved API key) is compiled
    once and reused, rather than recompiling per request.
    """
    from langgraph.prebuilt import create_react_agent

    return create_react_agent(
        _build_llm(organization_id),
        DIGITAL_INSPECTOR_TOOLS,
        prompt=_SYSTEM_PROMPT,
    )
