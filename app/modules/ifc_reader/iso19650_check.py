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

Also covers model-content checks that a single IFC file genuinely can answer
on its own, beyond the container-naming/CDE-governance checks above:
element-level classification references, owner-history completeness,
georeferencing, unit-declaration completeness, spatial-structure hierarchy,
whether the file declares a Model View Definition (declaration only - see
_check_mvd_declared for why full MVD rule conformance is out of scope),
GlobalId well-formedness, spatial containment (orphaned elements), and
coverage checks for materials, quantities, documents, and property sets.

Deliberately NOT covered here, on purpose:
- "required attributes/Psets/property values present" - that's what the
  generic rule_compliance engine (Module4_Comparator) already does at
  scale via user-defined and seeded rules; duplicating it here as a
  hardcoded second implementation would just fight with the real one.
- Element dimensions, clearances, accessibility, clash detection - that's
  the building-code domain (egress/stairs/windows/accessibility), a
  different engine and a different concern from ISO 19650 governance.
- revision-sequence-over-time and duplicate-filename-across-the-CDE both
  need upload history that isn't tracked anywhere yet; real IDS-spec
  validation is a separate, much larger feature (BIM-Guard's CDE gate
  currently takes ids_check_passed as a caller-supplied flag, not a
  computed result); real clash detection and IFC-syntax/geometry validity
  checking are each their own substantial feature, not implemented here.
