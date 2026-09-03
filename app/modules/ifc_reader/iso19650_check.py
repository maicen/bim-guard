"""
ifc_reader/iso19650_check.py
------------------------------------
Whole-model ISO 19650 information-management checks.

Distinct from the building-code/life-safety checks elsewhere in ifc_reader:
this file checks CDE governance (container naming, suitability/revision
codes, GUID traceability, CDE-state consistency, export provenance), not
physical building performance.

Reuses ISO19650Validator (document_parsing/iso_validator.py) for the
container-naming rules it already implements, and adds the whole-model
checks a single filename can't answer on its own: GlobalId uniqueness,
filename-vs-IfcProject.Name cross-reference, CDE-state/suitability-code
consistency, and export provenance (author/org/timestamp/schema).

Deliberately out of scope here (need data this function doesn't have):
revision-sequence-over-time and duplicate-filename-across-the-CDE both need
upload history that isn't tracked anywhere yet; real IDS-spec validation is
a separate, much larger feature (BIM-Guard's CDE gate currently takes
ids_check_passed as a caller-supplied flag, not a computed result).
"""

from __future__ import annotations

import logging

from app.modules.document_parsing.iso_validator import ISO19650Validator

logger = logging.getLogger("bimguard.iso19650")

try:
    import ifcopenshell  # noqa: F401  (import presence check only)

    _IFC_AVAILABLE = True
except ImportError:
    _IFC_AVAILABLE = False

# Suitability-code family expected for each CDE state, per the BS EN ISO
# 19650 UK National Annex convention: S-codes are used during WIP/Shared
# review, A/B/CR-codes only once a container is Authorized/Published. This
# is a consistency heuristic, not a strict standard mandate — flagged as a
# warning, not an error.
_SUITABILITY_PREFIX_BY_CDE_STATE = {
    "WIP": {"S"},
    "SHARED": {"S"},
    "PUBLISHED": {"A", "B", "C"},
    "ARCHIVED": {"A", "B", "C", "S"},
}


def _check_filename(val) -> dict:
    return {
        "check": "filename_format",
        "severity": "error",
        "passes": val.is_valid,
        "message": (
            "Filename follows ISO 19650 container naming convention"
            if val.is_valid
            else "; ".join(val.errors) or "Filename does not follow ISO 19650 naming"
        ),
        "details": val.to_dict(),
    }


def _check_suitability_revision(val) -> dict:
    suit = val.fields.get("suitability_code", "")
    rev = val.fields.get("revision_code", "")
    suit_ok = bool(suit) and ISO19650Validator.validate_suitability_code(suit)
    rev_ok = bool(rev) and ISO19650Validator.validate_revision_code(rev)
    passes = val.is_valid and suit_ok and rev_ok

    messages = []
    if not val.is_valid:
        messages.append("cannot evaluate - filename does not parse")
    else:
        if not suit_ok:
            messages.append(f"invalid suitability code '{suit}'")
        if not rev_ok:
            messages.append(f"invalid revision code format '{rev}'")

    return {
        "check": "suitability_revision_codes",
        "severity": "error",
        "passes": passes,
        "message": (
            "; ".join(messages) if messages
            else f"Suitability '{suit}' and revision '{rev}' are valid"
        ),
        "details": {"suitability_code": suit, "revision_code": rev},
    }


def _check_filename_vs_project_header(filename: str, ifc_file) -> dict | None:
    if not _IFC_AVAILABLE or ifc_file is None:
        return None
    try:
        projects = ifc_file.by_type("IfcProject")
        header_name = projects[0].Name if projects else None
    except Exception:
        header_name = None

    result = ISO19650Validator.cross_reference_header(filename, header_name)
    passes = len(result.warnings) == 0
    return {
        "check": "filename_vs_project_header",
        "severity": "warning",
        "passes": passes,
        "message": (
            "; ".join(result.warnings) if result.warnings
            else "Filename project code matches IfcProject.Name (or could not be compared)"
        ),
        "details": {"header_project_name": header_name},
    }


