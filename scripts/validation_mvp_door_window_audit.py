#!/usr/bin/env python
"""Score the MVP door and window rule packs on one IFC model against an
independent answer key, and draw the resulting confusion matrix.

Two things are compared for every (rule, element) pair:

* **BIM Guard's verdict** -- the rules run through the same two calls the
  architectural audit uses (``IFCReader.extract_for_compliance`` then
  ``ComplianceComparator.validate_metadata``), giving PASS / FAIL / MISSING.
* **The answer key** -- the same question answered by reading the raw IFC with
  ``ifcopenshell`` only, using none of BIM Guard's extraction code, giving
  COMPLIANT / VIOLATION / ABSENT (the value is not exported in the model).

The rules are the extraction drafts of the two MVP rule documents
(``BIMGuard_MVP_Structured_Door_Rules.pdf`` and
``BIMGuard_Window_MVP_20_Rules_Categorized.pdf``), read from
``rule_extraction_drafts`` and held in memory. Nothing is written to the
database. ``check_value`` / ``value_min`` / ``value_max`` are JSON-encoded the
way ``RuleService.create_rule`` stores them, so the engine sees what a promoted
rule row would hold.

A rule whose allowed-value set is an undefined ``TEST_*`` placeholder has no
answer (UNDEFINED) and is left out of the matrix; a rule that matched no
element is listed but contributes no pairs.

Usage::

    uv run python scripts/validation_mvp_door_window_audit.py --model path/to/model.ifc
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

warnings.filterwarnings("ignore")

import ifcopenshell  # noqa: E402
import ifcopenshell.util.element as ue  # noqa: E402
import ifcopenshell.util.unit as uu  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

#: (source document id, extraction run) for each MVP pack.
PACKS = {
    "doors": (1163, "EXTRACTED-20260920-044830"),
    "windows": (1362, "EXTRACTED-20261002-150802"),
}

VIOLATION, COMPLIANT, ABSENT, UNDEFINED = "VIOLATION", "COMPLIANT", "ABSENT", "UNDEFINED"
CLASSES = [VIOLATION, COMPLIANT, ABSENT]
PREDICTED = {"PASS": COMPLIANT, "FAIL": VIOLATION, "MISSING": ABSENT, "MISSING_DATA": ABSENT}
GUID_RE = re.compile(r"[0-3][0-9A-Za-z_$]{21}")


# ── BIM Guard side ────────────────────────────────────────────────────────────


def load_rules() -> list[dict]:
    """Return the MVP draft rules as in-memory rule rows (read-only)."""
    from app.modules.contracts import RuleCreateRequest
    from app.services.persistence import PersistenceService

    db = PersistenceService.get_db()
    rules: list[dict] = []
    for pack, (document_id, ruleset_id) in PACKS.items():
        drafts = (
            db.table("rule_extraction_drafts")
            .select("id,status,proposed_rule")
            .eq("source_document_id", document_id)
            .order("id")
            .execute()
            .data
        )
        for draft in drafts:
            proposed = draft["proposed_rule"]
            if isinstance(proposed, str):
                proposed = json.loads(proposed)
            if proposed.get("ruleset_id") != ruleset_id:
                continue
            rule = RuleCreateRequest.model_validate(proposed).model_dump()
            for key in ("check_value", "value_min", "value_max"):
                rule[key] = json.dumps(rule.get(key))
            rule["id"] = draft["id"]
            rule["reference"] = rule.get("reference") or rule.get("rule_id") or f"draft-{draft['id']}"
            rule["pack"] = pack
            rule["draft_status"] = draft["status"]
            rules.append(rule)
    return rules


def run_audit(model: Path, rules: list[dict]) -> list[dict]:
    """Run the rules through BIM Guard's extract-and-compare path."""
    from app.modules.comparator import ComplianceComparator
    from app.modules.ifc_reader import IFCReader

    reader = IFCReader(model)
    reader.load_ifc_file()
    return ComplianceComparator().validate_metadata(reader.extract_for_compliance(rules))


# ── Answer key: raw IFC only ──────────────────────────────────────────────────


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _pset(el, pset_name: str, prop: str):
    return (ue.get_psets(el).get(pset_name) or {}).get(prop)


def _authored(el, prop: str):
    """Value of a property by name in any pset on the occurrence or its type."""
    wanted = _norm(prop)
    for props in ue.get_psets(el).values():
        for key, value in props.items():
            if key != "id" and _norm(key) == wanted:
                return value
    return None


