"""
ifc_quality/validator.py
-------------------------
Validates IFC files for labeling quality, GUID coverage, and property
coverage. Scores 0-100% on each metric and returns an overall score.

Usage:
    from app.modules.ifc_quality.validator import IFCValidator, validate_ifc_file

    results = validate_ifc_file("building.ifc")
    if results["overall"]["score"] >= 80:
        print("Ready for compliance checking")
"""

import json
from pathlib import Path
from typing import Dict

try:
    import ifcopenshell
    from ifcopenshell.util.element import get_psets

    _IFC_AVAILABLE = True
except ImportError:
    _IFC_AVAILABLE = False


# Classes get_psets reads properties/quantities from (ifcopenshell.util.element).
_PSET_OWNER_BASES = (
    "IfcObjectDefinition",
    "IfcMaterialDefinition",
    "IfcMaterial",  # IFC2X3, where it is not an IfcMaterialDefinition
    "IfcProfileDef",
)


class IFCValidator:
    """Validate and score an IFC file for compliance-checking readiness."""

    def __init__(self, filepath: str, ifc_file=None):
        """``ifc_file`` is an already-open model for *filepath*; passing it
        skips a second parse of the file (several seconds on large models)."""
        self.filepath = filepath
        self.ifc = ifc_file
        self.results: dict = {}
        self._scan_cache: dict | None = None

    def validate(self) -> Dict:
        if not _IFC_AVAILABLE:
            return {"valid": False, "error": "ifcopenshell not installed"}

        if self.ifc is None:
            try:
                self.ifc = ifcopenshell.open(self.filepath)
            except Exception as exc:
                return {"valid": False, "error": str(exc), "filepath": self.filepath}

        self._check_metadata()
        self._check_elements()
        self._check_labeling()
        self._check_guids()
        self._check_properties()
        self._calculate_score()
        return self.results

    # ── Checks ────────────────────────────────────────────────────────────────

    def _check_metadata(self):
        self.results["metadata"] = {
            "schema": self.ifc.schema,
            "file_path": self.filepath,
            "file_size_kb": Path(self.filepath).stat().st_size / 1024,
        }

    def _scan(self) -> dict:
        """Group the model by concrete type once, so per-entity Python work is
        limited to the classes that can matter.

        A multi-million-entity model is mostly geometry (points, polylines,
        placements) that has no Name, no GlobalId and no property sets. Those
        are only counted; the relevant entities are visited in id order, which
        is the order a plain walk of the model yields them in.
        """
        if self._scan_cache is not None:
            return self._scan_cache
        by_type: dict = {}
        relevant: list = []
        total = 0
        try:
            type_names = self.ifc.wrapped_data.types()
            for name in type_names:
                entities = self.ifc.by_type(name, include_subtypes=False)
                if not entities:
                    continue
                by_type[name] = len(entities)
                total += len(entities)
                probe = entities[0]
                if (
                    hasattr(probe, "Name")
                    or hasattr(probe, "GlobalId")
                    or any(probe.is_a(t) for t in _PSET_OWNER_BASES)
                ):
                    relevant.extend(entities)
        except Exception:
            by_type, relevant, total = {}, [], 0
            for el in self._iter_entities():
                by_type[el.is_a()] = by_type.get(el.is_a(), 0) + 1
                total += 1
            relevant = list(self._iter_entities())
        relevant.sort(key=lambda e: e.id())
        self._scan_cache = {"by_type": by_type, "relevant": relevant, "total": total}
        return self._scan_cache

    def _check_elements(self):
        scan = self._scan()
        self.results["elements"] = {"total": scan["total"], "by_type": scan["by_type"]}

    def _check_labeling(self):
        named = unnamed = 0
        samples: list = []
        for el in self._scan()["relevant"]:
            if hasattr(el, "Name"):
                if el.Name and str(el.Name).strip():
                    named += 1
                    if len(samples) < 5:
                        samples.append(f"{el.is_a()}: {el.Name}")
                else:
                    unnamed += 1
        total = named + unnamed
        score = (named / total * 100) if total else 0
        self.results["labeling"] = {
            "named": named,
            "unnamed": unnamed,
            "total": total,
            "score": score,
            "sample_names": samples,
        }

    def _check_guids(self):
        with_guid = 0
        samples: list = []
        for el in self._scan()["relevant"]:
            if hasattr(el, "GlobalId") and el.GlobalId:
                with_guid += 1
                if len(samples) < 3:
                    samples.append(
                        {
                            "type": el.is_a(),
                            "guid": str(el.GlobalId),
                            "name": getattr(el, "Name", "N/A"),
                        }
                    )
        total = self._scan()["total"]
        score = (with_guid / total * 100) if total else 0
        self.results["guids"] = {
            "with_guid": with_guid,
            "total": total,
            "score": score,
            "samples": samples,
        }

    def _check_properties(self):
        scan = self._scan()
        with_props = 0
        # Every entity outside `relevant` has no property sets by construction.
        without_props = scan["total"] - len(scan["relevant"])
        all_psets: set = set()
        samples: list = []
        for el in scan["relevant"]:
            # Only these classes can own property/quantity sets; for the rest
            # get_psets returns nothing.
            if not any(el.is_a(t) for t in _PSET_OWNER_BASES):
                without_props += 1
                continue
            try:
                psets = get_psets(el, psets_only=False)
                if psets:
                    with_props += 1
                    all_psets.update(psets.keys())
                    if len(samples) < 3 and hasattr(el, "Name"):
                        entry: dict = {
                            "element": f"{el.is_a()}: {getattr(el, 'Name', 'unnamed')}",
                            "psets": list(psets.keys()),
                            "sample_props": {},
                        }
                        for ps_name in list(psets.keys())[:2]:
                            entry["sample_props"][ps_name] = dict(list(psets[ps_name].items())[:3])
                        samples.append(entry)
                else:
                    without_props += 1
            except Exception:
                without_props += 1
        total = with_props + without_props
        score = (with_props / total * 100) if total else 0
        self.results["properties"] = {
            "with_properties": with_props,
            "without_properties": without_props,
            "total": total,
            "score": score,
            "property_set_types": list(all_psets),
            "samples": samples,
        }

    def _iter_entities(self) -> list:
        """Every entity, in a version-safe way across IfcOpenShell releases
        (fallback path only; ``_scan`` is the normal route)."""
        try:
            return list(self.ifc)
        except Exception:
            pass
        try:
            return list(self.ifc.by_type("IfcRoot"))
        except Exception:
            return []

    def _calculate_score(self):
        l = self.results.get("labeling", {}).get("score", 0)
        g = self.results.get("guids", {}).get("score", 0)
        p = self.results.get("properties", {}).get("score", 0)
        self.results["overall"] = {
            "score": (l + g + p) / 3,
            "labeling_weight": l,
            "guid_weight": g,
            "property_weight": p,
        }


def validate_ifc_file(filepath: str) -> Dict:
    return IFCValidator(filepath).validate()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python validator.py <file.ifc>")
        sys.exit(1)
    results = validate_ifc_file(sys.argv[1])
    json_out = sys.argv[1].replace(".ifc", "_validation_report.json")
    with open(json_out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Report saved: {json_out}")
