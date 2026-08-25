"""Python OpenRouter agent loop contracts."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import app.agent.runner as runner_module
from app.agent.config import AgentConfig
from app.agent.runner import OpenRouterAgent
from app.agent.tools import execute_tool


class FakeMessage:
    """Small OpenAI-compatible response message used by the loop test."""

    def __init__(self, *, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self, exclude_none=True):
        result = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            result["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in self.tool_calls
            ]
        return result


def test_agent_executes_tool_then_returns_answer(monkeypatch, tmp_path):
    requests = []
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="datetime", arguments="{}"),
    )
    responses = [
        SimpleNamespace(
            choices=[SimpleNamespace(message=FakeMessage(tool_calls=[tool_call]))],
            _hidden_params={"response_cost": 0.01},
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(message=FakeMessage(content="Done"))],
            _hidden_params={"response_cost": 0.02},
        ),
    ]

    async def fake_completion(**kwargs):
        requests.append(kwargs)
        return responses.pop(0)

    monkeypatch.setattr(runner_module, "acompletion", fake_completion)
    config = AgentConfig(api_key="secret", session_dir=tmp_path, max_cost=1.0)
    agent = OpenRouterAgent(config)

    result = asyncio.run(agent.run("What time is it?"))

    assert result == "Done"
    assert len(requests) == 2
    assert requests[0]["model"] == "openrouter/auto"
    assert requests[0]["extra_headers"]["X-Title"] == "BIM Guard Agent"
    assert requests[0]["plugins"] == [{"id": "web", "max_results": 5}]
    assert requests[1]["messages"][-1]["role"] == "tool"
    assert agent.total_cost == 0.03
    records = [json.loads(line) for line in Path(agent.session.path).read_text().splitlines()]
    assert [record["event"] for record in records].count("tool") == 1
    assert "secret" not in Path(agent.session.path).read_text(encoding="utf-8")


def test_agent_stops_when_provider_cost_exceeds_limit(monkeypatch, tmp_path):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=FakeMessage(content="Too expensive"))],
        _hidden_params={"response_cost": 0.25},
    )

    async def fake_completion(**kwargs):
        return response

    monkeypatch.setattr(runner_module, "acompletion", fake_completion)
    agent = OpenRouterAgent(
        AgentConfig(api_key="secret", session_dir=tmp_path, max_cost=0.10)
    )

    try:
        asyncio.run(agent.run("Run"))
    except RuntimeError as exc:
        assert "cost limit exceeded" in str(exc)
    else:
        raise AssertionError("Expected the agent cost limit to stop execution")


def test_file_tools_reject_paths_outside_workspace():
    result = json.loads(execute_tool("file_read", {"path": "../outside.txt"}))

    assert "Path must stay inside the repository" in result["error"]