def _quantity(el, name: str):
    for props in ue.get_psets(el, qtos_only=True).values():
        if props.get(name) is not None:
            return props[name]
    return None


def _storey(el):
    container = ue.get_container(el)
    while container is not None and not container.is_a("IfcBuildingStorey"):
        container = ue.get_aggregate(container)
    return container


def _opening(el):
    rels = getattr(el, "FillsVoids", None) or ()
    return rels[0].RelatingOpeningElement if rels else None


def _host(el):
    opening = _opening(el)
    rels = (getattr(opening, "VoidsElements", None) or ()) if opening is not None else ()
    return rels[0].RelatingBuildingElement if rels else None


def _yes(condition: bool) -> str:
    return COMPLIANT if condition else VIOLATION


def _number(value, test: Callable[[float], bool]) -> str:
    """Compare an exported value; a text rating such as "REI 60" counts as 60."""
    if value is None:
        return ABSENT
    match = re.search(r"-?\d+(\.\d+)?", str(value))
    if not match:
        return UNDEFINED
    return _yes(test(float(match.group())))


def _true(value) -> str:
    return ABSENT if value is None else _yes(value is True)


def _type_relations(el) -> int:
    typed = [rel for rel in (getattr(el, "IsDefinedBy", ()) or ()) if rel.is_a("IfcRelDefinesByType")]
    return len(typed) + len(getattr(el, "IsTypedBy", ()) or ())


def build_answer_key(mm: float) -> dict[str, Callable[[Any], str]]:
    """Return rule reference -> function deciding one element from raw IFC.

    ``mm`` converts the model's length unit to millimetres. Each entry follows
    the rule's wording in its source document; "if exported" rules answer
    ABSENT, not VIOLATION, when the value is not in the model.
    """

    def dimension(attr: str, minimum: float):
        def check(el):
            value = getattr(el, attr, None)
            return ABSENT if value is None else _yes(value * mm >= minimum)

        return check

    def quantity(name: str, test: Callable[[float], bool]):
        return lambda el: ABSENT if _quantity(el, name) is None else _yes(test(_quantity(el, name)))

    def predefined(el):
        value = getattr(el, "PredefinedType", None)
        return ABSENT if not value else _yes(value != "NOTDEFINED")

    def is_external_boolean(el):
        value = _pset(el, "Pset_DoorCommon", "IsExternal")
        return ABSENT if value is None else _yes(isinstance(value, bool))

    def body_representation(el):
        rep = el.Representation
        return _yes(rep is not None and any(r.RepresentationIdentifier == "Body" for r in rep.Representations))

    def local_placement(el):
        placement = el.ObjectPlacement
        return _yes(
            placement is not None
            and placement.is_a("IfcLocalPlacement")
            and placement.RelativePlacement is not None
        )

    door = "Pset_DoorCommon"
    window = "Pset_WindowCommon"
    positive = lambda v: v > 0  # noqa: E731
    return {
        "DR-001": lambda el: _yes(bool(GUID_RE.fullmatch(el.GlobalId or ""))),
        "DR-002": lambda el: _yes(el.is_a("IfcDoor")),
        "DR-003": lambda el: _yes(bool((el.Name or "").strip())),
        "DR-004": lambda el: UNDEFINED if getattr(el, "PredefinedType", None) else ABSENT,
        "DR-005": lambda el: _yes(_storey(el) is not None),
        "DR-006": lambda el: _yes(bool((el.Name or "").strip())),
        "DR-007": lambda el: _yes(el.ObjectPlacement is not None),
        "DR-008": lambda el: _yes(_opening(el) is not None),
        "DR-009": lambda el: _yes(el.is_a("IfcOpeningElement")),
        "DR-010": lambda el: _yes(bool(getattr(el, "VoidsElements", None))),
        "DR-011": lambda el: UNDEFINED,
        "DR-012": dimension("OverallWidth", 800.0),
        "DR-013": dimension("OverallHeight", 2000.0),
        "DR-014": quantity("Width", positive),
        "DR-015": quantity("Height", positive),
        "DR-016": quantity("Perimeter", positive),
        "DR-017": quantity("Area", positive),
        "DR-018": body_representation,
        "DR-020": local_placement,
        "DR-021": lambda el: _yes(bool((el.Tag or "").strip())),
        "DR-022": lambda el: _yes(ue.get_type(el) is not None),
        "DR-024": lambda el: _number(_pset(el, door, "FireRating"), lambda v: v >= 45),
        "DR-025": is_external_boolean,
        "DR-026": lambda el: _number(_pset(el, door, "ThermalTransmittance"), lambda v: v <= 2.0),
        "DR-027": lambda el: _true(_pset(el, door, "HandicapAccessible")),
        "DR-028": lambda el: _true(_pset(el, door, "FireExit")),
        "DR-029": lambda el: _true(_pset(el, door, "SelfClosing")),
        "DR-030": lambda el: _true(_pset(el, door, "SmokeStop")),
        "WR-001": dimension("OverallWidth", 800.0),
        "WR-002": dimension("OverallHeight", 800.0),
        "WR-005": quantity("Area", lambda v: v >= 0.64),
        "WR-035": lambda el: _yes(_opening(el) is not None),
        "WR-036": lambda el: _yes(_host(el) is not None),
        "WR-039": lambda el: _yes(_storey(el) is not None),
        "WR-068": lambda el: _number(_pset(el, window, "FireRating"), lambda v: v >= 60),
        "WR-063": lambda el: _number(_pset(el, window, "ThermalTransmittance"), lambda v: v <= 1.8),
        "WR-059": lambda el: _number(_authored(el, "SolarHeatGainTransmittance"), lambda v: v <= 0.40),
        "WR-065": lambda el: _number(_pset(el, window, "Infiltration"), lambda v: v <= 0.30),
        "WR-007": lambda el: _number(_authored(el, "SillHeight"), lambda v: v <= 1000),
        "WR-012": lambda el: _number(_authored(el, "ClearOpeningWidth"), lambda v: v >= 500),
        "WR-013": lambda el: _number(_authored(el, "ClearOpeningHeight"), lambda v: v >= 600),
        "WR-014": lambda el: _number(_authored(el, "ClearOpeningArea"), lambda v: v >= 0.35),
        "WR-067": lambda el: _number(_pset(el, window, "AcousticRating"), lambda v: v >= 35),
        "WR-057": lambda el: _true(_authored(el, "IsSafetyGlass")),
        "WR-028": predefined,
        "WR-030": lambda el: _yes(ue.get_type(el) is not None),
        "WR-032": lambda el: _yes(_type_relations(el) == 1),
        "WR-023": lambda el: _yes(bool(GUID_RE.fullmatch(el.GlobalId or ""))),
    }