def _check_duplicate_guids(ifc_file) -> dict | None:
    if not _IFC_AVAILABLE or ifc_file is None:
        return None
    try:
        guids = [e.GlobalId for e in ifc_file if hasattr(e, "GlobalId") and e.GlobalId]
    except Exception:
        return None

    seen: dict[str, int] = {}
    for g in guids:
        seen[g] = seen.get(g, 0) + 1
    duplicates = {g: n for g, n in seen.items() if n > 1}

    return {
        "check": "duplicate_global_id",
        "severity": "critical",
        "passes": not duplicates,
        "message": (
            f"{len(duplicates)} GlobalId value(s) used by more than one element - "
            "breaks element-level traceability"
            if duplicates
            else f"All {len(guids)} GlobalIds are unique"
        ),
        "details": {
            "duplicate_count": len(duplicates),
            "duplicate_guids": list(duplicates)[:20],
            "total_guids": len(guids),
        },
    }


def _check_cde_state_consistency(suitability_code: str, cde_state: str) -> dict:
    code = (suitability_code or "").strip().upper()
    state = (cde_state or "WIP").strip().upper()
    prefix = code[:1]
    allowed_prefixes = _SUITABILITY_PREFIX_BY_CDE_STATE.get(state, {"S", "A", "B", "C"})
    # CR (client's/contractor's revision) is ambiguous by design — never flagged.
    passes = not code or code == "CR" or prefix in allowed_prefixes

    return {
        "check": "cde_state_vs_suitability",
        "severity": "warning",
        "passes": passes,
        "message": (
            f"Suitability code '{code}' is consistent with CDE state '{state}'"
            if passes
            else f"Suitability code '{code}' is not typically expected for CDE state '{state}'"
        ),
        "details": {"cde_state": state, "suitability_code": code},
    }


def _check_provenance_metadata(ifc_file) -> dict | None:
    if not _IFC_AVAILABLE or ifc_file is None:
        return None
    try:
        header = ifc_file.wrapped_data.header().file_name_py()
        names = header.get_attribute_names()
        info = {n: header.get_attribute_value(i) for i, n in enumerate(names)}
    except Exception:
        logger.warning("Could not read STEP header for provenance check", exc_info=True)
        info = {}

    missing = []
    if not info.get("time_stamp"):
        missing.append("export timestamp")
    if not any(str(a).strip() for a in (info.get("author") or ())):
        missing.append("author")
    if not any(str(o).strip() for o in (info.get("organization") or ())):
        missing.append("organization")
    if not info.get("originating_system"):
        missing.append("originating application")
    schema = getattr(ifc_file, "schema", None)
    if not schema:
        missing.append("IFC schema version")

    return {
        "check": "provenance_metadata",
        "severity": "warning",
        "passes": not missing,
        "message": (
            "Export provenance metadata present"
            if not missing
            else f"Missing provenance metadata: {', '.join(missing)}"
        ),
        "details": {**info, "schema": schema},
    }


def check_iso19650_compliance(
    ifc_file,
    *,
    filename: str = "",
    cde_state: str = "WIP",
    suitability_code: str = "",
) -> list[dict]:
    """Run all whole-model ISO 19650 checks; one result dict per check.

    Deliberately scoped to what a single loaded IFC file, its container
    filename, and its parent project record can answer — see module
    docstring for what's intentionally out of scope.
    """
    val = ISO19650Validator.validate_filename(filename)

    results: list[dict] = [
        _check_filename(val),
        _check_suitability_revision(val),
    ]

    header_check = _check_filename_vs_project_header(filename, ifc_file)
    if header_check:
        results.append(header_check)

    guid_check = _check_duplicate_guids(ifc_file)
    if guid_check:
        results.append(guid_check)

    results.append(_check_cde_state_consistency(suitability_code, cde_state))

    provenance_check = _check_provenance_metadata(ifc_file)
    if provenance_check:
        results.append(provenance_check)

    return results
