"""Invoke the Digital Inspector graph and report progress on the shared event bus.

Mirrors the ambient-tracking pattern in `app.services.pipeline_tracker`
(used by the compliance engines): binding a tracker for `project_id` and
calling `emit()` per tool call means the same `GET /api/events/{project_id}`
SSE channel used for engine runs also carries Digital Inspector tool-call
progress, rather than a second event system.
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.modules.contracts import InspectorResponse, InspectorToolCallContract
from app.services import pipeline_tracker

logger = get_logger(__name__)

_TRACKER_CODE = "DIGITAL-INSPECTOR"


async def run_inspection(project_id: int, query: str) -> InspectorResponse:
    """Run one Digital Inspector query and return the final answer + tool-call trace."""
    from langchain_core.messages import AIMessage

    from app.digital_inspector.graph import build_digital_inspector_graph

    graph = build_digital_inspector_graph()

    with pipeline_tracker.tracking(project_id):
        pipeline_tracker.emit(_TRACKER_CODE, query_chars=len(query))
        try:
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": query}]}
            )
        except Exception:
            pipeline_tracker.fail(_TRACKER_CODE, "graph invocation failed")
            raise

        messages = result.get("messages", [])
        tool_calls = _extract_tool_calls(messages)
        pipeline_tracker.complete(_TRACKER_CODE, tool_calls=len(tool_calls))

    answer = ""
    for message in reversed(messages):
        if isinstance(message, AIMessage) and (message.content or "").strip():
            answer = message.content
            break

    logger.info(
        "Digital Inspector run complete project_id=%d tool_calls=%d",
        project_id,
        len(tool_calls),
    )
    return InspectorResponse(project_id=project_id, answer=answer, tool_calls=tool_calls)


def _extract_tool_calls(messages: list) -> list[InspectorToolCallContract]:
    """Pair each AIMessage tool_call with its following ToolMessage result."""
    from langchain_core.messages import AIMessage, ToolMessage

    results_by_call_id: dict[str, str] = {
        message.tool_call_id: message.content
        for message in messages
        if isinstance(message, ToolMessage)
    }

    calls: list[InspectorToolCallContract] = []
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for call in message.tool_calls or []:
            call_id = call.get("id", "")
            output = results_by_call_id.get(call_id)
            calls.append(
                InspectorToolCallContract(
                    tool_name=call.get("name", ""),
                    input=call.get("args", {}),
                    output={"result": output} if output is not None else None,
                    status="success" if output is not None else "error",
                )
            )
    return calls
