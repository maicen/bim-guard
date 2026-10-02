"""rule_builder/adk_rule_generator.py

ADK-powered Evaluator-Optimizer loop for rule extraction.
Replaces the single-shot LlamaIndex approach with an iterative
Writer -> Critic -> Refiner workflow.
"""

import json
from typing import Optional

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import ToolContext
from google.adk.events import Event
from google.genai.types import Content, Part

from app.logging_config import get_logger
from app.modules.contracts import (
    DeonticStatement,
    DocumentNodeContract,
    RuleExtractionDraft,
)
from app.modules.rule_builder._extraction_prompts import (
    RULE_PROMPT,
    SYSTEM_PROMPT,
    format_check_category_context,
)
from app.services.clause_grounding_index import ClauseGroundingIndex

logger = get_logger(__name__)

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
            _LLMRuleExtractionResult,
            _candidate_to_draft,
            _format_kg_context,
        )
        
        model_name = model or "gemini-2.5-flash"
        
        # 1. Prepare formatting context
        kg_context = ""
        class_candidates = []
        if clause_grounding:
            grounding_matches = await clause_grounding.search_candidates(
                clause_text=node.text,
                organization_id=organization_id,
            )
            kg_context = _format_kg_context(
                class_candidates=grounding_matches.class_candidates,
                property_candidates=grounding_matches.property_candidates,
            )
            class_candidates = grounding_matches.class_candidates

        cat_context = format_check_category_context(
            categories=check_categories or [],
            section_heading=node.metadata.section_heading,
        )

        formatted_rule_prompt = RULE_PROMPT.format(
            kg_context=kg_context,
            check_category_context=cat_context,
            clause_text=node.text,
        )

        # 2. Define the ADK Agents
        initial_writer = LlmAgent(
            name="InitialRuleWriter",
            model=model_name,
            instruction=SYSTEM_PROMPT + "\n\n" + formatted_rule_prompt,
            output_schema=_LLMRuleExtractionResult,
            output_key="current_rules",
        )

        critic = LlmAgent(
            name="RuleCritic",
            model=model_name,
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
            model=model_name,
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

        workflow = SequentialAgent(
            name="RuleExtractionWorkflow",
            sub_agents=[initial_writer, loop]
        )

        # 3. Run the workflow
        runner = InMemoryRunner(workflow)
        session_id = f"extract_{node.node_id}"
        
        # We need a valid session to avoid SessionNotFoundError in Runner
        try:
            from google.adk.types import Session
            session = Session(id=session_id)
            runner.session_service._sessions[session_id] = session
        except Exception:
            pass 

        msg = Content(role="user", parts=[Part(text="Start extraction")])
        
        final_rules_obj = None
        
        # Execute the workflow stream
        try:
            async for event in runner.run_async(user_id="system", session_id=session_id, new_message=msg):
                if hasattr(event, "state") and "current_rules" in event.state:
                    final_rules_obj = event.state["current_rules"]
        except Exception as e:
            logger.error("ADK workflow failed: %s", e)
            return []

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
