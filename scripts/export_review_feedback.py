"""Export reviewed rule-extraction drafts for the evaluation repo.

Feeds the companion evaluation repo (maicen/bim-guard-evaluation). Every
accepted/edited/rejected draft in `rule_extraction_drafts` is a human
judgment on one LLM-extracted rule candidate -- exactly the kind of
human-corrected pair the evaluation repo's own docs describe using "as
benchmark test cases and few-shot exemplars ... to progressively increase
zero-shot extraction precision across model sweeps". Today that signal is
saved and never leaves this table; this script is the missing export step.

For an "edited" draft, `original_proposed_rule` (populated by
RuleDraftService.review_draft on first edit -- see that method) holds the
LLM's pre-edit guess, so the record below carries both what the model
produced and what the reviewer corrected it to. Accepted/rejected drafts
were never modified, so `proposed_rule` alone is both the LLM's output and
the record of the reviewer's judgment on it.

Usage:
    uv run python scripts/export_review_feedback.py
    uv run python scripts/export_review_feedback.py --output /tmp/feedback.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from supabase import Client, create_client

_REVIEWED_STATUSES = ("accepted", "edited", "rejected")

_DEFAULT_OUTPUT = Path("docs/validation/data/rule_review_feedback.json")


def _build_client() -> Client:
    """Create a Supabase client using server-side credentials."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url:
        raise ValueError("SUPABASE_URL is required.")
    if not key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) is required.")
    return create_client(url, key)


def _fetch_reviewed_drafts(client: Client) -> list[dict[str, Any]]:
    """Return every draft that has received a review decision."""
    response = (
        client.table("rule_extraction_drafts")
        .select("*")
        .in_("status", _REVIEWED_STATUSES)
        .order("id")
        .execute()
    )
    return response.data or []


def _fetch_document_filenames(client: Client, document_ids: set[int]) -> dict[int, str]:
    """Map document_id -> filename for the drafts being exported."""
    if not document_ids:
        return {}
    response = (
        client.table("documents").select("id,filename").in_("id", sorted(document_ids)).execute()
    )
    return {row["id"]: row.get("filename", "") for row in (response.data or [])}


def _to_feedback_record(row: dict[str, Any], filenames: dict[int, str]) -> dict[str, Any]:
    """Shape one draft row into an LLM-output-vs-human-correction record."""
    status = row.get("status")
    proposed_rule = row.get("proposed_rule") or {}
    original = row.get("original_proposed_rule")

    llm_proposed_rule = original if (status == "edited" and original) else proposed_rule
    reviewer_corrected_rule = proposed_rule if status == "edited" else None

    return {
        "draft_id": row.get("id"),
        "document_id": row.get("source_document_id"),
        "document_filename": filenames.get(row.get("source_document_id"), ""),
        "status": status,
        "extraction_method": row.get("extraction_method"),
        "confidence": row.get("confidence"),
        "clause": row.get("clause"),
        "source_snippet": row.get("source_snippet"),
        "llm_proposed_rule": llm_proposed_rule,
        "reviewer_corrected_rule": reviewer_corrected_rule,
        "reviewer_email": row.get("reviewer_email") or None,
        "review_notes": row.get("review_notes") or None,
        "created_at": row.get("created_at"),
        "reviewed_at": row.get("reviewed_at"),
    }


def export_review_feedback(output_path: Path) -> list[dict[str, Any]]:
    """Fetch reviewed drafts and write them as a JSON array to `output_path`."""
    client = _build_client()
    rows = _fetch_reviewed_drafts(client)
    filenames = _fetch_document_filenames(client, {r["source_document_id"] for r in rows})
    records = [_to_feedback_record(row, filenames) for row in rows]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    return records


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {_DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    records = export_review_feedback(args.output)

    by_status: dict[str, int] = {}
    for record in records:
        by_status[record["status"]] = by_status.get(record["status"], 0) + 1

    print(f"Exported {len(records)} reviewed drafts to {args.output}")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