"""

from __future__ import annotations

import logging
import re

from app.modules.document_parsing.iso_validator import ISO19650Validator

try:
    import ifcopenshell.guid as _guid_util
    import ifcopenshell.util.classification as _classification_util
    import ifcopenshell.util.element as _element_util
except ImportError:  # pragma: no cover - covered by _IFC_AVAILABLE below
    _guid_util = None
    _classification_util = None
    _element_util = None

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


def _check_element_classification(ifc_file) -> dict | None:
    """Do any elements carry a classification reference (e.g. Uniclass 2015)?

    Expected under UK BIM Framework / ISO 19650 practice via
    IfcRelAssociatesClassification. Coverage is reported so a project that
    classifies only some elements still shows partial progress rather than
    a flat pass/fail.
    """
    if not _IFC_AVAILABLE or ifc_file is None or _classification_util is None:
        return None
    try:
        elements = ifc_file.by_type("IfcElement")
    except Exception:
        return None
    if not elements:
        return None

    classified = 0
    for element in elements:
        try:
            if _classification_util.get_references(element):
                classified += 1
        except Exception:
            continue

    total = len(elements)
    coverage = classified / total if total else 0.0
    passes = classified > 0

    return {
        "check": "element_classification",
        "severity": "warning",
        "passes": passes,
        "message": (
            f"{classified}/{total} elements ({coverage:.0%}) carry a classification reference"
            if passes
            else "No elements carry a classification reference (e.g. Uniclass 2015) - "
            "expected under ISO 19650 / UK BIM Framework practice"
        ),
        "details": {"classified_count": classified, "total_elements": total, "coverage": round(coverage, 4)},
    }


def _check_ownership_history(ifc_file) -> dict | None:
    """Does every declared IfcOwnerHistory carry an owning user and application?

    Authoring tools (Revit included) typically write ONE shared OwnerHistory
    for the whole export rather than one per element, so this checks every
    declared history record rather than trying to attribute per-element
    authorship the file was never given.
    """
    if not _IFC_AVAILABLE or ifc_file is None:
        return None
    try:
        histories = ifc_file.by_type("IfcOwnerHistory")
    except Exception:
        return None

    if not histories:
        return {
            "check": "ownership_history",
            "severity": "warning",
            "passes": False,
            "message": "No IfcOwnerHistory found in the model - element authorship cannot be traced",
            "details": {"history_count": 0},
        }

    missing_user = sum(1 for oh in histories if not getattr(oh, "OwningUser", None))
    missing_app = sum(1 for oh in histories if not getattr(oh, "OwningApplication", None))
    passes = missing_user == 0 and missing_app == 0

    return {
        "check": "ownership_history",
        "severity": "warning",
        "passes": passes,
        "message": (
            "All declared owner-history record(s) carry an owning user and application"
            if passes
            else f"{missing_user}/{len(histories)} owner-history record(s) missing OwningUser, "
            f"{missing_app}/{len(histories)} missing OwningApplication"
        ),
        "details": {
            "history_count": len(histories),
            "missing_owning_user": missing_user,
            "missing_owning_application": missing_app,
        },
    }


def _check_georeferencing(ifc_file) -> dict | None:
    """Is the model georeferenced, via either the IFC4 CRS entities or the
    older (still IFC4-legal, commonly Revit-exported) IfcSite lat/long?"""
    if not _IFC_AVAILABLE or ifc_file is None:
        return None
    try:
        has_crs = bool(ifc_file.by_type("IfcProjectedCRS")) or bool(ifc_file.by_type("IfcMapConversion"))
        sites = ifc_file.by_type("IfcSite")
    except Exception:
        return None

    has_site_lat_long = any(
        getattr(site, "RefLatitude", None) and getattr(site, "RefLongitude", None) for site in sites
    )
    passes = has_crs or has_site_lat_long
    method = "IfcProjectedCRS/IfcMapConversion" if has_crs else ("IfcSite RefLatitude/RefLongitude" if has_site_lat_long else "none")

    return {
        "check": "georeferencing",
        "severity": "warning",
        "passes": passes,
        "message": (
            f"Model is georeferenced via {method}"
            if passes
            else "No georeferencing found (no IfcProjectedCRS/IfcMapConversion, "
            "and no IfcSite RefLatitude/RefLongitude)"
        ),
        "details": {"method": method, "has_projected_crs": has_crs, "has_site_lat_long": has_site_lat_long},
    }


_REQUIRED_UNIT_TYPES = {"LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT"}


def _check_units_declaration(ifc_file) -> dict | None:
    """Are length, area, and volume units all declared on IfcUnitAssignment?"""
    if not _IFC_AVAILABLE or ifc_file is None:
        return None
    try:
        assignments = ifc_file.by_type("IfcUnitAssignment")
    except Exception:
        return None

    if not assignments:
        return {
            "check": "units_declaration",
            "severity": "error",
            "passes": False,
            "message": "No IfcUnitAssignment found - model has no declared units",
            "details": {"declared_unit_types": []},
        }

    declared: set[str] = set()
    for assignment in assignments:
        for unit in getattr(assignment, "Units", None) or []:
            unit_type = getattr(unit, "UnitType", None)
            if unit_type:
                declared.add(unit_type)

    missing = _REQUIRED_UNIT_TYPES - declared
    passes = not missing

    return {
        "check": "units_declaration",
        "severity": "error",
        "passes": passes,
        "message": (
            "Length, area, and volume units are all declared"
            if passes
            else f"Missing unit declaration(s): {', '.join(sorted(missing))}"
        ),
        "details": {"declared_unit_types": sorted(declared)},
    }


def _check_spatial_structure(ifc_file) -> dict | None:
    """Does the Project -> Site -> Building -> Storey hierarchy actually exist?

    Presence-only (at least one of each level) — not a check that every
    element decomposes correctly into it.
    """
    if not _IFC_AVAILABLE or ifc_file is None:
        return None
    try:
        levels = {
            "IfcProject": bool(ifc_file.by_type("IfcProject")),
            "IfcSite": bool(ifc_file.by_type("IfcSite")),
            "IfcBuilding": bool(ifc_file.by_type("IfcBuilding")),
            "IfcBuildingStorey": bool(ifc_file.by_type("IfcBuildingStorey")),
        }
    except Exception:
        return None

    missing = [name for name, present in levels.items() if not present]
    passes = not missing

    return {
        "check": "spatial_structure",
        "severity": "error",
        "passes": passes,
        "message": (
            "Project -> Site -> Building -> Storey spatial hierarchy is present"
            if passes
            else f"Missing spatial structure level(s): {', '.join(missing)}"
        ),
        "details": levels,
    }


def _check_mvd_declared(ifc_file) -> dict | None:
    """Does the STEP header declare a Model View Definition?

    Presence/declaration only — e.g. confirms the file says "ViewDefinition
    [CoordinationView_2.0]". It does NOT validate that the file's content
    actually conforms to that MVD's rules; real conformance checking needs a
    full express-schema/rule validator, a separate and much larger feature.
    """
    if not _IFC_AVAILABLE or ifc_file is None:
        return None
    try:
        header = ifc_file.wrapped_data.header().file_description_py()
        names = header.get_attribute_names()
        info = {n: header.get_attribute_value(i) for i, n in enumerate(names)}
    except Exception:
        return None

    descriptions = info.get("description") or ()
    mvd_text = next((d for d in descriptions if "ViewDefinition" in str(d)), None)
    passes = bool(mvd_text)

    return {
        "check": "mvd_declared",
        "severity": "warning",
        "passes": passes,
        "message": (
            f"Declares a Model View Definition: {mvd_text}"
            if passes
            else "No ViewDefinition declared in the STEP header - cannot confirm which MVD "
            "(e.g. Coordination View 2.0) this file targets"
        ),
        "details": {"view_definition": mvd_text},
    }


_GUID_ALPHABET_RE = re.compile(r"^[0-9A-Za-z_$]{22}$")


def _check_guid_format(ifc_file) -> dict | None:
    """Is every GlobalId a well-formed 22-character IFC-compressed GUID?

    Distinct from duplicate_global_id above: this checks well-formedness
    (right alphabet/length, and actually decodes), not uniqueness. A
    malformed GUID breaks interoperability with any tool that round-trips
    it through ifcopenshell.guid.expand()/compress().
    """
    if not _IFC_AVAILABLE or ifc_file is None or _guid_util is None:
        return None
    try:
        elements = [e for e in ifc_file if hasattr(e, "GlobalId") and e.GlobalId]
    except Exception:
        return None
    if not elements:
        return None

    malformed = 0
    for element in elements:
        gid = element.GlobalId
        if not _GUID_ALPHABET_RE.match(gid):
            malformed += 1
            continue
        try:
            _guid_util.expand(gid)
        except Exception:
            malformed += 1

    total = len(elements)
    passes = malformed == 0

    return {
        "check": "guid_format",
        "severity": "critical",
        "passes": passes,
        "message": (
            f"All {total} GlobalIds are well-formed"
            if passes
            else f"{malformed}/{total} GlobalId(s) are not well-formed 22-character IFC GUIDs"
        ),
        "details": {"malformed_count": malformed, "total_guids": total},
    }


def _check_spatial_containment(ifc_file) -> dict | None:
    """What fraction of elements are contained in NO spatial structure at all?

    An orphaned element (no storey/space container, direct or via
    decomposition) is invisible to storey-scoped reporting and most
    building-code checks, even though it's still in the model.
    """
    if not _IFC_AVAILABLE or ifc_file is None or _element_util is None:
        return None
    try:
        elements = ifc_file.by_type("IfcElement")
    except Exception:
        return None
    if not elements:
        return None

    orphaned = 0
    for element in elements:
        try:
            if _element_util.get_container(element) is None:
                orphaned += 1
        except Exception:
            orphaned += 1

    total = len(elements)
    passes = orphaned == 0

    return {
        "check": "spatial_containment",
        "severity": "warning",
        "passes": passes,
        "message": (
            f"All {total} elements are contained in the spatial structure"
            if passes
            else f"{orphaned}/{total} element(s) have no spatial container (storey/space) at all"
        ),
        "details": {"orphaned_count": orphaned, "total_elements": total},
    }


def _coverage_check(ifc_file, *, check_name: str, label: str, has_feature) -> dict | None:
    """Shared shape for the material/quantity/document/pset coverage checks
    below: what fraction of IfcElements satisfy `has_feature(element)`."""
    if not _IFC_AVAILABLE or ifc_file is None:
        return None
    try:
        elements = ifc_file.by_type("IfcElement")
    except Exception:
        return None
    if not elements:
        return None

    covered = 0
    for element in elements:
        try:
            if has_feature(element):
                covered += 1
        except Exception:
            continue

    total = len(elements)
    coverage = covered / total if total else 0.0
    passes = covered > 0

    return {
        "check": check_name,
        "severity": "warning",
        "passes": passes,
        "message": (
            f"{covered}/{total} elements ({coverage:.0%}) have {label}"
            if passes
            else f"No elements have {label}"
        ),
        "details": {"covered_count": covered, "total_elements": total, "coverage": round(coverage, 4)},
    }


def _check_material_assignment(ifc_file) -> dict | None:
    if _element_util is None:
        return None
    return _coverage_check(
        ifc_file,
        check_name="material_assignment",
        label="a material assigned",
        has_feature=lambda e: _element_util.get_material(e) is not None,
    )


def _check_quantity_sets(ifc_file) -> dict | None:
    if _element_util is None:
        return None
    return _coverage_check(
        ifc_file,
        check_name="quantity_sets",
        label="at least one quantity set (Qto_*)",
        has_feature=lambda e: bool(_element_util.get_psets(e, qtos_only=True)),
    )


def _check_document_references(ifc_file) -> dict | None:
    def has_document(element) -> bool:
        for rel in getattr(element, "HasAssociations", None) or []:
            if rel.is_a("IfcRelAssociatesDocument"):
                return True
        return False

    return _coverage_check(
        ifc_file,
        check_name="document_references",
        label="at least one associated document reference",
        has_feature=has_document,
    )


def _check_property_set_coverage(ifc_file) -> dict | None:
    """What fraction of elements carry at least one (non-quantity) Pset,
    and how many distinct IFC classes does the model actually use? The
    class count is informational only - there's no universal "correct"
    count to compare it against."""
    if not _IFC_AVAILABLE or ifc_file is None or _element_util is None:
        return None
    try:
        elements = ifc_file.by_type("IfcElement")
    except Exception:
        return None
    if not elements:
        return None

    covered = 0
    classes: set[str] = set()
    for element in elements:
        classes.add(element.is_a())
        try:
            if _element_util.get_psets(element, psets_only=True):
                covered += 1
        except Exception:
            continue

    total = len(elements)
    coverage = covered / total if total else 0.0
    passes = covered > 0

    return {
        "check": "property_set_coverage",
        "severity": "warning",
        "passes": passes,
        "message": (
            f"{covered}/{total} elements ({coverage:.0%}) carry at least one property set, "
            f"across {len(classes)} distinct IFC classes"
            if passes
            else f"No elements carry a property set, across {len(classes)} distinct IFC classes"
        ),
        "details": {
            "covered_count": covered,
            "total_elements": total,
            "coverage": round(coverage, 4),
            "unique_ifc_classes": len(classes),
        },
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

    for check_fn in (
        _check_provenance_metadata,
        _check_element_classification,
        _check_ownership_history,
        _check_georeferencing,
        _check_units_declaration,
        _check_spatial_structure,
        _check_mvd_declared,
        _check_guid_format,
        _check_spatial_containment,
        _check_material_assignment,
        _check_quantity_sets,
        _check_document_references,
        _check_property_set_coverage,
    ):
        check_result = check_fn(ifc_file)
        if check_result:
            results.append(check_result)

    return results
