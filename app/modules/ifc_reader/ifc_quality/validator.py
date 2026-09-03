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


class IFCValidator:
    """Validate and score an IFC file for compliance-checking readiness."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.ifc = None
        self.results: dict = {}

    def validate(self) -> Dict:
        if not _IFC_AVAILABLE:
            return {"valid": False, "error": "ifcopenshell not installed"}

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

    def _check_elements(self):
        element_types: dict = {}
        total = 0
        for el in self._iter_entities():
            t = el.is_a()
            element_types[t] = element_types.get(t, 0) + 1
            total += 1
        self.results["elements"] = {"total": total, "by_type": element_types}

    def _check_labeling(self):
        named = unnamed = 0
        samples: list = []
        for el in self._iter_entities():
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
        entities = self._iter_entities()
        for el in entities:
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
        total = len(entities)
        score = (with_guid / total * 100) if total else 0
        self.results["guids"] = {
            "with_guid": with_guid,
            "total": total,
            "score": score,
            "samples": samples,
        }

    def _check_properties(self):
        with_props = without_props = 0
        all_psets: set = set()
        samples: list = []
        for el in self._iter_entities():
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
        """Return IFC entities in a version-safe way across IfcOpenShell releases."""
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
