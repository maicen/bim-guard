"""Bounded OpenRouter agent loop built on LiteLLM."""

import json
from collections.abc import Callable

from litellm import acompletion

from app.agent.config import AgentConfig
from app.agent.session import AgentSession
from app.agent.tools import TOOL_SCHEMAS, execute_tool

SYSTEM_PROMPT = """You are the BIM Guard coding and compliance assistant.
Work only inside the current repository. Use tools proactively to inspect facts.
Keep edits targeted, validate changes, and continue until the task is resolved.
Never invent file contents or command results. Be concise in the final response."""

EventHandler = Callable[[str, dict], None]


class OpenRouterAgent:
    """Run an OpenRouter-backed conversation with local Python tools."""

    def __init__(self, config: AgentConfig) -> None:
        """Initialize a bounded agent conversation and its JSONL session."""
        self.config = config
        self.session = AgentSession(config.session_dir)
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.total_cost = 0.0

    def reset(self) -> None:
        """Start a fresh conversation and session log."""
        self.session = AgentSession(self.config.session_dir)
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.total_cost = 0.0

    async def run(self, prompt: str, on_event: EventHandler | None = None) -> str:
        """Run one user turn until the model answers or a limit is reached."""
        self.messages.append({"role": "user", "content": prompt})
        self.session.append("message", role="user", content=prompt)

        for step in range(1, self.config.max_steps + 1):
            request = {
                "model": self.config.model,
                "messages": list(self.messages),
                "tools": TOOL_SCHEMAS,
                "tool_choice": "auto",
                "api_key": self.config.api_key,
                "extra_headers": {
                    "HTTP-Referer": self.config.site_url,
                    "X-Title": self.config.app_name,
                },
            }
            if self.config.web_search:
                request["plugins"] = [{"id": "web", "max_results": 5}]
            response = await acompletion(
                **request,
            )
            self._record_cost(response)
            if self.total_cost > self.config.max_cost:
                raise RuntimeError(
                    f"Agent cost limit exceeded: ${self.total_cost:.4f} "
                    f"> ${self.config.max_cost:.4f}."
                )

            message = response.choices[0].message
            assistant = message.model_dump(exclude_none=True)
            self.messages.append(assistant)
            tool_calls = message.tool_calls or []

            if not tool_calls:
                content = message.content or ""
                self.session.append(
                    "message", role="assistant", content=content, step=step
                )
                return content

            for tool_call in tool_calls:
                name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                if on_event:
                    on_event("tool_call", {"name": name, "arguments": arguments})
                output = execute_tool(name, arguments)
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": output,
                    }
                )
                self.session.append(
                    "tool", name=name, arguments=arguments, output=output, step=step
                )
                if on_event:
                    on_event("tool_result", {"name": name, "output": output})

        raise RuntimeError(f"Agent step limit reached ({self.config.max_steps}).")

    def _record_cost(self, response) -> None:
        hidden = getattr(response, "_hidden_params", {}) or {}
        cost = hidden.get("response_cost") or 0.0
        self.total_cost += float(cost)
        self.session.append("usage", cost=cost, total_cost=self.total_cost)