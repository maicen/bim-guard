"""Configuration for the BIM Guard OpenRouter agent."""

import os
from dataclasses import dataclass
from pathlib import Path

from app.environment import load_env_file

load_env_file()


@dataclass(slots=True)
class AgentConfig:
    """Runtime limits and OpenRouter connection settings."""

    api_key: str
    model: str = "openrouter/auto"
    max_steps: int = 20
    max_cost: float = 1.0
    session_dir: Path = Path("data/agent-sessions")
    site_url: str = "http://127.0.0.1:8000"
    app_name: str = "BIM Guard Agent"
    web_search: bool = True

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Build agent configuration from the project environment."""
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required to run the agent.")
        return cls(
            api_key=api_key,
            model=os.environ.get("BIM_GUARD_AGENT_MODEL", "openrouter/auto"),
            max_steps=int(os.environ.get("BIM_GUARD_AGENT_MAX_STEPS", "20")),
            max_cost=float(os.environ.get("BIM_GUARD_AGENT_MAX_COST", "1.0")),
            session_dir=Path(
                os.environ.get("BIM_GUARD_AGENT_SESSION_DIR", "data/agent-sessions")
            ),
            site_url=os.environ.get(
                "OPENROUTER_SITE_URL", "http://127.0.0.1:8000"
            ),
            app_name=os.environ.get("OPENROUTER_APP_NAME", "BIM Guard Agent"),
            web_search=os.environ.get("BIM_GUARD_AGENT_WEB_SEARCH", "1") == "1",
        )