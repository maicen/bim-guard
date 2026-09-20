"""Measure how often real IFC models carry the properties BIMGuard grades, and compare with the grade.

The reliability grade (app/modules/rule_reliability.py) is a judgement from property *names*.
This script checks that judgement against evidence: for each element class and property it
counts how many elements in real models actually carry a non-empty value, turns that coverage
into an observed tier, and reports where the name-based grade and the observed tier disagree.

Read-only. It opens IFC files, and reads (never writes) the extracted rule drafts for the
"rules we actually extracted" section. Writes a report and its data under docs/validation/.

Usage:
    uv run python scripts/measure_property_coverage.py
    uv run python scripts/measure_property_coverage.py --models a.ifc b.ifc --classes IfcDoor IfcWindow
    uv run python scripts/measure_property_coverage.py --drafts-document 1163

The observed-tier thresholds are parameters, not product rules: they decide how the report
buckets coverage and are worth revisiting once more models are available.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Real-world models cached locally. The app's own synthetic test models (mock, golden, broken,
# multi-c-door, ...) are left out on purpose: they are built to carry the properties.
DEFAULT_MODEL_PATTERNS = (
    "Clinic_Architectural.ifc",
    "BUILDING_R4.ifc",
    "Pacific Continental Residence Sample IFC 2x3 Coordination View 2.0.ifc",
    "Pacific Continental Residence Sample IFC4.3 Reference View ARCH.ifc",
    "Building-Architecture.ifc",
)
DEFAULT_CLASSES = ("IfcDoor", "IfcWindow", "IfcWall", "IfcSlab", "IfcStair", "IfcRailing", "IfcBuildingStorey")

#: Direct IFC attributes measured on every class (missing on a schema -> counted as absent).
ATTRIBUTES = (
    "GlobalId", "Name", "Description", "ObjectType", "Tag", "PredefinedType",
    "OverallHeight", "OverallWidth", "OperationType",
)  # fmt: skip
#: BIMGuard's own relationship/geometry lookups; the pset is blank in extracted rules.
DERIVED = (
    "StoreyGlobalId", "StoreyName", "PlacementMatrix", "HostGlobalId", "HostIfcClass",
    "OpeningGlobalId", "OpeningIfcClass", "TypeGlobalId",
)  # fmt: skip

_ABSENT_STRINGS = {"", "NOTDEFINED"}


def is_present(value: Any) -> bool:
    """Return whether a value counts as carried: set, and not an IFC "not defined" placeholder."""
    if value is None:
        return False
    if isinstance(value, str) and value.strip().upper() in _ABSENT_STRINGS:
        return False
    if isinstance(value, (list, tuple)) and not value:
        return False
    return True


def _derived_values(element: Any, util: Any) -> dict[str, bool]:
    """Presence of BIMGuard's derived lookups for one element."""
    out = {name: False for name in DERIVED}
    try:
        storey = element if element.is_a("IfcBuildingStorey") else util.get_container(element, ifc_class="IfcBuildingStorey")
        out["StoreyGlobalId"] = bool(storey is not None and is_present(storey.GlobalId))
        out["StoreyName"] = bool(storey is not None and is_present(storey.Name))
    except Exception:  # noqa: BLE001 - one odd element must not stop the survey
        pass
    out["PlacementMatrix"] = getattr(element, "ObjectPlacement", None) is not None
    try:
        fills = getattr(element, "FillsVoids", None) or ()
        opening = fills[0].RelatingOpeningElement if fills else None
        out["OpeningGlobalId"] = opening is not None and is_present(opening.GlobalId)
        out["OpeningIfcClass"] = opening is not None
        voids = (getattr(opening, "VoidsElements", None) or ()) if opening is not None else ()
        host = voids[0].RelatingBuildingElement if voids else None
        out["HostGlobalId"] = host is not None and is_present(host.GlobalId)
        out["HostIfcClass"] = host is not None
    except Exception:  # noqa: BLE001
        pass
    try:
        type_ = util.get_type(element)
        out["TypeGlobalId"] = type_ is not None and is_present(type_.GlobalId)
    except Exception:  # noqa: BLE001
        pass
    return out


