"""Graph state for the Digital Inspector agent."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class InspectorState(TypedDict):
    """State threaded through the Digital Inspector's LangGraph run.

    `messages` is the ReAct-style conversation LangGraph's prebuilt
    `create_react_agent` reads/writes (system + human query, tool calls,
    tool results, final AI answer); `project_id` is the only input the
    caller supplies.
    """

    project_id: int
    messages: Annotated[list, add_messages]
