"""Boot the real API with model retrieval pointed at local IFC files.

WHY THIS EXISTS

    ``/api/analyze/upload`` stores the model through Supabase Storage, which a
    developer machine or CI runner without Supabase credentials cannot reach.
    That blocks the *upload*, not the analysis: everything downstream of "give
    me the bytes for project N" is the shipped code. This launcher patches that
    one boundary -- :func:`app.services.analysis_runner.model_bytes` -- and
    nothing else, so an end-to-end run over real IFC files stays honest about
    what it proves.

    What it does NOT stand in for: rule packs served from the ``static_data``
    tables (GC-001, CC-001, MC-001 and BUILDING-CODE-PART9). Those still need a
    database; without one the engines fall back to their built-in catalogs and
    the architectural ruleset is empty.

USAGE

    BIMGUARD_E2E_MODELS='{"1": "path/to/model.ifc"}' uv run python
    scripts/e2e_server.py --port 8010
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def install_model_source(mapping: dict[int, Path]) -> None:
    """Serve ``mapping``'s files as the models of the project ids that key them.

    Args:
        mapping: Project id to IFC path. A project id outside the mapping keeps
            the real lookup, so an unmapped project still reports the storage
            error it would report in production.
    """
    import app.services.analysis_runner as runner

    original = runner.model_bytes

    def model_bytes(project_id: int):
        path = mapping.get(int(project_id))
        if path is None:
            return original(project_id)
        if not path.is_file():
            return None, f"E2E model missing: {path}"
        return path.read_bytes(), None

    runner.model_bytes = model_bytes


def main() -> None:
    """Parse arguments, install the model source and run uvicorn."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()

    raw = os.getenv("BIMGUARD_E2E_MODELS", "{}")
    mapping = {int(k): Path(v) for k, v in json.loads(raw).items()}
    install_model_source(mapping)
    for project_id, path in sorted(mapping.items()):
        print(f"[e2e] project {project_id} -> {path} ({path.stat().st_size if path.is_file() else 'MISSING'} bytes)")

    import uvicorn

    from app.main import app

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
