"""Audit an IFC model against the BIMGUARD AI piping intake requirements.

Runs ``data/ids/bimguard_piping_intake.ids`` over a model with ifctester and
reports, per specification, how many piping elements are applicable and how
many carry the datum. It then translates those counts into one line per
corrosion engine, saying which elements the engine will return a verdict on and
which it will refuse as Undetermined.

This is a REPORT, NOT A GATE. The exit code is always 0: a model that fails
every optional specification is still a model worth auditing, and the point of
running this before upload is to know what the audit will be able to say, not
to be stopped at the door.

Nothing here touches the network or a server; the model is read locally.

Usage::

    python scripts/check_model_intake.py their_model.ifc
    python scripts/check_model_intake.py their_model.ifc --ids path/to/other.ids

See ``docs/reference/piping_intake_sources.md`` for the parser line behind
every requirement, and ``docs/reference/model_intake_requirements.md`` for the
one-page note to send with a model.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The intake IDS this script reports against by default.
DEFAULT_IDS = REPO_ROOT / "data" / "ids" / "bimguard_piping_intake.ids"

#: Specification names, as written in the IDS. Keyed by name rather than by
#: ``identifier`` because ifctester's IDS parser does not restore the
#: identifier attribute on read, even though it writes it.
SPEC_MATERIAL = "Material association"
SPEC_MATERIAL_PROPERTY = "Material stated as a property"
SPEC_SYSTEM = "System assignment"
SPEC_VELOCITY = "Flow velocity"
SPEC_TEMPERATURE = "Operating temperature"
SPEC_DEAD_LEG_LENGTH = "Dead-leg length"
SPEC_DEAD_LEG_FLAG = "Dead-leg flag"
SPEC_COUPLE = "Declared couple — second material at the junction"


def _entity_keys(entities: Iterable[Any]) -> set:
    """Return a hashable identity per entity, for set arithmetic across specs.

    ``GlobalId`` is the IFC identity of record; ``id()`` is the STEP line
    number, used only for an entity that somehow carries no GlobalId.
    """
    keys = set()
    for entity in entities or []:
        global_id = getattr(entity, "GlobalId", None)
        keys.add(str(global_id) if global_id else f"#{entity.id()}")
    return keys


def _percent(part: int, whole: int) -> str:
    """Format *part* of *whole* as a percentage, or ``n/a`` when whole is 0."""
    if not whole:
        return "n/a"
    return f"{100.0 * part / whole:.1f}%"


def audit(model_path: Path, ids_path: Path) -> tuple[Any, dict]:
    """Run the IDS audit and return ``(ids_document, results_by_spec_name)``.

    Args:
        model_path: The IFC file to read.
        ids_path: The IDS file to audit against.

    Returns:
        The validated :class:`ifctester.ids.Ids` and a dict keyed by
        specification name holding ``applicable``, ``passed``, ``failed`` counts
        and the set of passing entity keys.
    """
    import ifcopenshell
    from ifctester import ids as ids_module

    document = ids_module.open(str(ids_path), validate=False)
    model = ifcopenshell.open(str(model_path))
    document.validate(model)

    results: dict = {}
    for specification in document.specifications:
        applicable = list(specification.applicable_entities or [])
        passed = list(specification.passed_entities or [])
        failed = list(specification.failed_entities or [])
        results[specification.name] = {
            "usage": specification.get_usage(),
            "applicable": len(applicable),
            "passed": len(passed),
            "failed": len(failed),
            "passed_keys": _entity_keys(passed),
            "applicable_keys": _entity_keys(applicable),
        }
    return document, results


def print_specifications(results: dict) -> None:
    """Print one line per specification: applicable, pass, fail, pass %."""
    name_width = max((len(name) for name in results), default = 20)
    name_width = min(max(name_width, 20), 52)

    print("Per specification")
    print(
        f"  {'specification'.ljust(name_width)}  {'req?':<8} "
        f"{'applic':>7} {'pass':>7} {'fail':>7} {'pass %':>8}"
    )
    for name, row in results.items():
        label = name if len(name) <= name_width else name[: name_width - 1] + "…"
        print(
            f"  {label.ljust(name_width)}  {row['usage']:<8} "
            f"{row['applicable']:>7} {row['passed']:>7} {row['failed']:>7} "
            f"{_percent(row['passed'], row['applicable']):>8}"
        )


def print_engine_verdicts(results: dict) -> None:
    """Print one line per engine, in the audit's own tri-state vocabulary.

    The counts are what the engines will see, not simply what the IDS measured:
    a material resolves from the association OR from a Material/MaterialName
    property, and MC-001 runs when ANY ONE of velocity, dead leg or temperature
    is present. Both unions are computed here rather than read off a single
    specification.
    """
    material = results.get(SPEC_MATERIAL, {})
    total = material.get("applicable", 0)

    material_keys = material.get("passed_keys", set()) | results.get(
        SPEC_MATERIAL_PROPERTY, {}
    ).get("passed_keys", set())
    with_material = len(material_keys)
    without_material = total - with_material

    hydraulic_keys = set()
    for spec_name in (
        SPEC_VELOCITY,
        SPEC_TEMPERATURE,
        SPEC_DEAD_LEG_LENGTH,
        SPEC_DEAD_LEG_FLAG,
    ):
        hydraulic_keys |= results.get(spec_name, {}).get("passed_keys", set())
    with_hydraulics = len(hydraulic_keys)
    without_hydraulics = total - with_hydraulics

    temperature = results.get(SPEC_TEMPERATURE, {}).get("passed", 0)
    couple = results.get(SPEC_COUPLE, {}).get("passed", 0)
    system = results.get(SPEC_SYSTEM, {}).get("passed", 0)

    print()
    print("Per engine")
    print(
        f"  GC-001: {with_material} of {total} elements have a resolvable material "
        f"— expect verdicts on {with_material}, material_unresolved on "
        f"{without_material}; {couple} declare a second material, the rest score "
        f"as a self-couple"
    )
    print(
        f"  CC-001: {with_material} of {total} elements have a resolvable material "
        f"— expect verdicts on {with_material}, material_unresolved on "
        f"{without_material}"
    )
    print(
        f"  MC-001: {with_hydraulics} of {total} elements carry at least one of "
        f"flow velocity, dead-leg length or flag, or operating temperature "
        f"— expect verdicts on {with_hydraulics}, hydraulics_unavailable on "
        f"{without_hydraulics}"
    )
    print(
        f"  MM-001: {with_material} of {total} elements have a resolvable "
        f"material and {system} are assigned to a system (which supplies the "
        f"media axis); {temperature} state an operating temperature, the rest "
        f"fall back to a system design convention or raise temperature_missing"
    )
    print(
        f"  XM-001: {with_material} of {total} elements have a resolvable "
        f"material; adjacency is resolved from IFC ports or geometry and is not "
        f"expressible in IDS, so this line reports the material side only"
    )


def print_caveats() -> None:
    """State what the numbers above do and do not measure."""
    print()
    print("Read the numbers this way")
    print(
        "  - A failing OPTIONAL specification is information, not a rejection. "
        "The audit still runs; the affected engine returns Undetermined for "
        "those elements instead of a verdict."
    )
    print(
        "  - The material figure counts an IfcRelAssociatesMaterial association "
        "or a Material/MaterialName property. The audit can additionally infer "
        "a material from the piping system for some systems; that is a design "
        "convention, is tagged as such, and is not counted here."
    )
    print(
        "  - Environment class falls back to spatial names and then to a T1 "
        "indoor-damp default, so a 0% environment row does not mean the "
        "elements are unassessed — it means they are assessed at low confidence."
    )
    print(
        "  - Each property row checks ONE named property set, because an IDS "
        "property facet must name one. The audit itself reads the property name "
        "and ignores the set, so a 0% property row can be a false negative: the "
        "property may be present under a different set name and still be read."
    )
    print(
        "  - This script never contacts a server. Exit code is always 0."
    )


def main(argv: list[str] | None = None) -> int:
    """Run the audit and print the report. Always returns 0."""
    parser = argparse.ArgumentParser(
        description=(
            "Report how well an IFC model meets the BIMGUARD AI piping intake "
            "requirements. Always exits 0 — this is a report, not a gate."
        )
    )
    parser.add_argument("model", type=Path, help="path to the .ifc file to check")
    parser.add_argument(
        "--ids",
        type=Path,
        default=DEFAULT_IDS,
        help=f"IDS file to audit against (default: {DEFAULT_IDS.name})",
    )
    args = parser.parse_args(argv)

    if not args.model.exists():
        print(f"Model not found: {args.model}", file=sys.stderr)
        return 0
    if not args.ids.exists():
        print(f"IDS not found: {args.ids}", file=sys.stderr)
        return 0

    print(f"Model: {args.model}")
    print(f"IDS:   {args.ids}")
    print()

    try:
        document, results = audit(args.model, args.ids)
    except Exception as exc:  # noqa: BLE001 - a report must not raise at the caller
        print(f"Could not audit the model: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 0

    print(f"{document.info.get('title', 'IDS')} v{document.info.get('version', '?')}")
    print(f"{len(document.specifications)} specifications")
    print()
    print_specifications(results)
    print_engine_verdicts(results)
    print_caveats()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
