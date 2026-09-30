"""Bulk upload script for importing local IFC models into BIM-Guard.

Supports:
- Automatic in-memory compression to .ifcZIP (saving ~80% network & storage space)
- Multi-model discipline auto-detection (architectural, structural, mechanical, etc.)
- Smart auto-grouping by project prefix (e.g. West Riverside Hospital, B-CIT)
- Direct persistence via ModelsService / ProjectsService into Supabase Storage & PostgreSQL

Usage:
    uv run python scripts/bulk_upload_models.py --help
    uv run python scripts/bulk_upload_models.py --dir "/path/to/models" --dry-run
    uv run python scripts/bulk_upload_models.py --dir "/path/to/models" --auto-group
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.api.dependencies import get_models_service, get_projects_service  # noqa: E402
from app.logging_config import get_logger  # noqa: E402
from app.services.object_storage import ObjectStorage  # noqa: E402

logger = get_logger("bulk_upload_models")

# Discipline mapping heuristic from filename tokens
DISCIPLINE_HINTS: list[tuple[list[str], str, bool]] = [
    (["_arc_", "-arc-", "_arq_", "-arq-", "_architectural", "architecture"], "architectural", True),
    (["_str_", "-str-", "_structural", "structure"], "structural", False),
    (["_mech_", "-mech-", "_mechanical", "hvac"], "mechanical", False),
    (["_elec_", "-elec-", "_electrical"], "electrical", False),
    (["_plumb_", "-plumb-", "_plumbing", "sanitary", "sanitario"], "plumbing", False),
    (["_fire_", "-fire-"], "fire", False),
    (["_sprinkle_", "-sprinkle-", "_sprinkler"], "sprinkler", False),
]


def detect_discipline(filename: str) -> tuple[str, bool]:
    """Detect model discipline role and whether it should be default primary."""
    lower = filename.lower()
    for tokens, role, is_primary in DISCIPLINE_HINTS:
        if any(t in lower for t in tokens):
            return role, is_primary
    return "context", False


def compress_to_ifczip(ifc_path: Path) -> tuple[bytes, str, float]:
    """Compress an IFC file into .ifcZIP bytes, returning (bytes, new_filename, ratio)."""
    raw_bytes = ifc_path.read_bytes()
    raw_size = len(raw_bytes)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(ifc_path.name, raw_bytes)

    zip_bytes = buf.getvalue()
    zip_size = len(zip_bytes)
    ratio = (1.0 - (zip_size / raw_size)) * 100 if raw_size > 0 else 0.0

    zip_filename = ifc_path.stem + ".ifczip"
    return zip_bytes, zip_filename, ratio


def main():
    parser = argparse.ArgumentParser(description="Bulk upload IFC models to BIM-Guard")
    parser.add_argument("--dir", type=str, required=True, help="Directory containing IFC models")
    parser.add_argument("--project-id", type=int, help="Target existing project ID (optional)")
    parser.add_argument("--project-name", type=str, help="Create a new project with this name")
    parser.add_argument("--auto-group", action="store_true", help="Auto-group models into projects by name prefix (West Riverside Hospital, B-CIT)")
    parser.add_argument("--compress", action="store_true", default=True, help="Compress models to .ifcZIP before uploading (default: True)")
    parser.add_argument("--no-compress", action="store_false", dest="compress", help="Do not compress; upload raw .ifc")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and report without writing to DB/Storage")

    args = parser.parse_args()

    model_dir = Path(args.dir).expanduser().resolve()
    if not model_dir.is_dir():
        print(f"Error: Directory not found: {model_dir}")
        sys.exit(1)

    ifc_files = sorted([f for f in model_dir.glob("*") if f.is_file() and f.suffix.lower() in {".ifc", ".ifczip", ".zip"}])
    if not ifc_files:
        print(f"No IFC files found in {model_dir}")
        sys.exit(0)

    print(f"\n📦 Found {len(ifc_files)} IFC models in {model_dir}:")
    total_raw_bytes = 0
    total_upload_bytes = 0

    plans = []
    for f in ifc_files:
        raw_size = f.stat().st_size
        total_raw_bytes += raw_size
        role, is_prim = detect_discipline(f.name)

        if args.compress and f.suffix.lower() == ".ifc":
            est_zip_bytes, zip_name, ratio = compress_to_ifczip(f)
            upload_size = len(est_zip_bytes)
            upload_name = zip_name
            total_upload_bytes += upload_size
            plans.append({
                "file": f,
                "upload_name": upload_name,
                "content": est_zip_bytes,
                "role": role,
                "is_primary": is_prim,
                "raw_size": raw_size,
                "upload_size": upload_size,
                "ratio": ratio,
            })
            print(f"  • {f.name} -> {zip_name} [{role}] ({raw_size/1024/1024:.2f} MB -> {upload_size/1024/1024:.2f} MB, -{ratio:.1f}%)")
        else:
            upload_size = raw_size
            upload_name = f.name
            total_upload_bytes += upload_size
            plans.append({
                "file": f,
                "upload_name": upload_name,
                "content": f.read_bytes(),
                "role": role,
                "is_primary": is_prim,
                "raw_size": raw_size,
                "upload_size": upload_size,
                "ratio": 0.0,
            })
            print(f"  • {f.name} [{role}] ({raw_size/1024/1024:.2f} MB)")

    print(f"\nTotal payload: {total_raw_bytes/1024/1024:.2f} MB -> {total_upload_bytes/1024/1024:.2f} MB ({100*(1 - total_upload_bytes/total_raw_bytes):.1f}% reduction)")

    projects_service = get_projects_service()
    models_service = get_models_service()
    storage = ObjectStorage()

    # Organize plans into projects
    grouped_plans: dict[str, list[dict]] = defaultdict(list)
    if args.auto_group:
        for plan in plans:
            fname = plan["file"].name.lower()
            if "west_riverside_hospital" in fname:
                grouped_plans["West Riverside Hospital"].append(plan)
            elif "b-cit" in fname:
                grouped_plans["B-CIT Test Project"].append(plan)
            else:
                grouped_plans[args.project_name or "General Uploads"].append(plan)
    else:
        group_key = args.project_name or (f"Project #{args.project_id}" if args.project_id else "Bulk Upload Project")
        grouped_plans[group_key] = plans

    print("\n📋 Upload Grouping Plan:")
    for group_name, group_items in grouped_plans.items():
        print(f"  📁 {group_name} ({len(group_items)} models):")
        for item in group_items:
            prim_tag = " (Primary)" if item["is_primary"] else ""
            print(f"     - {item['upload_name']} [{item['role']}]{prim_tag}")

    if args.dry_run:
        print("\n[DRY RUN] No changes were made.")
        return

    # Execute upload per group
    for group_name, group_items in grouped_plans.items():
        project_id = None

        if group_name == "B-CIT Test Project":
            # Check if 3992 exists
            existing_p = projects_service.get_project(3992)
            if existing_p:
                project_id = 3992
                print(f"\nTargeting existing Project #{project_id} ('{existing_p.get('name')}')")

        if not project_id and args.project_id:
            project_id = args.project_id

        if not project_id:
            # Check if project with this name already exists
            all_projs = projects_service.list_projects()
            matched = next((p for p in all_projs if (p.get("name") or "").lower() == group_name.lower()), None)
            if matched:
                project_id = matched["id"]
                print(f"\nFound existing project #{project_id} ('{group_name}')")
            else:
                print(f"\nCreating project '{group_name}'...")
                new_project = projects_service.create_project(
                    name=group_name,
                    country="United States",
                    analysis_type="Arch",
                    project_type="COMMERCIAL",
                    description=f"Federated project with {len(group_items)} models",
                )
                project_id = new_project["id"]
                print(f"Created project ID: {project_id}")

        # Ensure at least one primary model if creating new or if project has no primary
        existing_models = models_service.list_models(project_id)
        has_primary = any(m.get("is_primary") for m in existing_models)
        if has_primary:
            # Keep existing primary; attach new ones as context
            for item in group_items:
                item["is_primary"] = False
        else:
            # If no primary exists, make sure the architectural or first one is primary
            has_group_prim = any(item["is_primary"] for item in group_items)
            if not has_group_prim and group_items:
                group_items[0]["is_primary"] = True

        existing_names = {m.get("file_name") for m in existing_models}

        print(f"\n🚀 Uploading {len(group_items)} models to Project #{project_id} ('{group_name}')...")
        for item in group_items:
            upload_name = item["upload_name"]
            content = item["content"]
            role = item["role"]
            is_prim = item["is_primary"]
            up_sz = item["upload_size"]

            if upload_name in existing_names or item["file"].name in existing_names:
                print(f"  ⏭  {upload_name} is already attached to Project #{project_id} (skipping)")
                continue

            print(f"  Uploading {upload_name} ({up_sz/1024/1024:.2f} MB)...", end=" ", flush=True)
            storage_ref = storage.save_upload(upload_name, content, f"projects/{project_id}/models")
            attached = models_service.attach_model(
                project_id=project_id,
                file_path=storage_ref,
                file_name=upload_name,
                role=role,
                is_primary=is_prim,
            )
            print(f"✓ Attached (ID: {attached.get('id')}, Primary: {is_prim})")

    print("\n🎉 All models successfully uploaded and attached to BIM-Guard!")


if __name__ == "__main__":
    main()
