"""
module1_doc_parser/llamaindex_program.py
------------------------------------------
Shared LlamaIndex-backed typed-extraction helpers.

Centralizes the LlamaIndex ``LLMTextCompletionProgram`` wiring (LLM
instantiation, Pydantic output parsing) used by both deontic-statement
extraction (Module 1b) and structured rule generation (Module 3), so both
callers route through the same LLM configuration instead of each building
their own LlamaIndex LLM binding.

Uses ``llama_index.llms.litellm.LiteLLM`` — LlamaIndex's own LiteLLM
integration — configured from the same ``app.modules.config`` values as the
rest of the app's LLM calls (``DEFAULT_LLM_MODEL``, ``COMPLIANCE_TEMPERATURE``),
so no second API-key/model-routing surface is introduced alongside the
existing ``LiteLLMClient``.
"""

from typing import TypeVar

from pydantic import BaseModel

from app.logging_config import get_logger
from app.modules.contracts import ClauseMetadata, DeonticStatement

logger = get_logger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

_DEONTIC_PROMPT = """\
Identify the single normative ("shall"/"must"/"should"/"may") obligation
expressed by the following clause text, if any. If the text expresses no
such obligation, respond with modality "may" and an empty subject.

Extract:
- text: the obligation sentence, quoted or closely paraphrased
- modality: exactly one of "shall", "must", "should", "may"
- subject: the IFC entity or discipline the obligation applies to (e.g.
  "IfcStairFlight", "electrical contractor"), or null if unclear

CLAUSE TEXT:
{clause_text}
"""


def build_llm():
    """Construct the LlamaIndex LiteLLM binding from shared app config."""
    from llama_index.llms.litellm import LiteLLM

    from app.modules.config import COMPLIANCE_TEMPERATURE, DEFAULT_LLM_MODEL

    return LiteLLM(model=DEFAULT_LLM_MODEL, temperature=COMPLIANCE_TEMPERATURE)


class _DeonticExtractionResult(BaseModel):
    """Internal LLM output schema — modality/subject only; clause is attached after."""

    text: str
    modality: str
    subject: str | None = None


async def extract_deontic_statement(
    clause_text: str, *, clause: ClauseMetadata
) -> DeonticStatement | None:
    """Run a LlamaIndex Pydantic program to extract one deontic statement.

    Returns None when the LLM found no obligation in the text, or when its
    output fails to validate against the modality enum.
    """
    from llama_index.core.program import LLMTextCompletionProgram

    program = LLMTextCompletionProgram.from_defaults(
        output_cls=_DeonticExtractionResult,
        prompt_template_str=_DEONTIC_PROMPT,
        llm=build_llm(),
    )
    result: _DeonticExtractionResult = await program.acall(clause_text=clause_text)

    modality = (result.modality or "").strip().lower()
    if modality not in {"shall", "must", "should", "may"}:
        return None
    if not result.text or not result.text.strip():
        return None

    return DeonticStatement(
        text=result.text.strip(),
        modality=modality,  # type: ignore[arg-type]
        subject=(result.subject or "").strip() or None,
        clause=clause,
    )
