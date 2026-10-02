"""ADK-powered Evaluator-Optimizer loop for rule extraction (rule_builder/adk_rule_generator.py).

Replaces the single-shot LlamaIndex approach with an iterative
Writer -> Critic -> Refiner workflow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.adk.tools import ToolContext
from google.genai.types import Content, Part

from app.logging_config import get_logger
from app.modules.config import DEFAULT_LLM_MODEL
from app.modules.contracts import (
    DeonticStatement,
    DocumentNodeContract,
    RuleExtractionDraft,
)
from app.modules.llm_providers.key_resolver import resolve_api_key
from app.modules.rule_builder._extraction_prompts import (
    RULE_PROMPT,
    SYSTEM_PROMPT,
    format_check_category_context,
    format_kg_context,
)

if TYPE_CHECKING:
    # Type-only: a runtime import cycles back through app.services -> rule_extraction_service.
    from app.services.clause_grounding_index import ClauseGroundingIndex

logger = get_logger(__name__)


def _build_adk_model(model: str | None, *, organization_id: int | None):
    """Resolve the model argument for an ADK LlmAgent, mirroring build_llm's provider/key logic.

    A bare Gemini model name routes to ADK's native Gemini integration; any
    other provider (e.g. "openrouter/...") needs the LiteLlm wrapper plus the
    org/env-resolved API key -- ADK's LlmAgent has no provider-routing of its
    own the way LlamaIndex's LiteLLM binding does.
    """
    resolved_model = model or DEFAULT_LLM_MODEL
    if "/" not in resolved_model:
        return resolved_model
    provider = resolved_model.split("/", 1)[0]
    api_key = resolve_api_key(provider, organization_id)
    return LiteLlm(model=resolved_model, api_key=api_key)


def exit_loop(tool_context: ToolContext) -> dict:
    """Call this function ONLY when the rules are perfect and no further changes are needed."""
    logger.info("Rule refinement complete; exiting loop.")
    tool_context.actions.escalate = True
    return {}


class AdkRuleGenerator:
    """Generates Pydantic-validated rule drafts using an ADK Evaluator-Optimizer loop."""

    async def generate_drafts_from_node(
        self,
        node: DocumentNodeContract,
        *,
        deontic: DeonticStatement | None = None,
        model: str | None = None,
        organization_id: int | None = None,
        clause_grounding: ClauseGroundingIndex | None = None,
        check_categories: list[dict] | None = None,
    ) -> list[RuleExtractionDraft]:
        from app.modules.rule_builder.llamaindex_rule_generator import (
            _candidate_to_draft,
            _LLMRuleExtractionResult,
        )

        adk_model = _build_adk_model(model, organization_id=organization_id)

        # 1. Prepare formatting context
        clause_id = node.metadata.clause_id if node.metadata else None
        class_candidates = []
        if clause_grounding:
            class_candidates = clause_grounding.class_candidates_for(clause_id)
            kg_context = format_kg_context(
                class_candidates=class_candidates,
                property_hints=clause_grounding.property_hints_for(clause_id),
                dependencies=clause_grounding.dependencies_for(clause_id),
            )
        else:
            kg_context = ""

        cat_context = format_check_category_context(
            categories=check_categories or [],
            section_heading=node.metadata.parent_section if node.metadata else None,
        )

        formatted_rule_prompt = RULE_PROMPT.format(
            kg_context=kg_context,
            check_category_context=cat_context,
            clause_text=node.text,
        )

        # 2. Define the ADK Agents
        initial_writer = LlmAgent(
            name="InitialRuleWriter",
            model=adk_model,
            instruction=SYSTEM_PROMPT + "\n\n" + formatted_rule_prompt,
            output_schema=_LLMRuleExtractionResult,
            output_key="current_rules",
        )

        critic = LlmAgent(
            name="RuleCritic",
            model=adk_model,
            instruction=f"""
You are a strict compliance rule critic. Review the extracted rules against the original text.

Original Clause Text:
{node.text}

Extracted Rules (from state):
{{current_rules}}

Review Criteria:
1. Target IFC class (target_ifc_class) must be a valid IFC entity (e.g., IfcDoor, IfcSpace) and populated.
2. Property name must be a standard IFC property if possible (e.g., FireRating, IsExternal).
3. The rule must accurately reflect the clause's requirement without hallucinating thresholds.
4. Applicability conditions (rase_applicability) must use min/max bounds for tiered ranges.

If ALL criteria are met and the rules are completely correct, output EXACTLY the phrase: "Rules are perfect."
If there are issues, list them clearly so the refiner can fix them. Do NOT output JSON.
""",
            output_key="criticism",
        )

        refiner = LlmAgent(
            name="RuleRefiner",
            model=adk_model,
            instruction=f"""
You are a compliance rule refiner. You must refine the current rules based on the critic's feedback.

Original Clause Text:
{node.text}

Current Rules (from state):
{{current_rules}}

Criticism (from state):
{{criticism}}

Task:
If the Criticism is exactly "Rules are perfect.", you MUST call the `exit_loop` tool immediately. Do not output rules.
Otherwise, apply the requested fixes to the Current Rules and output the corrected rules as structured JSON.
""",
            tools=[exit_loop],
            output_schema=_LLMRuleExtractionResult,
            output_key="current_rules",
        )

        loop = LoopAgent(
            name="RefinementLoop",
            sub_agents=[critic, refiner],
            max_iterations=2,
        )

        workflow = SequentialAgent(name="RuleExtractionWorkflow", sub_agents=[initial_writer, loop])

        # 3. Run the workflow
        runner = InMemoryRunner(workflow)
        session_id = f"extract_{node.node_id}"

        # The runner only executes against an existing session; its state is
        # where each agent's output_key result lands.
        await runner.session_service.create_session(
            app_name=runner.app_name, user_id="system", session_id=session_id
        )

        msg = Content(role="user", parts=[Part(text="Start extraction")])

        # Execute the workflow stream. A genuine failure (bad API key, model
        # unavailable, ...) propagates instead of being swallowed into an
        # empty list here -- RuleExtractionService.extract_rule_drafts
        # counts these per-node exceptions to tell "the model failed on
        # every clause" apart from "the model legitimately found nothing".
        async for _event in runner.run_async(
            user_id="system", session_id=session_id, new_message=msg
        ):
            pass

        session = await runner.session_service.get_session(
            app_name=runner.app_name, user_id="system", session_id=session_id
        )
        final_rules_obj = session.state.get("current_rules") if session else None

        if not final_rules_obj:
            return []

        # Parse output if it's a dict
        if isinstance(final_rules_obj, dict):
            try:
                final_rules_obj = _LLMRuleExtractionResult.model_validate(final_rules_obj)
            except Exception:
                pass

        if not isinstance(final_rules_obj, _LLMRuleExtractionResult):
            logger.warning("Final output was not a valid _LLMRuleExtractionResult")
            return []

        # 4. Map back to drafts
        drafts = []
        for candidate in final_rules_obj.rules:
            draft = _candidate_to_draft(
                candidate,
                node,
                deontic=deontic,
                class_candidates=class_candidates,
                check_categories=check_categories,
            )
            if draft:
                drafts.append(draft)

        return drafts
