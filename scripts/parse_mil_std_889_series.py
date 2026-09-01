"""Parse MIL-STD-889B Table II into a structured, ordered galvanic series.

Reads the Firecrawl-scraped Markdown in ``docs/scraped_standards/`` and emits a
JSON extract of Table II, *Galvanic series of selected metals in seawater*
(per Army Missile Command Report RS-TR-67-11).

Table II is an **ordinal** series: it ranks alloys from most active (anodic) to
most noble (cathodic) but publishes no electrode potentials. The extract
therefore carries ``rank`` only -- no ``potential_v`` is synthesised, because
the source does not contain one. See the module notes in
``app/services/corrosion_rule_catalog.py`` for why the GC-001 catalog cannot
consume a rank-only series directly.

Active and passive states are emitted as distinct material identifiers, e.g.
``stainless_steel_304_active`` and ``stainless_steel_304_passive``.

Usage::

    python scripts/parse_mil_std_889_series.py

Exit codes: ``0`` success, ``1`` source file missing or table not found.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SOURCE = REPO_ROOT / "docs" / "scraped_standards" / "corrosion_mil_std_889_galvanic.md"
OUTPUT = REPO_ROOT / "data" / "reference" / "mil_std_889b_table_ii.json"

TABLE_START = re.compile(r"^TABLE II\.\s*Galvanic series", re.IGNORECASE)
ACTIVE_SENTINEL = re.compile(r"^Active \(Anodic\)", re.IGNORECASE)
NOBLE_SENTINEL = re.compile(r"^Noble \(Less Active-Cathodic\)", re.IGNORECASE)

#: Scan/OCR furniture carried over from the PDF page breaks.
NOISE = (
    re.compile(r"^-{3,}$"),
    re.compile(r"^Supersedes page", re.IGNORECASE),
    re.compile(r"^MIL-STD-?\d*", re.IGNORECASE),
    re.compile(r"^\d{1,2} \w+ \d{4}$"),
    re.compile(r"^PER:", re.IGNORECASE),
    re.compile(r"^#"),
)

STATE = re.compile(r"\((active|passive)\)", re.IGNORECASE)


def _is_noise(line: str) -> bool:
    """Return True when a line is page furniture rather than a series entry."""
    return any(pattern.match(line) for pattern in NOISE)


def _material_key(name: str) -> str:
    """Derive a stable snake_case identifier, keeping active/passive distinct."""
    text = name.lower()
    text = text.replace("stainless steel", "stainless_steel")
    text = re.sub(r"[(),.%]", " ", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def extract_series(markdown: str) -> list[dict]:
    """Return Table II entries in published order, most anodic first."""
    lines = markdown.splitlines()

    start = next((i for i, line in enumerate(lines) if TABLE_START.match(line.strip())), None)
    if start is None:
        raise LookupError("TABLE II heading not found in source document")

    entries: list[dict] = []
    seen: dict[str, int] = {}
    started = False

    for raw in lines[start + 1 :]:
        line = raw.strip()
        if not line or _is_noise(line):
            continue
        if ACTIVE_SENTINEL.match(line):
            started = True
            continue
        if NOBLE_SENTINEL.match(line):
            break
        if not started:
            continue

        state_match = STATE.search(line)
        state = state_match.group(1).lower() if state_match else None
        key = _material_key(line)

        # The published table repeats a handful of alloys; keep both rows but
        # mark the later one so the duplication is visible downstream.
        duplicate_of = seen.get(key)
        seen.setdefault(key, len(entries) + 1)

        entries.append(
            {
                "rank": len(entries) + 1,
                "name": line,
                "material_key": key,
                "state": state,
                "duplicate_of_rank": duplicate_of,
            }
        )

    if not entries:
        raise LookupError("TABLE II located but no entries parsed")
    return entries


def main() -> int:
    """Parse Table II and write the JSON extract."""
    if not SOURCE.exists():
        print(f"error: source not found: {SOURCE}", file=sys.stderr)
        return 1

    try:
        entries = extract_series(SOURCE.read_text(encoding="utf-8"))
    except LookupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = {
        "source_standard": "MIL-STD-889B (USAF), Notices 1-3",
        "source_table": "TABLE II. Galvanic series of selected metals in seawater",
        "source_attribution": "Army Missile Command Report RS-TR-67-11, Practical Galvanic Series",
        "source_file": str(SOURCE.relative_to(REPO_ROOT)).replace("\\", "/"),
        "ordering": "index 0 = most active (anodic); last = most noble (cathodic)",
        "potentials_published": False,
        "potential_note": (
            "Table II is ordinal only. MIL-STD-889B section 30.4 states that standard "
            "electrode potentials are 'of little value in establishing galvanic corrosion "
            "relationships in actual environments'. No voltages are synthesised here."
        ),
        "entry_count": len(entries),
        "entries": entries,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    states = sum(1 for e in entries if e["state"])
    dupes = sum(1 for e in entries if e["duplicate_of_rank"])
    print(f"Parsed {len(entries)} entries -> {OUTPUT.relative_to(REPO_ROOT)}")
    print(f"  active/passive-qualified entries: {states}")
    print(f"  repeated entries flagged:         {dupes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
