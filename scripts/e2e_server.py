"""Boot the real API with model retrieval pointed at local IFC files.

WHY THIS EXISTS

    ``/api/analyze/upload`` stores the model through Supabase Storage, which a
    developer machine or CI runner without Supabase credentials cannot reach.
    That blocks the *upload*, not the analysis: everything downstream of "give
    me the bytes for project N" is the shipped code. This launcher patches that
    one boundary -- :func:`app.services.analysis_runner.model_bytes` -- and
    nothing else, so an end-to-end run over real IFC files stays honest about
    what it proves.

    ``--seed-db`` extends the same idea to the database. Rule packs served from
    ``static_data_assets`` (GC-001, CC-001, MC-001, BUILDING-CODE-PART9 and its
    extension) ship as rows of ``supabase/migrations/20260806180500_seed_static
    _data_assets.sql``, so an environment without Supabase starts with an empty
    table: the corrosion engines fall back to their built-in catalogs and the
    architectural analysis cannot run at all. With the flag,
    :mod:`scripts.e2e_static_seed` loads those rows through the shipped
    ``StaticDataService`` write path and registers one project row per mapped
    model, so both analyses run against database-resident rules. It proves the
    rule packs parse, seed and evaluate; it does not prove the Supabase network
    path. Without the flag the launcher behaves exactly as before.

USAGE

    BIMGUARD_E2E_MODELS='{"1": "path/to/model.ifc"}' uv run python
    scripts/e2e_server.py --port 8010 [--seed-db]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


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


def install_local_storage(mapping: dict[int, Path]) -> None:
    """Let ``materialize_local_path`` resolve a plain filesystem path.

    Project rows the E2E launcher registers carry an absolute path in
    ``ifc_file_path`` rather than an ``sb://`` reference, because there is no
    Supabase Storage to hold the bytes. This is the same boundary
    :func:`install_model_source` patches, reached by the second caller: the
    architectural pipeline resolves its own IFC through the project record
    instead of through ``model_bytes``.
    """
    from app.services.object_storage import ObjectStorage

    original = ObjectStorage.materialize_local_path
    known = {str(path.resolve()) for path in mapping.values()}

    def materialize_local_path(self, reference: str):
        if reference in known:
            return Path(reference)
        return original(self, reference)

    ObjectStorage.materialize_local_path = materialize_local_path


def register_projects(mapping: dict[int, Path]) -> int:
    """Insert one project row per mapped model, so project lookups resolve.

    Returns:
        The number of rows inserted.
    """
    from app.services.persistence import PersistenceService
    from app.utils import now_iso_utc

    projects = PersistenceService.get_table(
        "projects",
        {
            "id": int,
            "name": str,
            "description": str,
            "status": str,
            "country": str,
            "analysis_type": str,
            "ifc_file_path": str,
            "ifc_md5_hash": str,
            "created_at": str,
            "updated_at": str,
        },
        required_columns={"ifc_file_path": str, "ifc_md5_hash": str},
    )
    now = now_iso_utc()
    inserted = 0
    for project_id, path in sorted(mapping.items()):
        if not path.is_file():
            continue
        projects.insert(
            {
                "id": project_id,
                "name": path.stem,
                "description": "E2E fixture",
                "status": "active",
                "country": "CA",
                "analysis_type": "compliance",
                "ifc_file_path": str(path.resolve()),
                "ifc_md5_hash": "",
                "created_at": now,
                "updated_at": now,
            }
        )
        inserted += 1
    return inserted


def main() -> None:
    """Parse arguments, install the model source and run uvicorn."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Load the seed migration's rule packs and register project rows.",
    )
    parser.add_argument(
        "--seed-code-rulesets",
        action="store_true",
        help=(
            "Also seed BUILDING-CODE-PART9 and -EXT into the rules table. "
            "Startup seeding does not: app.main seeds seed_engine_rulesets and "
            "the four hardcoded architectural rules, and nothing calls "
            "seed_default_code_rulesets, so the 47-rule packs sit unused in "
            "static_data_assets. Implies --seed-db."
        ),
    )
    args = parser.parse_args()

    raw = os.getenv("BIMGUARD_E2E_MODELS", "{}")
    mapping = {int(k): Path(v) for k, v in json.loads(raw).items()}
    if args.seed_code_rulesets:
        args.seed_db = True
    if args.seed_db:
        # Before importing app.main: its startup seeding reads these assets.
        from e2e_static_seed import install_static_assets

        install_static_assets()
        install_local_storage(mapping)
        print(f"[e2e-db] registered {register_projects(mapping)} project rows")

    install_model_source(mapping)
    for project_id, path in sorted(mapping.items()):
        print(f"[e2e] project {project_id} -> {path} ({path.stat().st_size if path.is_file() else 'MISSING'} bytes)")

    import uvicorn

    from app.main import app

    if args.seed_code_rulesets:
        from app.services.rules_service import RuleService
        from app.services.ruleset_seeder import seed_default_code_rulesets

        service = RuleService()
        print(f"[e2e-db] code rulesets seeded: {seed_default_code_rulesets(service)}")
        print(f"[e2e-db] rules table now holds {service.count()} rules")

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
