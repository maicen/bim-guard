"""Registry of tasks an org can assign a curated model shortlist to.

A plain module-level list, not a database table — like LLMProviderRegistry's
kinds, the set of tasks is a build-time property of the codebase (which
features actually accept a model override), not runtime configuration.
Exposed to the frontend via GET .../llm-providers/tasks so it never
hardcodes this list either.

Adding a task here only registers it for shortlisting in the External
Providers admin UI — actually consuming an org's shortlist for a given task
still means wiring that feature's call site to read from
LLMTaskAssignmentService (see RuleExtractionView.svelte / RuleExtractionService
for the one wired today: "rule_extraction").
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMTask:
    key: str
    """Stable, persisted discriminator (e.g. "rule_extraction")."""

    label: str
    description: str = ""


LLM_TASKS: list[LLMTask] = [
    LLMTask(
        key="rule_extraction",
        label="Rule Extraction",
        description="Drafting compliance rules from uploaded documents (Rule Extraction Studio).",
    ),
    LLMTask(
        key="document_qa",
        label="Digital Inspector Q&A",
        description="Natural-language Q&A over a project's analysis results.",
    ),
]
