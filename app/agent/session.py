"""Append-only JSONL session persistence for the Python agent."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class AgentSession:
    """Persist agent events without storing provider credentials."""

    def __init__(self, directory: Path) -> None:
        """Create a new session log in *directory*."""
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.id = f"{timestamp}-{uuid4().hex[:8]}"
        self.path = directory / f"{self.id}.jsonl"

    def append(self, event: str, **payload) -> None:
        """Append one timestamped event to the session log."""
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, default=str) + "\n")