# ── Scoring ───────────────────────────────────────────────────────────────────


def _panel(pack: str, ifc_class: str) -> str:
    if pack == "windows":
        return "windows"
    return "doors" if ifc_class == "IfcDoor" else "door_pack_other"


def score(model: Path, rules: list[dict], results: list[dict]) -> dict:
    """Compare every BIM Guard verdict with the answer key."""
    ifc = ifcopenshell.open(str(model))
    answer_key = build_answer_key(uu.calculate_unit_scale(ifc) * 1000.0)
    by_reference = {rule["reference"]: rule for rule in rules}

    matrices: dict[str, Counter] = defaultdict(Counter)
    per_rule: list[dict] = []
    for result in results:
        reference = result["rule_ref"]
        rule = by_reference[reference]
        decide = answer_key.get(reference)
        cells: Counter = Counter()
        for entry in result.get("all_elements") or []:
            element = ifc.by_guid(entry["guid"])
            actual = decide(element) if decide else UNDEFINED
            predicted = PREDICTED.get(entry["status"], entry["status"])
            cells[(actual, predicted)] += 1
            if actual != UNDEFINED:
                matrices[_panel(rule["pack"], element.is_a())][(actual, predicted)] += 1
        per_rule.append(
            {
                "reference": reference,
                "pack": rule["pack"],
                "draft_status": rule["draft_status"],
                "target": result.get("target"),
                "property": result.get("property_name"),
                "operator": result.get("operator"),
                "check_value": json.loads(rule["check_value"]),
                "rule_status": result.get("status"),
                "elements": result.get("total_count", 0),
                "cells": {f"{actual}->{predicted}": n for (actual, predicted), n in sorted(cells.items())},
                "agrees": bool(cells) and all(a == p for a, p in cells),
            }
        )

    def summary(matrix: Counter) -> dict:
        total = sum(matrix.values())
        flagged = sum(n for (_, p), n in matrix.items() if p == VIOLATION)
        real = sum(n for (a, _), n in matrix.items() if a == VIOLATION)
        hit = matrix[(VIOLATION, VIOLATION)]
        return {
            "pairs": total,
            "matrix": {a: {p: matrix[(a, p)] for p in CLASSES} for a in CLASSES},
            "agreement": round(sum(matrix[(c, c)] for c in CLASSES) / total, 4) if total else None,
            "violations_in_model": real,
            "flagged_as_violation": flagged,
            "true_violations_flagged": hit,
            "false_violations_flagged": flagged - hit,
            "violations_missed": real - hit,
            "precision": round(hit / flagged, 4) if flagged else None,
            "recall": round(hit / real, 4) if real else None,
        }

    return {
        "model": model.name,
        "schema": ifc.schema,
        "element_counts": {c: len(ifc.by_type(c)) for c in ("IfcDoor", "IfcWindow", "IfcOpeningElement", "IfcBuildingStorey")},
        "rules": len(rules),
        "panels": {name: summary(matrix) for name, matrix in matrices.items()},
        "per_rule": per_rule,
    }