def survey_model(path: Path, classes: tuple[str, ...], max_elements: int) -> dict[str, Any]:
    """Count, per class, how many elements carry each attribute / derived lookup / property."""
    import ifcopenshell
    import ifcopenshell.util.element as util

    started = time.time()
    model = ifcopenshell.open(str(path))
    result: dict[str, Any] = {"schema": model.schema, "classes": {}}
    for ifc_class in classes:
        try:
            elements = model.by_type(ifc_class)
        except Exception:  # noqa: BLE001 - class not in this schema
            continue
        if not elements:
            continue
        total = len(elements)
        step = max(1, total // max_elements)
        sample = elements[::step][:max_elements]

        has: Counter = Counter()  # (group, property) -> elements carrying it
        any_pset: Counter = Counter()  # property name -> elements carrying it in *any* set
        for element in sample:
            has[("Attributes", "IfcClass")] += 1  # the entity type: present by definition
            for attr in ATTRIBUTES:
                if is_present(getattr(element, attr, None)):
                    has[("Attributes", attr)] += 1
            for name, present in _derived_values(element, util).items():
                if present:
                    has[("", name)] += 1
            try:
                psets = util.get_psets(element)
            except Exception:  # noqa: BLE001
                psets = {}
            seen_names: set[str] = set()
            for pset_name, props in psets.items():
                for prop, value in props.items():
                    if prop == "id" or not is_present(value):
                        continue
                    has[(pset_name, prop)] += 1
                    seen_names.add(prop)
            for prop in seen_names:
                any_pset[prop] += 1
        result["classes"][ifc_class] = {
            "elements": total,
            "sampled": len(sample),
            "has": {f"{g}␟{p}": n for (g, p), n in has.items()},
            "any_pset": dict(any_pset),
        }
    result["seconds"] = round(time.time() - started, 1)
    return result


def coverage_by_pair(surveys: dict[str, dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Fold per-model counts into per-(class, group, property) coverage statistics.

    Coverage is averaged over *every* model that contains the class, so a property carried in one
    model and missing from the others is scored as the low coverage it really has -- not 100%.
    """
    sampled_by_class: dict[str, list[tuple[str, int]]] = defaultdict(list)
    counts: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)
    for model_name, survey in surveys.items():
        for ifc_class, info in survey["classes"].items():
            sampled_by_class[ifc_class].append((model_name, info["sampled"]))
            for key, count in info["has"].items():
                group, prop = key.split("␟")
                counts[(ifc_class, group, prop)][model_name] = count

    stats: dict[tuple[str, str, str], dict[str, Any]] = {}
    for (ifc_class, group, prop), per_model in counts.items():
        models = sampled_by_class[ifc_class]
        coverages = [per_model.get(name, 0) / sampled for name, sampled in models if sampled]
        stats[(ifc_class, group, prop)] = {
            "models_with_class": len(models),
            "models_present": sum(1 for name, _ in models if per_model.get(name, 0) > 0),
            "mean_coverage": statistics.fmean(coverages) if coverages else 0.0,
            "min_coverage": min(coverages) if coverages else 0.0,
            "elements_with": sum(per_model.values()),
            "elements_sampled": sum(sampled for _, sampled in models),
        }
    return stats


def observed_tier(mean_coverage: float, high: float, medium: float) -> str:
    if mean_coverage >= high:
        return "high"
    if mean_coverage >= medium:
        return "medium"
    return "low"


def rule_pairs(document_id: Optional[int]) -> list[dict[str, str]]:
    """Return the (class, property set, property) each extracted draft checks (read-only)."""
    if document_id is None:
        return []
    from app.services.rule_draft_service import RuleDraftService

    pairs = []
    for row in RuleDraftService().list_drafts(document_id):
        rule = row.get("proposed_rule") or {}
        if rule.get("property_name"):
            pairs.append(
                {
                    "rule_id": rule.get("rule_id") or "",
                    "ifc_class": rule.get("target_ifc_class") or "IfcDoor",
                    "pset": rule.get("property_set") or "",
                    "prop": rule.get("property_name"),
                }
            )
    return sorted(pairs, key=lambda p: p["rule_id"])


def find_models(explicit: list[str], patterns: tuple[str, ...]) -> list[Path]:
    if explicit:
        return [Path(p) for p in explicit]
    found: dict[str, Path] = {}
    for pattern in patterns:
        for hit in (REPO_ROOT / "data").rglob(f"*{pattern}"):
            if "_improved" in hit.name or "enhancements" in hit.parts:
                continue
            found.setdefault(pattern, hit)
    return list(found.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="*", default=[], help="IFC files (default: the real-world models cached locally)")
    parser.add_argument("--classes", nargs="*", default=list(DEFAULT_CLASSES))
    parser.add_argument("--max-elements", type=int, default=1500, help="cap on elements sampled per class per model")
    parser.add_argument("--min-elements", type=int, default=10, help="ignore classes with fewer elements in total")
    parser.add_argument("--high", type=float, default=0.90, help="observed coverage at/above which a property is 'high'")
    parser.add_argument("--medium", type=float, default=0.50, help="observed coverage at/above which it is 'medium'")
    parser.add_argument("--drafts-document", type=int, default=1163, help="document whose extracted drafts to check (0 = skip)")
    parser.add_argument("--out", default=str(REPO_ROOT / "docs" / "validation" / "reliability-calibration.md"))
    args = parser.parse_args()

    from app.modules.rule_reliability import assess_property

    models = find_models(args.models, DEFAULT_MODEL_PATTERNS)
    if not models:
        print("No IFC models found.", file=sys.stderr)
        return 1

    surveys: dict[str, dict[str, Any]] = {}
    for path in models:
        print(f"surveying {path.name} ...", file=sys.stderr, flush=True)
        surveys[path.name] = survey_model(path, tuple(args.classes), args.max_elements)
        print(f"  done in {surveys[path.name]['seconds']}s", file=sys.stderr, flush=True)

    stats = coverage_by_pair(surveys)
    class_totals: Counter = Counter()
    for survey in surveys.values():
        for ifc_class, info in survey["classes"].items():
            class_totals[ifc_class] += info["elements"]
    usable_classes = {c for c, n in class_totals.items() if n >= args.min_elements}

    # -- every observed pair: predicted (from the name) vs observed (from the models) --------------
    confusion: Counter = Counter()
    rows: list[dict[str, Any]] = []
    for (ifc_class, group, prop), s in stats.items():
        if ifc_class not in usable_classes:
            continue
        predicted = assess_property(group, prop)
        if predicted is None:
            continue
        observed = observed_tier(s["mean_coverage"], args.high, args.medium)
        confusion[(predicted.level, observed)] += 1
        rows.append(
            {"class": ifc_class, "group": group or "(derived)", "property": prop,
             "predicted": predicted.level, "category": predicted.category, "observed": observed, **s}
        )  # fmt: skip

    # -- the rules actually extracted: absent properties count as 0% coverage ---------------------
    rule_rows: list[dict[str, Any]] = []
    for pair in rule_pairs(args.drafts_document or None):
        ifc_class, group, prop = pair["ifc_class"], pair["pset"], pair["prop"]
        s = stats.get((ifc_class, group, prop))
        if s is None and not group:
            s = stats.get((ifc_class, "Attributes", prop))  # a direct IFC attribute
        if s is None and not group:
            # No property set stated: carried if it appears in *any* set on the class.
            hits = [(info["any_pset"].get(prop, 0), info["sampled"]) for sv in surveys.values()
                    for c, info in sv["classes"].items() if c == ifc_class]  # fmt: skip
            covs = [h / n for h, n in hits if n]
            s = {"models_present": sum(1 for h, _ in hits if h), "mean_coverage": statistics.fmean(covs) if covs else 0.0}
        if s is None:
            s = {"models_present": 0, "mean_coverage": 0.0}
        predicted = assess_property(group, prop)
        # No elements of this class in any surveyed model: there is no evidence either way, which is
        # different from "present on 0% of elements".
        measurable = class_totals.get(ifc_class, 0) >= args.min_elements
        rule_rows.append(
            {**pair, "predicted": predicted.level if predicted else "n/a",
             "coverage": s["mean_coverage"] if measurable else None,
             "models_present": s["models_present"],
             "class_elements": class_totals.get(ifc_class, 0),
             "observed": observed_tier(s["mean_coverage"], args.high, args.medium) if measurable else "no data"}
        )  # fmt: skip

    payload = {
        "models": {name: {"schema": sv["schema"], "seconds": sv["seconds"], "classes": {
            c: {"elements": i["elements"], "sampled": i["sampled"]} for c, i in sv["classes"].items()}}
            for name, sv in surveys.items()},
        "thresholds": {"high": args.high, "medium": args.medium},
        "confusion": {f"{p}->{o}": n for (p, o), n in sorted(confusion.items())},
        "pairs": sorted(rows, key=lambda r: -r["elements_sampled"]),
        "extracted_rules": rule_rows,
    }
    data_path = REPO_ROOT / "docs" / "validation" / "data" / "reliability-calibration.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(render_report(payload, args), encoding="utf-8")
    print(f"report: {args.out}\ndata:   {data_path}", file=sys.stderr)
    return 0


def render_report(payload: dict[str, Any], args: argparse.Namespace) -> str:
    levels = ("high", "medium", "low")
    conf = payload["confusion"]
    total = sum(conf.values()) or 1
    exact = sum(n for k, n in conf.items() if k.split("->")[0] == k.split("->")[1])
    rank = {"low": 0, "medium": 1, "high": 2}
    over = sum(n for k, n in conf.items() if rank[k.split("->")[0]] > rank[k.split("->")[1]])
    under = sum(n for k, n in conf.items() if rank[k.split("->")[0]] < rank[k.split("->")[1]])

    lines = [
        "# Reliability calibration: grade from names vs coverage in real models",
        "",
        "Does the name-based reliability grade match how often real models actually carry the property?",
        f"Observed tier = mean per-model coverage: **high >= {args.high:.0%}**, **medium >= {args.medium:.0%}**, else **low**.",
        "These thresholds are report parameters, not product rules. Coverage = share of sampled elements",
        "carrying a non-empty value.",
        "",
        "## Models surveyed",
        "",
        "| Model | Schema | Classes (elements) | Seconds |",
        "|---|---|---|---|",
    ]
    for name, m in payload["models"].items():
        cls = ", ".join(f"{c} {i['elements']}" for c, i in m["classes"].items()) or "-"
        lines.append(f"| {name} | {m['schema']} | {cls} | {m['seconds']} |")

    lines += [
        "",
        "## Predicted (from the name) vs observed (from the models)",
        "",
        f"{total} distinct class/property pairs observed. Rows = predicted grade, columns = observed tier.",
        "",
        "| predicted \\ observed | high | medium | low |",
        "|---|---|---|---|",
    ]
    for p in levels:
        lines.append(f"| **{p}** | " + " | ".join(str(conf.get(f"{p}->{o}", 0)) for o in levels) + " |")
    lines += [
        "",
        f"- Exact agreement: **{exact}/{total} ({exact / total:.0%})**",
        f"- Over-confident (predicted higher than observed): **{over}** ({over / total:.0%})",
        f"- Under-confident (predicted lower than observed): **{under}** ({under / total:.0%})",
        "",
    ]

    if payload["extracted_rules"]:
        lines += [
            "## The rules that were actually extracted",
            "",
            "A property missing from every element of a class that *is* in the models counts as 0% coverage; a class that is not in the models has no evidence and is marked n/a.",
            "",
            "| Rule | Class | Property set / property | Predicted | Coverage | Models | Observed | Match |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in payload["extracted_rules"]:
            if r["observed"] == "no data":
                match, coverage = "n/a", f"no {r['ifc_class']} in the models"
            else:
                match = "yes" if r["predicted"] == r["observed"] else (
                    "over-confident" if rank.get(r["predicted"], 0) > rank[r["observed"]] else "under-confident")
                coverage = f"{r['coverage']:.0%}"
            lines.append(
                f"| {r['rule_id']} | {r['ifc_class']} | {r['pset'] or '-'} / {r['prop']} | {r['predicted']} | "
                f"{coverage} | {r['models_present']} | {r['observed']} | {match} |"
            )
        lines.append("")

    disagreements = [r for r in payload["pairs"] if r["predicted"] != r["observed"]][:25]
    if disagreements:
        lines += [
            "## Largest disagreements (by elements sampled)",
            "",
            "| Class | Set / property | Predicted | Observed | Mean coverage | Models | Basis |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in disagreements:
            lines.append(
                f"| {r['class']} | {r['group']} / {r['property']} | {r['predicted']} | {r['observed']} | "
                f"{r['mean_coverage']:.0%} | {r['models_present']} | {r['category']} |"
            )
        lines.append("")

    lines += [
        "## Limits",
        "",
        "- A handful of models, mostly Revit-exported samples: coverage reflects their authoring habits.",
        "- The two Pacific Continental Residence files are the same building in two IFC schemas, so they",
        "  are one independent model, not two.",
        "- Quantity and property-set names an extraction invented (e.g. `QtoWidth`) show as 0% because no",
        "  model can carry a property that does not exist; that is a finding about the extraction, not the models.",
        "- Elements are sampled (capped per class per model); classes with few elements are ignored.",
        "- Coverage measures *presence*, not correctness of the value.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
