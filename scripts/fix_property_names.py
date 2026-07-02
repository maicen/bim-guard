"""
scripts/fix_property_names.py
-------------------------------
One-time migration: renames property_name values in rules.db to match
the standard buildingSMART IFC Pset property names that Revit actually exports.

Before: rules used custom names (TreadDepth, ClearWidth, etc.) that never
        matched any real IFC property, causing permanent MISSING_DATA.
After:  rules use the standard names Revit exports automatically.

Usage:
    uv run python scripts/fix_property_names.py
    uv run python scripts/fix_property_names.py --dry-run
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.persistence import PersistenceService

RENAMES = [
    # (old_name,             new_name,          reason)
    ("TreadDepth",           "TreadLength",      "Pset_StairFlightCommon uses TreadLength"),
    ("HeadroomClearance",    "RequiredHeadroom", "Pset_StairFlightCommon uses RequiredHeadroom"),
    ("ClearWidth",           "OverallWidth",     "IfcDoor direct attribute is OverallWidth"),
    ("ClearOpeningHeight",   "OverallHeight",    "IfcWindow direct attribute is OverallHeight"),
    ("ClearOpeningWidth",    "OverallWidth",     "IfcWindow direct attribute is OverallWidth"),
    ("ClearOpeningArea",     "Area",             "Qto_WindowBaseQuantities uses Area"),
    ("Slope",                "RequiredSlope",    "Pset_RampCommon uses RequiredSlope"),
    ("MaxSlope",             "PitchAngle",       "Pset_SlabCommon uses PitchAngle"),
]


def run(dry_run: bool) -> None:
    db_path = Path(PersistenceService.DB_PATH)
    if not db_path.exists():
        print(f"DB not found at {db_path}")
        sys.exit(1)

    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        total = 0
        for old, new, reason in RENAMES:
            cur = conn.execute(
                "SELECT COUNT(*) FROM rules WHERE property_name = ?", (old,)
            )
            count = cur.fetchone()[0]
            if count == 0:
                print(f"  SKIP  {old!r:30} — no rows found")
                continue
            print(f"  {'DRY ' if dry_run else ''}UPDATE  {old!r:25} -> {new!r:20}  ({count} row(s))  [{reason}]")
            if not dry_run:
                conn.execute(
                    "UPDATE rules SET property_name = ?, updated_at = ? WHERE property_name = ?",
                    (new, now, old),
                )
            total += count

        if not dry_run:
            conn.commit()
            print(f"\nDone — {total} rule(s) updated in {db_path}")
        else:
            print(f"\nDry run — {total} rule(s) would be updated. Re-run without --dry-run to apply.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rename rule property_name values to match standard IFC Psets.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()
    run(args.dry_run)


if __name__ == "__main__":
    main()
