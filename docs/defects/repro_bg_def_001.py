"""
Minimal reproduction for BG-DEF-001 — see defect_report_map_ordering.md.

Shows that ``RuleGenerator._enrich_target()`` resolves MEP element names to
architectural IFC classes, because it takes the first substring match over an
insertion-ordered map whose MEP keywords sit at the end.

Reads the map literals with ``ast`` rather than importing ``app.modules.config``,
which performs network I/O at import time and cannot run without credentials
(section 7 of the report). The resolution loop below is a line-for-line
transcription of the function under test.

Run from the repository root:

    uv run python docs/defects/repro_bg_def_001.py

Exits non-zero while the defect is present, so it doubles as a regression gate.
"""

import ast
import sys
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "app" / "modules" / "config.py"

#: (target string, the class it should resolve to). ``None`` means the target is
#: genuinely ambiguous and should be flagged for review rather than guessed.
CASES = [
    ("pipework in the pool plant room", "IfcPipeSegment"),
    ("plant room pipework", "IfcPipeSegment"),
    ("duct in the riser room", None),
    ("valve in the plant room", "IfcValve"),
    ("pump in the tank room", "IfcPump"),
    ("stainless steel pipework", "IfcPipeSegment"),
    ("stair riser", "IfcStairFlight"),
]


def load_maps() -> dict[str, list[tuple[str, str]]]:
    """Read the two enrichment maps out of config.py without importing it."""
    tree = ast.parse(CONFIG.read_text())
    wanted = {"CODE_TO_IFC_MAP", "IFC_PROPERTY_SET_MAP"}
    return {
        node.targets[0].id: [
            (ast.literal_eval(k), ast.literal_eval(v))
            for k, v in zip(node.value.keys, node.value.values)
        ]
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in wanted
        and isinstance(node.value, ast.Dict)
    }


def enrich_target(target: str, code_map: list[tuple[str, str]]) -> str:
    """Transcription of RuleGenerator._enrich_target(): first substring match wins."""
    if target.startswith("Ifc"):
        return target
    lowered = target.lower()
    for keyword, ifc_class in code_map:
        if keyword in lowered:
            return ifc_class
    return target


def main() -> int:
    """Print the resolution of every case and report how many are wrong."""
    maps = load_maps()
    code_map = maps["CODE_TO_IFC_MAP"]
    psets = dict(maps["IFC_PROPERTY_SET_MAP"])

    print(f"CODE_TO_IFC_MAP: {len(code_map)} entries, resolved in insertion order")
    keys = [k for k, _ in code_map]
    for kw in ("riser", "space", "room", "pipe", "duct"):
        index = keys.index(kw) if kw in keys else None
        print(f"  index of {kw!r:8} = {index}")
    print()

    failures = 0
    for target, expected in CASES:
        actual = enrich_target(target, code_map)
        ok = actual == expected if expected else False
        failures += 0 if ok else 1
        verdict = "ok  " if ok else "WRONG"
        want = expected or "ambiguous -> flag for review"
        print(f"  [{verdict}] {target!r:36} -> {actual!r:18} (want {want})")

    print()
    distribution = {
        c for _, c in code_map
        if any(w in c for w in ("Pipe", "Duct", "Valve", "Pump", "Flow"))
    }
    missing = sorted(c for c in distribution if c not in psets)
    print(f"Distribution-element classes without a property set: {missing or 'none'}")
    failures += len(missing)

    print()
    print(f"BG-DEF-001 present: {failures} failing check(s)" if failures else "BG-DEF-001 fixed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