# ── Figure ────────────────────────────────────────────────────────────────────


def draw(report: dict, path: Path) -> None:
    """Draw one 3x3 matrix per panel; shade is the share of that actual row."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    titles = {
        "doors": "Door rules on doors",
        "door_pack_other": "Door-pack rules on openings and storeys",
        "windows": "Window rules on windows",
    }
    rows = ["Violation", "Compliant", "Not exported"]
    cols = ["Fail", "Pass", "Missing data"]
    panels = [name for name in titles if name in report["panels"]]
    ink, muted = "#1a1a1a", "#5f6368"

    fig, axes = plt.subplots(1, len(panels), figsize=(4.6 * len(panels), 5.0), squeeze=False)
    for ax, name in zip(axes[0], panels):
        panel = report["panels"][name]
        counts = [[panel["matrix"][a][p] for p in CLASSES] for a in CLASSES]
        shares = [[(n / sum(row) if sum(row) else 0.0) for n in row] for row in counts]
        ax.imshow(shares, cmap="Blues", vmin=0.0, vmax=1.0)
        for i, row in enumerate(counts):
            for j, n in enumerate(row):
                ax.text(j, i, f"{n:,}", ha="center", va="center", fontsize=15, fontweight="bold",
                        color="white" if shares[i][j] > 0.6 else ink)
        ax.set_xticks(range(3), cols, fontsize=10, color=ink)
        ax.set_yticks(range(3), rows if ax is axes[0][0] else [""] * 3, fontsize=10, color=ink)
        ax.xaxis.tick_top()
        ax.tick_params(length=0)
        ax.set_xticks([0.5, 1.5], minor=True)
        ax.set_yticks([0.5, 1.5], minor=True)
        ax.grid(which="minor", color="white", linewidth=2)
        ax.tick_params(which="minor", length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(f"{titles[name]}\n{panel['pairs']:,} rule-element checks", fontsize=11, color=ink, pad=26)
        ax.set_xlabel(f"Agreement {panel['agreement']:.0%}", fontsize=10, color=muted, labelpad=10)
    axes[0][0].set_ylabel("Actual (raw IFC)", fontsize=10, color=muted)
    fig.suptitle("BIM Guard verdict (columns) against the raw IFC model (rows)", fontsize=12, color=ink, y=0.98)
    fig.text(0.5, 0.02, "Shade = share of each row. MVP door and window rule packs, golden mock model.",
             ha="center", fontsize=9, color=muted)
    fig.tight_layout(rect=(0, 0.1, 1, 0.94))
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", required=True, type=Path, help="IFC model to audit")
    parser.add_argument("--json", type=Path, default=REPO_ROOT / "docs/validation/data/mvp-door-window-audit.json")
    parser.add_argument("--figure", type=Path, default=REPO_ROOT / "docs/validation/mvp-door-window-confusion-matrix.png")
    args = parser.parse_args()

    rules = load_rules()
    report = score(args.model, rules, run_audit(args.model, rules))
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    draw(report, args.figure)

    for name, panel in report["panels"].items():
        print(f"{name}: {panel['pairs']} checks, agreement {panel['agreement']:.1%}, "
              f"flagged {panel['flagged_as_violation']} (true {panel['true_violations_flagged']}, "
              f"false {panel['false_violations_flagged']}), missed {panel['violations_missed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
