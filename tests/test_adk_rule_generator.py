"""AdkRuleGenerator keeps the extracted rules through the critic/refiner loop.

Drives the real ADK workflow with a scripted model so the regression is
exercised end to end: when the critic accepted the rules, the refiner's exit
used to overwrite them with prose, and every clause returned no drafts.
"""

import asyncio
import json

import pytest
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai.types import Content, FunctionCall, Part

from app.modules.contracts import ClauseMetadata, DocumentNodeContract
from app.modules.rule_builder import adk_rule_generator
from app.modules.rule_builder.adk_rule_generator import AdkRuleGenerator

pytestmark = pytest.mark.rules

_RULES_JSON = json.dumps(
    {
        "rules": [
            {
                "rule_id": "DOOR-1",
                "description": "Exit doors shall be at least 850 mm wide",
                "target_ifc_class": "IfcDoor",
                "property_name": "OverallWidth",
                "operator": ">=",
                "check_value": "850",
                "unit": "mm",
            }
        ]
    }
)


class _ScriptedLlm(BaseLlm):
    """Answers each agent in the workflow, told apart by its instruction."""

    refiner_calls_exit_loop: bool = True

    async def generate_content_async(self, llm_request, stream=False):
        instruction = str(llm_request.config.system_instruction or "")
        if "strict compliance rule critic" in instruction:
            yield _text("Rules are perfect.")
        elif "compliance rule refiner" in instruction:
            last = llm_request.contents[-1] if llm_request.contents else None
            replied_to_tool = last is not None and any(p.function_response for p in last.parts or [])
            if self.refiner_calls_exit_loop and not replied_to_tool:
                yield LlmResponse(
                    content=Content(role="model", parts=[Part(function_call=FunctionCall(name="exit_loop", args={}))])
                )
            else:
                yield _text("The rules are perfect, so no changes are needed.")
        else:
            yield _text(f"Here are the rules:\n```json\n{_RULES_JSON}\n```")


def _text(text: str) -> LlmResponse:
    return LlmResponse(content=Content(role="model", parts=[Part(text=text)]))


def _node() -> DocumentNodeContract:
    return DocumentNodeContract(
        node_id="node-1",
        text="Exit doors shall have a clear width of at least 850 mm.",
        metadata=ClauseMetadata(node_type="paragraph", source_document_id=1),
    )


@pytest.mark.parametrize("refiner_calls_exit_loop", [True, False])
def test_accepted_rules_survive_the_refiner(monkeypatch, refiner_calls_exit_loop):
    llm = _ScriptedLlm(model="scripted", refiner_calls_exit_loop=refiner_calls_exit_loop)
    monkeypatch.setattr(adk_rule_generator, "_build_adk_model", lambda model, organization_id: llm)

    drafts = asyncio.run(AdkRuleGenerator().generate_drafts_from_node(_node()))

    assert [d.proposed_rule.rule_id for d in drafts] == ["DOOR-1"]
    assert drafts[0].proposed_rule.target_ifc_class == "IfcDoor"
