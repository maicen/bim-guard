"""Seed built-in BIMGuard engine rulesets into the shared rules table.

The seeding operations are idempotent: each routine checks whether its
``ruleset_id`` already exists before inserting rows.
"""

import json
from pathlib import Path

from app.logging_config import get_logger
from app.services.corrosion_rule_catalog import band_lower_bound
from app.services.rules_service import RuleService
from app.services.static_data_service import StaticDataService

logger = get_logger(__name__)

_RULESET_DIR = Path(__file__).resolve().parents[2] / "data" / "rulesets"

_DEFAULT_CODE_RULESET_FILES = (
    "building_code_part9_ruleset.json",
    "building_code_part9_ext_ruleset.json",
)

# ── Helpers ───────────────────────────────────────────────────────────────────


# ---------------------------------------------------------------------------
# MC-001 temperature class bounds
# ---------------------------------------------------------------------------
# The ruleset states each temperature class as a human range string ("25–45°C")
# and nothing else. classify_temperature needs numbers, and the catalog used to
# supply 0.0 for both bounds when they were absent, so ``t_min <= t <= t_max``
# was false for every real temperature and every element fell through to the
# T4_SAFE_HOT fallback -- risk 0.05, the *lowest* of the six. Water sitting at
# 35 °C in the middle of the Legionella danger zone scored as safely hot.
#
# These are transcriptions of the published range strings, not new thresholds:
#
#   T0_COLD       "< 20°C"     -273.15 .. 20     open below, so absolute zero
#   T1_MARGINAL   "20–25°C"          20 .. 25
#   T2_DANGER     "25–45°C"          25 .. 45
#   T3_TOLERABLE  "45–55°C"          45 .. 55
#   T4_SAFE_HOT   "> 55°C"           55 .. 1000  open above, so beyond any
#                                                building service temperature
#   T5_UNKNOWN    "Unknown"          no bounds -- it is not a temperature range
#                                                but the absence of one, and
#                                                classify_temperature selects it
#                                                by name rather than by compare
#
# Intervals are half-open [t_min, t_max) as classify_temperature evaluates
# them, so the shared endpoints belong to the warmer class and no temperature
# matches two rows.
_TEMPERATURE_BOUNDS: dict[str, tuple[float, float]] = {
    "T0_COLD": (-273.15, 20.0),
    "T1_MARGINAL": (20.0, 25.0),
    "T2_DANGER": (25.0, 45.0),
    "T3_TOLERABLE": (45.0, 55.0),
    "T4_SAFE_HOT": (55.0, 1000.0),
}


def _temperature_bounds(class_key: str) -> dict[str, float]:
    """Return the numeric bounds for an MC-001 temperature class.

    Args:
        class_key: The class key, e.g. ``"T2_DANGER"``.

    Returns:
        ``{"t_min": ..., "t_max": ...}``, or ``{}`` for a class that has no
        range. Empty is meaningful and must not become ``0.0``: the catalog
        now drops a bounded class that lacks numbers rather than silently
        giving it a zero-width interval.
    """
    bounds = _TEMPERATURE_BOUNDS.get(class_key)
    if bounds is None:
        return {}
    return {"t_min": bounds[0], "t_max": bounds[1]}


def _load(filename: str) -> dict:
    asset_key_map = {
        "building_code_part9_ruleset.json": "ruleset:BUILDING-CODE-PART9",
        "building_code_part9_ext_ruleset.json": "ruleset:BUILDING-CODE-PART9-EXT",
        "galvanic_corrosion_ruleset.json": "ruleset:BIMGUARD-GC-001",
        "crevice_corrosion_ruleset.json": "ruleset:BIMGUARD-CC-001",
        "mic_corrosion_ruleset.json": "ruleset:BIMGUARD-MC-001",
        "mm_001_material_media.json": "ruleset:BIMGUARD-MM-001",
        "xm_001_cross_material.json": "ruleset:BIMGUARD-XM-001",
    }

    asset_key = asset_key_map.get(filename)
    if asset_key:
        payload = StaticDataService().get_asset_json(asset_key)
        if isinstance(payload, dict):
            return payload

    # Database-primary, repository fallback: MM-001 and XM-001 ship as approved
    # JSON documents in data/rulesets/ and are not yet registered in
    # static_data_assets. Read them from disk so seeding is not blocked on a
    # migration; the DB copy wins as soon as one exists.
    local_path = _RULESET_DIR / filename
    if local_path.is_file():
        payload = json.loads(local_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload

    raise RuntimeError(f"Missing static ruleset asset: {filename}")


def _create(svc: RuleService, **kwargs) -> None:
    """Thin wrapper that sets extraction_method='seed' by default."""
    kwargs.setdefault("extraction_method", "seed")
    kwargs.setdefault("severity", "mandatory")
    svc.create_rule(**kwargs)


def _existing_references(svc: RuleService, ruleset_id: str) -> set[str]:
    """Return the references already stored for a ruleset.

    Insertion is one network round trip per row, so a seeding run that is
    interrupted part-way leaves the ruleset present but incomplete. Callers use
    this to resume: skip the references already written, insert the rest.

    Reads the table rather than the cached ``list_by_ruleset`` -- see
    :meth:`RuleService.references_for_ruleset` for why a cached answer let a
    duplicate set of band rows through on 2026-09-06.
    """
    return svc.references_for_ruleset(ruleset_id)


def _rule_key(reference: str, target: str, prop: str) -> tuple[str, str, str]:
    """Identity of one code rule within its ruleset.

    Reference alone is not unique: Part 9 cites one clause against several
    element classes (9.8.2.2.(3) covers both IfcStairFlight and IfcSlab), and
    the QA rules share the reference "BIMGuard QA" entirely. Target class and
    property name are what separate them.
    """
    return (reference.strip(), target.strip(), prop.strip())


def _seed_json_ruleset(svc: RuleService, filename: str) -> int:
    """Seed one ruleset JSON document via RuleService.import_ruleset().

    Resumes rather than skipping: this previously returned 0 as soon as the
    ruleset had any row at all, so a set that was interrupted part way through
    stayed permanently incomplete. Only the rules not already stored are
    imported.
    """
    payload = _load(filename)
    ruleset_id = str(payload.get("ruleset_id") or "").strip()
    if not ruleset_id:
        raise ValueError(f"Ruleset file '{filename}' is missing ruleset_id")

    stored = {
        _rule_key(
            str(row.get("reference") or ""),
            str(row.get("target_ifc_class") or ""),
            str(row.get("property_name") or ""),
        )
        for row in svc.rows_for_ruleset(ruleset_id)
    }

    pending = []
    for rule in payload.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        key = _rule_key(
            str(rule.get("ref") or rule.get("reference") or ""),
            str(rule.get("target") or rule.get("target_ifc_class") or ""),
            str(rule.get("property_name") or ""),
        )
        if key in stored:
            continue
        stored.add(key)
        pending.append(rule)

    if not pending:
        return 0
    return svc.import_ruleset({**payload, "rules": pending})


def seed_architectural_code_rules(svc: RuleService) -> int:
    """Ensure hardcoded architectural egress, exit, daylight, and fire separation rules exist in DB."""
    count = 0
    rules_to_seed = [
        {
            "reference": "CODE 9.9.10.1",
            "rule_type": "egress_path",
            "rule_category": "circulation",
            "description": "Maximum egress travel distance from habitable room to exit — 25.0 m",
            "target_ifc_class": "IfcSpace",
            "property_name": "TravelDistance",
            "operator": "<=",
            "check_value": 25.0,
            "unit": "m",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
        {
            "reference": "CODE 9.9.4.1",
            "rule_type": "numeric_comparison",
            "rule_category": "circulation",
            "description": "Minimum number of exterior exits per building storey — 1",
            "target_ifc_class": "IfcBuildingStorey",
            "property_name": "ExitCount",
            "operator": ">=",
            "check_value": 1.0,
            "unit": "count",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
        {
            "reference": "CODE 9.7.2.3",
            "rule_type": "spatial_adjacency",
            "rule_category": "daylight",
            "description": "Minimum window glazing area to floor area ratio for habitable spaces — 1/10 (0.10)",
            "target_ifc_class": "IfcSpace",
            "property_name": "DaylightRatio",
            "operator": ">=",
            "check_value": 0.10,
            "unit": "ratio",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
        {
            "reference": "CODE 9.10.9.14.PW",
            "rule_type": "spatial_adjacency",
            "rule_category": "fire_safety",
            "description": "Fire-rated wall between dwelling units (party wall) — minimum 45-minute fire resistance",
            "target_ifc_class": "IfcWall",
            "property_name": "FireRating",
            "operator": ">=",
            "check_value": 45.0,
            "unit": "min",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
    ]

    # Window data-completeness checks: presence-only, not code-mandated
    # thresholds. Life-safety window properties (fire/acoustic/security
    # rating, thermal transmittance, egress/fire-exit flags, ...) live in
    # Pset_WindowCommon but are almost never populated by default in
    # authoring tools — ComplianceComparator already treats a missing
    # property as MISSING_DATA (or PARTIAL if some elements have it), never
    # PASS, so these rules surface "this window has no documented X" rather
    # than asserting compliance against a threshold nobody has verified.
    # Kept in a separate ruleset_id / mechanism from the seeded "CODE"
    # building-code rows above so they're never mistaken for real regulatory citations.
    window_pset_common_fields = [
        "FireRating",
        "AcousticRating",
        "SecurityRating",
        "ThermalTransmittance",
        "Infiltration",
        "IsExternal",
        "HandicapAccessible",
        "FireExit",
        "SelfClosing",
        "SmokeStop",
    ]
    for field_name in window_pset_common_fields:
        rules_to_seed.append({
            "reference": f"BIMGUARD-WIN.{field_name}",
            "rule_type": "property_presence",
            "rule_category": "window_documentation",
            "description": (
                f"Pset_WindowCommon.{field_name} should be documented on every "
                f"window (BIM-Guard data-completeness check — flags undocumented "
                f"data as MISSING_DATA, not a jurisdiction-specific threshold)"
            ),
            "target_ifc_class": "IfcWindow",
            "property_name": field_name,
            "operator": "documented",
            "ruleset_id": "BIMGUARD-WINDOW-DATA",
            "mechanism": "DATA_QC",
            "category": "Arch",
            "severity": "recommended",
        })

    existing_refs = svc.all_references()

    for item in rules_to_seed:
        if item["reference"] not in existing_refs:
            _create(svc, **item)
            count += 1

    return count


def seed_default_code_rulesets(svc: RuleService) -> dict[str, int]:
    """Seed baseline/extended building-code rulesets from JSON files."""
    seeded: dict[str, int] = {}
    for filename in _DEFAULT_CODE_RULESET_FILES:
        payload = _load(filename)
        ruleset_id = str(payload.get("ruleset_id") or "").strip() or filename
        seeded[ruleset_id] = _seed_json_ruleset(svc, filename)
    seed_architectural_code_rules(svc)
    return seeded


def _seed_risk_bands(
    svc: RuleService,
    *,
    ruleset_id: str,
    prefix: str,
    bands: dict,
    target_ifc_class: str = "IfcPipeSegment",
) -> None:
    """Seed composite-score threshold rows for a ruleset."""
    existing = _existing_references(svc, ruleset_id)
    for band_name, band_data in bands.items():
        if band_name not in {"Medium", "High", "Critical"}:
            continue
        if f"{prefix}.BAND.{band_name.upper()}" in existing:
            # Callers reach this on every startup once the ruleset is present.
            # Without the guard each boot inserted three more copies of the same
            # band row: they had accumulated into the majority of the rules
            # table and, carrying no mechanism, were being swept up by
            # RuleService.list_code_rules() as if they were building-code rules.
            continue
        reference = f"{prefix}.BAND.{band_name.upper()}"
        existing.add(reference)
        # A float, never the string it was parsed out of. check_value is stored
        # JSON-encoded, so a string threshold lands in the column as the seven
        # characters "0.85" -- quotes included -- which every reader of the row
        # then failed to coerce (audit F1).
        try:
            threshold = band_lower_bound(str((band_data or {}).get("range") or ""))
        except ValueError as exc:
            logger.error("Not seeding %s: %s", reference, exc)
            continue
        _create(
            svc,
            reference=reference,
            rule_type="risk_band",
            rule_category="threshold_band",
            description=band_data.get("bcf_action", band_name),
            check_value=threshold,
            keyword=band_name,
            mechanism=prefix,
            ruleset_id=ruleset_id,
            target_ifc_class=target_ifc_class,
            parameters=json.dumps({"band": band_name, **band_data}),
        )


# ── GC-001, CC-001, MC-001 — provenance of what is seeded below ───────────────
# Every GC-001, CC-001 and MC-001 row below is written with
# source_text="Source: <citation>". That citation names the standard or body of
# practice governing the mechanism; it is NOT the document the number was read
# from. The numbers are a calibration authored for these rulesets with AI
# assistance (NotebookLM prompts, April 2026; docs/RESOURCES.md:97-104), none of
# the cited documents is held, and no value has been verified against one. The
# "Source:" prefix is left as it is because it is stored rule data; the corrected
# reading, and proposed wording, are in
# docs/planning/corrosion_provenance_2026-09-13.md.

# ── GC-001 — Galvanic Corrosion ───────────────────────────────────────────────


def _seed_gc001(svc: RuleService) -> int:
    RULESET_ID = "BIMGUARD-GC-001"
    if svc.has_ruleset(RULESET_ID):
        _seed_risk_bands(
            svc,
            ruleset_id=RULESET_ID,
            prefix="GC-001",
            bands=_load("galvanic_corrosion_ruleset.json")["risk_bands"],
        )
        return 0

    gc = _load("galvanic_corrosion_ruleset.json")
    TARGET = "IfcPipeSegment"
    MECH = "GC-001"
    count = 0

    def _r(**kw):
        nonlocal count
        _create(svc, mechanism=MECH, ruleset_id=RULESET_ID, target_ifc_class=TARGET, **kw)
        count += 1

    # ── Scoring model ─────────────────────────────────────────────────────────
    sm = gc["scoring_model"]
    _r(
        reference="GC-001.SCORING",
        rule_type="scoring_model",
        rule_category="scoring_model",
        description=sm["formula"],
        parameters=json.dumps(sm),
    )

    _seed_risk_bands(svc, ruleset_id=RULESET_ID, prefix="GC-001", bands=gc["risk_bands"])

    # ── Environment classes (E1–E7) ───────────────────────────────────────────
    env_src = gc["environment_classes"].get("source", "NASA-STD-6012")
    for key, data in gc["environment_classes"].items():
        if key == "source":
            continue
        _r(
            reference=f"GC-001.ENV.{key}",
            rule_type="environment_class",
            rule_category="reference_config",
            description=f"{key} — {data['label']}: threshold {data['voltage_threshold_v']} V, multiplier {data['multiplier']}",
            check_value=data["voltage_threshold_v"],
            operator="<=",
            unit="V",
            source_text=f"Source: {env_src}",
            parameters=json.dumps({**data, "class_key": key}),
        )

    # ── Area ratio bands ──────────────────────────────────────────────────────
    ar_src = gc["area_ratio_bands"].get("source", "Prosoco Technical Note 104")
    for band in gc["area_ratio_bands"]["bands"]:
        ref_key = band["label"].upper().replace(" ", "_")
        _r(
            reference=f"GC-001.AREA_RATIO.{ref_key}",
            rule_type="area_ratio_band",
            rule_category="threshold_band",
            description=f"Area ratio band — {band['label']}: min ratio {band['min_ratio']}, risk score {band['risk_score']}",
            check_value=band["risk_score"],
            value_min=band["min_ratio"],
            operator=">=",
            source_text=f"Source: {ar_src}",
            parameters=json.dumps(band),
        )

    # ── Galvanic series materials ─────────────────────────────────────────────
    mat_src = gc["galvanic_series"].get("source", "WorldStainless / Euro Inox")
    for mat_key, mat in gc["galvanic_series"]["materials"].items():
        noble_label = "noble (cathodic)" if mat.get("noble") else "active (anodic)"
        _r(
            reference=f"GC-001.MAT.{mat_key.upper()}",
            rule_type="galvanic_series_entry",
            rule_category="material_property",
            description=f"{mat['label']}: potential {mat['potential_v']} V ({noble_label})",
            check_value=mat["potential_v"],
            unit="V",
            keyword=mat_key,
            source_text=f"Source: {mat_src}",
            parameters=json.dumps({**mat, "material_key": mat_key}),
        )

    # ── PREN thresholds by environment ────────────────────────────────────────
    pren = gc["pren_thresholds"]
    pren_src = pren.get("source", "IMOA Design Manual 4th Ed.")
    for env_key, pdata in pren["by_environment"].items():
        _r(
            reference=f"GC-001.PREN.{env_key}",
            rule_type="pren_threshold",
            rule_category="threshold_band",
            description=f"Min PREN {pdata['min_pren']} for {env_key}: {pdata['note']}",
            check_value=pdata["min_pren"],
            operator=">=",
            source_text=f"Source: {pren_src}",
            parameters=json.dumps(
                {**pdata, "environment_class": env_key, "formula": pren.get("formula", "")}
            ),
        )

    # ── Mitigations ───────────────────────────────────────────────────────────
    for code, desc in gc["mitigation_catalogue"].items():
        _r(
            reference=code,
            rule_type="mitigation",
            rule_category="mitigation",
            description=desc,
            severity="recommended",
            parameters=json.dumps({"code": code}),
        )

    print(f"[RulesetSeeder] GC-001: {count} rules seeded")
    return count


# ── CC-001 — Crevice Corrosion ────────────────────────────────────────────────


def _seed_cc001(svc: RuleService) -> int:
    RULESET_ID = "BIMGUARD-CC-001"
    if svc.has_ruleset(RULESET_ID):
        _seed_risk_bands(
            svc,
            ruleset_id=RULESET_ID,
            prefix="CC-001",
            bands=_load("crevice_corrosion_ruleset.json")["risk_bands"],
        )
        return 0

    cc = _load("crevice_corrosion_ruleset.json")
    TARGET = "IfcPipeFitting"
    MECH = "CC-001"
    count = 0

    def _r(**kw):
        nonlocal count
        _create(svc, mechanism=MECH, ruleset_id=RULESET_ID, target_ifc_class=TARGET, **kw)
        count += 1

    # ── Scoring model ─────────────────────────────────────────────────────────
    sm = cc["scoring_model"]
    _r(
        reference="CC-001.SCORING",
        rule_type="scoring_model",
        rule_category="scoring_model",
        description=sm["formula"],
        parameters=json.dumps(sm),
    )

    _seed_risk_bands(svc, ruleset_id=RULESET_ID, prefix="CC-001", bands=cc["risk_bands"])

    # ── CCT grades ────────────────────────────────────────────────────────────
    cct = cc["cct_table"]
    cct_src = cct.get("test_conditions", "ASTM G48 Method B")
    for mat_key, mat in cct["grades"].items():
        _r(
            reference=f"CC-001.CCT.{mat_key.upper()}",
            rule_type="cct_material",
            rule_category="material_property",
            description=f"{mat['label']}: CCT = {mat['cct_c']} °C, PREN = {mat['pren_typical']}",
            check_value=mat["cct_c"],
            unit="°C",
            keyword=mat_key,
            source_text=f"Source: {cct_src}",
            parameters=json.dumps({**mat, "material_key": mat_key}),
        )

    # ── Geometry classes ──────────────────────────────────────────────────────
    geom = cc["geometry_classes"]
    geom_src = geom.get("description", "CIBSE Guide G / CIRIA C692")
    for class_key, data in geom.items():
        if class_key == "description":
            continue
        _r(
            reference=f"CC-001.GEOM.{class_key.upper()}",
            rule_type="geometry_class",
            rule_category="reference_config",
            description=f"Geometry {class_key}: width {data.get('crevice_width_mm', '')}, risk {data['risk']}",
            check_value=data["risk"],
            source_text=f"Source: {geom_src}",
            parameters=json.dumps({**data, "class_key": class_key}),
        )

    # ── Joint types (JT-001 … JT-014) ────────────────────────────────────────
    # Seeded, but not matched by the engine: every element scores JT-014.
    # See docs/defects/CC-001-scoring-inputs-inert.md.
    for jt_code, jt in cc["joint_type_library"]["types"].items():
        _r(
            reference=f"CC-001.JT.{jt_code}",
            rule_type="joint_type",
            rule_category="reference_config",
            description=f"{jt_code} — {jt['label']}: geometry {jt['geometry']}, risk {jt['risk']}",
            check_value=jt["risk"],
            keyword=jt_code,
            parameters=json.dumps({**jt, "joint_code": jt_code}),
        )

    # ── Environment severity classes ──────────────────────────────────────────
    env_src = cc["environment_severity"].get("source", "EN ISO 15329:2007")
    for env_key, data in cc["environment_severity"]["classes"].items():
        _r(
            reference=f"CC-001.ENV.{env_key}",
            rule_type="environment_severity",
            rule_category="reference_config",
            description=f"{env_key} — {data['label']}: severity {data['severity']}",
            check_value=data["severity"],
            source_text=f"Source: {env_src}",
            parameters=json.dumps({**data, "class_key": env_key}),
        )

    # ── Mitigations ───────────────────────────────────────────────────────────
    for code, desc in cc["mitigation_catalogue"].items():
        _r(
            reference=code,
            rule_type="mitigation",
            rule_category="mitigation",
            description=desc,
            severity="recommended",
            parameters=json.dumps({"code": code}),
        )

    print(f"[RulesetSeeder] CC-001: {count} rules seeded")
    return count


# ── MC-001 — Microbially Influenced Corrosion ─────────────────────────────────


#: The corrected citation for the MC-001 materials whose payload ``reference``
#: names ASTM G-187 (a soil-resistivity practice) or NACCE TPC 11 (an
#: unverified, misspelt NACE document). Wording from
#: docs/planning/corrosion_provenance_2026-09-13.md §12.2, identical to what
#: migration 20260914195107 writes.
_MC001_MATERIAL_SOURCE_TEXT = (
    "Source: AMPP (formerly NACE) industry practice, MIC mechanism only; "
    "score is MC-001 authored calibration"
)

#: Payload ``reference`` -> seeded ``source_text`` for the seven
#: ``material_susceptibility`` entries carrying a suspect citation (carbon_steel,
#: cast_iron, galv_steel, ss304, ss316, duplex2205, titanium; five distinct
#: strings). Keyed by the exact payload string; every other reference is seeded
#: as ``Source: <reference>`` unchanged.
_MC001_SUPERSEDED_MATERIAL_REFERENCES = {
    "ASTM G-187 / NACCE TPC 11": _MC001_MATERIAL_SOURCE_TEXT,
    "NACCE TPC 11": _MC001_MATERIAL_SOURCE_TEXT,
    "ASTM G-187": _MC001_MATERIAL_SOURCE_TEXT,
    "NACE / ASTM G-187": _MC001_MATERIAL_SOURCE_TEXT,
    "ASTM G-187 — exceptional MIC resistance": _MC001_MATERIAL_SOURCE_TEXT,
}


def _mc001_material_source_text(mat: dict) -> str:
    """Return the ``source_text`` seeded for one MC-001 material.

    A payload reference in :data:`_MC001_SUPERSEDED_MATERIAL_REFERENCES` is
    replaced by :data:`_MC001_MATERIAL_SOURCE_TEXT`; any other reference, and the
    no-reference default, is emitted as before. The seeder inserts only, so
    existing rows are corrected by migration 20260914195107; this change prevents
    a fresh seed from reintroducing the old text.
    """
    reference = mat.get(
        "reference",
        "AMPP (formerly NACE) industry practice, MIC mechanism only; score is MC-001 authored calibration",
    )
    return _MC001_SUPERSEDED_MATERIAL_REFERENCES.get(reference, f"Source: {reference}")


def _seed_mc001(svc: RuleService) -> int:
    RULESET_ID = "BIMGUARD-MC-001"
    if svc.has_ruleset(RULESET_ID):
        _seed_risk_bands(
            svc,
            ruleset_id=RULESET_ID,
            prefix="MC-001",
            bands=_load("mic_corrosion_ruleset.json")["risk_bands"],
        )
        return 0

    mc = _load("mic_corrosion_ruleset.json")
    TARGET = "IfcPipeSegment"
    MECH = "MC-001"
    count = 0

    def _r(**kw):
        nonlocal count
        _create(svc, mechanism=MECH, ruleset_id=RULESET_ID, target_ifc_class=TARGET, **kw)
        count += 1

    # ── Scoring model ─────────────────────────────────────────────────────────
    sm = mc["scoring_model"]
    _r(
        reference="MC-001.SCORING",
        rule_type="scoring_model",
        rule_category="scoring_model",
        description=sm["formula"],
        parameters=json.dumps(sm),
    )

    _seed_risk_bands(svc, ruleset_id=RULESET_ID, prefix="MC-001", bands=mc["risk_bands"])

    # ── Flow velocity classes ─────────────────────────────────────────────────
    for fv_key, data in mc["flow_velocity_classes"].items():
        _r(
            reference=f"MC-001.FLOW.{fv_key}",
            rule_type="flow_velocity_class",
            rule_category="threshold_band",
            description=f"{fv_key} — {data['label']}: risk {data['risk']}",
            check_value=data["risk"],
            value_min=data.get("threshold_ms"),
            unit="m/s",
            source_text=f"Source: {data.get('reference', 'CIBSE TM13:2013')}",
            parameters=json.dumps({**data, "class_key": fv_key}),
        )

    # ── Temperature classes ───────────────────────────────────────────────────
    for t_key, data in mc["temperature_classes"].items():
        _r(
            reference=f"MC-001.TEMP.{t_key}",
            rule_type="temperature_class",
            rule_category="threshold_band",
            description=f"{t_key} — {data['range']}: risk {data['risk']}",
            check_value=data["risk"],
            unit="°C",
            source_text=f"Source: {data.get('reference', 'WHO GDWQ / CIBSE TM13')}",
            parameters=json.dumps(
                {**data, **_temperature_bounds(t_key), "class_key": t_key}
            ),
        )

    # ── Dead-leg classes ──────────────────────────────────────────────────────
    for dl_key, data in mc["dead_leg_classes"].items():
        _r(
            reference=f"MC-001.DEADLEG.{dl_key}",
            rule_type="dead_leg_class",
            rule_category="threshold_band",
            description=f"{dl_key} — {data['label']}: L/D {data['length_to_dia_ratio']}, risk {data['risk']}",
            check_value=data["risk"],
            source_text=f"Source: {data.get('reference', 'HSE HSG274 Part 2')}",
            parameters=json.dumps({**data, "class_key": dl_key}),
        )

    # ── Material MIC susceptibility ───────────────────────────────────────────
    for mat_key, mat in mc["material_susceptibility"].items():
        _r(
            reference=f"MC-001.MAT.{mat_key.upper()}",
            rule_type="material_susceptibility",
            rule_category="material_property",
            description=f"{mat['label']}: MIC susceptibility score {mat['score']}",
            check_value=mat["score"],
            keyword=mat_key,
            source_text=_mc001_material_source_text(mat),
            parameters=json.dumps({**mat, "material_key": mat_key}),
        )

    # ── System type modifiers ─────────────────────────────────────────────────
    for sys_key, data in mc["system_type_modifiers"].items():
        _r(
            reference=f"MC-001.SYS.{sys_key}",
            rule_type="system_modifier",
            rule_category="reference_config",
            description=f"{sys_key}: MIC risk multiplier {data['multiplier']} — {data.get('rationale', '')}",
            check_value=data["multiplier"],
            keyword=sys_key,
            parameters=json.dumps({**data, "system_key": sys_key}),
        )

    # ── Under-insulation risk states ──────────────────────────────────────────
    for state_key, risk in mc["under_insulation_risk"].items():
        _r(
            reference=f"MC-001.UIC.{state_key.upper()}",
            rule_type="under_insulation_risk",
            rule_category="threshold_band",
            description=f"Insulation condition '{state_key}': UIC risk {risk}",
            check_value=risk,
            parameters=json.dumps({"state_key": state_key, "risk": risk}),
        )

    # ── Mitigations ───────────────────────────────────────────────────────────
    for code, desc in mc["mitigation_catalogue"].items():
        _r(
            reference=code,
            rule_type="mitigation",
            rule_category="mitigation",
            description=desc,
            severity="recommended",
            parameters=json.dumps({"code": code}),
        )

    print(f"[RulesetSeeder] MC-001: {count} rules seeded")
    return count


#: Why each SB-001 threshold has the value it has, as ``source_text``. Worded
#: from the ``provenance`` notes in ``data/rulesets/sb001_seismic_clearance.json``
#: (schema 1.3.0); tests/test_sb001_seeded_provenance.py holds the two together.
#:
#: Three prefixes, matching the three provenance categories the configuration
#: uses: "Sourced to ..." (a held document states the value), "BIMGUARD SB-001
#: authored calibration. " (no source; BIMGUARD chose the value as a screening
#: threshold), and "Unsourced placeholder ... " (no source, and the value is not
#: a BIMGUARD choice either — it is an unverified figure with no known origin
#: BIMGUARD can stand behind, kept only because no sourced replacement exists).
_SB001_SOURCE_TEXT = {
    # Unsourced, not authored: 63.0 is not a BIMGUARD screening choice. It is the
    # same fabricated Hermes research pass that produced the pre-2026-09-16 angle
    # and pre-2026-09-16 spacing values (same unit-mirroring signature), and no
    # document held gives a pipe-diameter seismic-bracing exemption threshold to
    # replace it with.
    "SB-001.01": (
        "Unsourced placeholder. "
        "Not a BIMGUARD authored calibration and not a stated standard value: this is an "
        "unverified figure carried over from the same fabricated Hermes research pass that "
        "produced the brace angle and brace spacing values (see changelog 1.2.0 and 1.3.0), "
        "flagged by the same unit-mirroring signature (EN 63 mm ≈ 2.48 in, close to NFPA's "
        "reported ≈2.5 in). Falls within the ASCE 7-10 exemption band FEMA E-74 §6.4.3.1 "
        "reports (roughly 1 to 3 in / 25.4-76.2 mm depending on seismic design category and "
        "occupancy), but that band does not fix a single threshold, so it does not confirm "
        "the value. No document in D:/claude-workspace/hilti-seismic/sources (NFPA 13, "
        "UFGS 23 05 48.19, Hilti Seismic Manual) states a pipe-diameter seismic-bracing "
        "exemption threshold, so no sourced replacement is available; the value is left at "
        "63.0 pending one and is marked unsourced/placeholder rather than authored."
    ),
    "SB-001.02": (
        "BIMGUARD SB-001 authored calibration. Authored. No source. Also the value of "
        "brace_types[*].clearance_mm, which the loader applies in preference. FEMA E-74 "
        "App. A §3.9.D.9 gives a related rule, horizontal clearance of at least 2/3 the "
        "hanger length, but only for unbraced (exempt) piping. No braced-service clearance "
        "dimension exists in any source held."
    ),
    # Sourced, not authored: same shape as SB-001.05 below — an attribution
    # sentence followed by the configuration's own provenance note, verbatim.
    "SB-001.03": (
        "Sourced to the Hilti Seismic Manual – Earthquake-resistant design of MEP supports, "
        "MT System (05/2022), citing NFPA 13 / EN 12845 Annex E: transverse restraint "
        "spacing 12 m. "
        "Sourced. Replaces the former 1.0, which was not BIMGUARD calibration: it was the "
        "same unverified Hermes research pass that produced the fabricated brace angle, "
        "with an additional feet-written-as-inches unit corruption -- the same figure, "
        "stated once in metres and once (corrupted) in inches by that pass's two invented "
        "per-standard entries, survived a min() merge across them. The real value the "
        "corrupted figure belongs to is 40 ft (12.19 m), which this source states directly "
        "as 12 m. See changelog 1.3.0 and "
        "D:/claude-workspace/hilti-seismic/sb001_spacing_investigation.md."
    ),
    "SB-001.04": (
        "Sourced to the Hilti Seismic Manual – Earthquake-resistant design of MEP supports, "
        "MT System (05/2022), citing NFPA 13 / EN 12845 Annex E: longitudinal restraint "
        "spacing 24 m. "
        "Sourced. Replaces the former 1.5, from the same fabricated Hermes pass as the "
        "transverse value, with an extra digit change (the real 80 ft became 60 in before "
        "conversion to 1.5 m). The real NFPA 13 value is 80 ft (24.38 m), which this source "
        "states directly as 24 m. See changelog 1.3.0 and "
        "D:/claude-workspace/hilti-seismic/sb001_spacing_investigation.md."
    ),
    "SB-001.05": (
        "Sourced to the Hilti Seismic Manual – Earthquake-resistant design of MEP supports, "
        "MT System (05/2022), Annex A \"Tilt angle – for all bracings\": nominal brace tilt "
        "angle 45° ± 15° on the horizontal level, i.e. 30-60° from horizontal. "
        "Lower bound of the source's stated 45° ± 15° band (45 - 15). Datum: degrees from "
        "horizontal, the same convention the source uses. Replaces the former 40.0, which "
        "came from an unverified AI research summary; see changelog 1.2.0. FEMA E-74 "
        "contains no brace angle for pipe or duct. A vendor design manual, not a code."
    ),
}

#: What superseded SB-001 rows carry, and what replaces it. Each entry maps a
#: column to every stored value known to be stale (``from``) and the current one
#: (``to``). A stored field is corrected only while it still holds exactly one of
#: those values, so a rule someone has since edited by hand is left as they left it.
#:
#: Three generations are corrected here:
#:
#: - Rows seeded before 2026-09-13 attributed authored spacing thresholds to
#:   EN 1998-1 / DIN 4149, which give no MEP brace spacing, and carried the Hermes
#:   research summary's EN-only 35-70 degree angle range.
#: - Rows seeded between 2026-09-13 and 2026-09-16 carried the 40-65 degree range
#:   labelled BIMGUARD authored calibration, and (for spacing) a 1.0 m / 1.5 m
#:   value likewise labelled BIMGUARD authored calibration. Both labels were
#:   wrong twice over: neither range nor spacing pair was BIMGUARD's calibration
#:   (they were the same unverified research summary's invented DIN 4149 and
#:   EN 1998-1 figures, the spacing pair additionally corrupted by a
#:   feet-written-as-inches unit error), and both are now sourced to the Hilti
#:   Seismic Manual (05/2022): the angle as 45° ± 15° (30-60° from horizontal),
#:   the spacing as 12 m transverse / 24 m longitudinal (citing NFPA 13 /
#:   EN 12845 Annex E).
#: - The pipe diameter threshold (SB-001.01) never changed value, but its
#:   source_text is corrected here too: it was labelled "BIMGUARD SB-001
#:   authored calibration", which is also wrong (see sb001_spacing_investigation.md);
#:   there being no sourced replacement, it is now labelled unsourced/placeholder.
_SB001_SUPERSEDED = {
    "SB-001.01": {
        "source_text": {
            "from": (
                "BIMGUARD SB-001 authored calibration. Within the ASCE 7-10 exemption band "
                "as reported by FEMA E-74 §6.4.3.1: roughly 1 to 3 in (25.4-76.2 mm) "
                "depending on seismic design category and occupancy. 63 mm ≈ 2.48 in falls "
                "inside that band. Not a stated standard value.",
            ),
            "to": _SB001_SOURCE_TEXT["SB-001.01"],
        },
    },
    "SB-001.03": {
        "description": {
            "from": (
                "Maximum transverse seismic brace spacing — 1.0 m per EN 1998-1 / DIN 4149",
                "Maximum transverse seismic brace spacing — 1.0 m, BIMGUARD SB-001 screening "
                "calibration (authored, not a code value)",
            ),
            "to": (
                "Maximum transverse seismic brace spacing — 12 m, Hilti Seismic Manual "
                "05/2022 (NFPA 13 / EN 12845 Annex E)"
            ),
        },
        "check_value": {"from": (1.0,), "to": 12.0},
        "source_text": {
            "from": (
                "BIMGUARD SB-001 authored calibration. Authored conservative calibration. "
                "Upstream reference: FEMA E-74 App. A §3.9.D.6-7 gives maxima of 40 ft "
                "(12.19 m) for ductile and 20 ft (6.10 m) for nonductile pipe, from a sample "
                "specification intended to be customised. BIMGUARD's value is approximately "
                "6-12× tighter and is a screening threshold, not a code requirement. Not "
                "applicable to ducts: E-74 gives no duct brace spacing.",
            ),
            "to": _SB001_SOURCE_TEXT["SB-001.03"],
        },
    },
    "SB-001.04": {
        "description": {
            "from": (
                "Maximum longitudinal seismic brace spacing — 1.5 m per EN 1998-1 / DIN 4149",
                "Maximum longitudinal seismic brace spacing — 1.5 m, BIMGUARD SB-001 "
                "screening calibration (authored, not a code value)",
            ),
            "to": (
                "Maximum longitudinal seismic brace spacing — 24 m, Hilti Seismic Manual "
                "05/2022 (NFPA 13 / EN 12845 Annex E)"
            ),
        },
        "check_value": {"from": (1.5,), "to": 24.0},
        "source_text": {
            "from": (
                "BIMGUARD SB-001 authored calibration. Authored conservative calibration. "
                "Upstream: FEMA E-74 App. A §3.9.D.6 gives 80 ft (24.38 m) ductile / 40 ft "
                "(12.19 m) nonductile. Same screening rationale as the transverse value. Not "
                "applicable to ducts.",
            ),
            "to": _SB001_SOURCE_TEXT["SB-001.04"],
        },
    },
    "SB-001.05": {
        "description": {
            "from": (
                "Seismic brace installation angle — permissible range 35° to 70° from horizontal",
                "Seismic brace installation angle — permissible range 40° to 65° from "
                "horizontal, BIMGUARD SB-001 screening calibration (authored, not a code value)",
            ),
            "to": (
                "Seismic brace installation angle — permissible range 30° to 60° from "
                "horizontal (45° ± 15°), Hilti Seismic Manual 05/2022"
            ),
        },
        "value_min": {"from": (35.0, 40.0), "to": 30.0},
        "value_max": {"from": (70.0, 65.0), "to": 60.0},
        "source_text": {
            "from": (
                "BIMGUARD SB-001 authored calibration. Authored. No source. FEMA E-74 contains no "
                "brace angle for pipe or duct. Datum: degrees from horizontal.",
            ),
            "to": _SB001_SOURCE_TEXT["SB-001.05"],
        },
    },
}


def _correct_superseded_seismic_rows(svc: RuleService) -> int:
    """Correct SB-001 rows already stored with superseded content.

    The insert pass skips any reference that exists, so without this a database
    seeded earlier would keep the old descriptions and angle range indefinitely.
    Scoped to the SB-001 references in :data:`_SB001_SUPERSEDED` and
    :data:`_SB001_SOURCE_TEXT`, and to fields still holding one of the exact
    superseded values (or, for ``source_text``, still empty).

    Returns:
        The number of rows changed.
    """
    corrected = 0
    for row in svc.rows_for_ruleset("BIMGUARD-SB-001"):
        reference = str(row.get("reference") or "").strip()
        if reference not in _SB001_SOURCE_TEXT:
            continue
        columns: dict[str, str] = {}
        for field, change in _SB001_SUPERSEDED.get(reference, {}).items():
            stored = row.get(field)
            superseded, current = change["from"], change["to"]
            if field in {"description", "source_text"}:
                if str(stored or "").strip() in superseded:
                    columns[field] = current
            elif RuleService._parse_numeric(_json_scalar(stored)) in superseded:
                columns[field] = json.dumps(current)
        if not str(row.get("source_text") or "").strip():
            columns["source_text"] = _SB001_SOURCE_TEXT[reference]
        if columns:
            svc.patch_rule_columns(row["id"], columns)
            corrected += 1
            logger.info(
                "Corrected superseded SB-001 rule reference=%s fields=%s",
                reference,
                sorted(columns),
            )
    return corrected


def _json_scalar(stored) -> str:
    """Unwrap a JSON-encoded scalar column (``'35.0'``, ``'"35.0"'``) to its text."""
    if stored is None:
        return ""
    try:
        decoded = json.loads(stored) if isinstance(stored, str) else stored
    except ValueError:
        return str(stored)
    return "" if decoded is None else str(decoded)


def seed_seismic_rules(svc: RuleService) -> int:
    """Seed Blue Halo seismic bracing clearance rules (BIMGUARD-SB-001).

    Only the base clearance (SB-001.02) and the clearance additions are BIMGUARD
    screening calibration with no source; each such row's ``source_text`` says so.
    The brace angle (SB-001.05) and brace spacing (SB-001.03, SB-001.04) are
    sourced to the Hilti Seismic Manual (05/2022). The pipe diameter threshold
    (SB-001.01) is neither: it is an unverified figure with no known BIMGUARD
    rationale and no sourced replacement, so its ``source_text`` says that
    plainly instead of calling it authored. Rows seeded with superseded content
    are brought up to date in place by :func:`_correct_superseded_seismic_rows`.

    Returns:
        The number of rows inserted.
    """
    rules_to_seed = [
        {
            "reference": "SB-001.01",
            "rule_type": "numeric_comparison",
            "rule_category": "property_check",
            "category": "seismic",
            "description": "Seismic pipe bracing threshold — pipe diameter >= 63.0 mm requires Blue Halo clearance envelope",
            "target_ifc_class": "IfcPipeSegment",
            "property_name": "NominalDiameter",
            "operator": ">=",
            "check_value": 63.0,
            "unit": "mm",
            "ruleset_id": "BIMGUARD-SB-001",
            "mechanism": "SEISMIC",
            "severity": "mandatory",
        },
        {
            "reference": "SB-001.02",
            "rule_type": "spatial_clearance",
            "rule_category": "property_check",
            "category": "seismic",
            "description": "Seismic bracing access clearance envelope — 200 mm buffer volume around braced services",
            "target_ifc_class": "IfcPipeSegment",
            "property_name": "ClearanceZone",
            "operator": ">=",
            "check_value": 200.0,
            "unit": "mm",
            "ruleset_id": "BIMGUARD-SB-001",
            "mechanism": "SEISMIC",
            "severity": "mandatory",
        },
        {
            "reference": "SB-001.03",
            "rule_type": "numeric_comparison",
            "rule_category": "property_check",
            "category": "seismic",
            "description": _SB001_SUPERSEDED["SB-001.03"]["description"]["to"],
            "target_ifc_class": "IfcPipeSegment",
            "property_name": "TransverseBraceSpacing",
            "operator": "<=",
            "check_value": 12.0,
            "unit": "m",
            "ruleset_id": "BIMGUARD-SB-001",
            "mechanism": "SEISMIC",
            "severity": "mandatory",
        },
        {
            "reference": "SB-001.04",
            "rule_type": "numeric_comparison",
            "rule_category": "property_check",
            "category": "seismic",
            "description": _SB001_SUPERSEDED["SB-001.04"]["description"]["to"],
            "target_ifc_class": "IfcPipeSegment",
            "property_name": "LongitudinalBraceSpacing",
            "operator": "<=",
            "check_value": 24.0,
            "unit": "m",
            "ruleset_id": "BIMGUARD-SB-001",
            "mechanism": "SEISMIC",
            "severity": "mandatory",
        },
        {
            "reference": "SB-001.05",
            "rule_type": "numeric_range",
            "rule_category": "property_check",
            "category": "seismic",
            "description": _SB001_SUPERSEDED["SB-001.05"]["description"]["to"],
            "target_ifc_class": "IfcPipeSegment",
            "property_name": "BraceAngle",
            "operator": "between",
            "value_min": 30.0,
            "value_max": 60.0,
            "unit": "deg",
            "ruleset_id": "BIMGUARD-SB-001",
            "mechanism": "SEISMIC",
            "severity": "mandatory",
        },
    ]

    count = 0
    existing_refs = svc.all_references()
    for item in rules_to_seed:
        if item["reference"] not in existing_refs:
            _create(svc, source_text=_SB001_SOURCE_TEXT[item["reference"]], **item)
            count += 1
    _correct_superseded_seismic_rows(svc)
    return count


# ── MM-001 — Material / Media Compatibility ───────────────────────────────────


def _seed_band_thresholds(
    svc: RuleService,
    *,
    ruleset_id: str,
    prefix: str,
    mechanism: str,
    target_ifc_class: str,
    thresholds: dict,
    existing: set[str] | None = None,
) -> int:
    """Seed numeric composite-score band thresholds ({'medium': 0.35, ...})."""
    seen = existing if existing is not None else set()
    count = 0
    for band_name in ("medium", "high", "critical"):
        if band_name not in thresholds:
            continue
        if f"{prefix}.BAND.{band_name.upper()}" in seen:
            continue
        seen.add(f"{prefix}.BAND.{band_name.upper()}")
        _create(
            svc,
            mechanism=mechanism,
            ruleset_id=ruleset_id,
            target_ifc_class=target_ifc_class,
            reference=f"{prefix}.BAND.{band_name.upper()}",
            rule_type="risk_band",
            rule_category="threshold_band",
            description=(
                f"Composite score >= {thresholds[band_name]} bands as {band_name.capitalize()}"
            ),
            check_value=thresholds[band_name],
            operator=">=",
            keyword=band_name.capitalize(),
            parameters=json.dumps(
                {
                    "band": band_name.capitalize(),
                    "min_score": thresholds[band_name],
                    "note": thresholds.get("_note", ""),
                }
            ),
        )
        count += 1
    return count


def _seed_mm001(svc: RuleService) -> int:
    """Decompose the MM-001 material/media pack into individual rule rows."""
    RULESET_ID = "BIMGUARD-MM-001"
    existing = _existing_references(svc, RULESET_ID)

    mm = _load("mm_001_material_media.json")
    params = mm.get("parameters", {})
    meta = mm.get("metadata", {})
    TARGET = "IfcPipeSegment"
    MECH = "MM-001"
    count = 0

    def _r(**kw):
        nonlocal count
        if kw.get("reference") in existing:
            return
        _create(svc, mechanism=MECH, ruleset_id=RULESET_ID, target_ifc_class=TARGET, **kw)
        existing.add(kw["reference"])
        count += 1

    # ── Scoring model ─────────────────────────────────────────────────────────
    weights = params.get("weights", {})
    _r(
        reference="MM-001.SCORING",
        rule_type="scoring_model",
        rule_category="scoring_model",
        description=meta.get(
            "scoring_note",
            "MM-001 composite = 0.40*material_media + 0.35*environment_severity "
            "+ 0.25*temperature_stress",
        ),
        source_text="; ".join(str(s) for s in meta.get("standards", [])),
        parameters=json.dumps({"weights": weights, "scoring_note": meta.get("scoring_note", "")}),
    )

    # ── Risk band thresholds ──────────────────────────────────────────────────
    count += _seed_band_thresholds(
        svc,
        ruleset_id=RULESET_ID,
        prefix="MM-001",
        mechanism=MECH,
        target_ifc_class=TARGET,
        thresholds=params.get("risk_band_thresholds", {}),
        existing=existing,
    )

    # ── Compatibility matrix (material × medium) ──────────────────────────────
    for material, media in params.get("compatibility_matrix", {}).items():
        if not isinstance(media, dict):
            continue
        for medium, cell in media.items():
            if not isinstance(cell, dict):
                continue
            _r(
                reference=f"MM-001.{material}.{medium}",
                rule_type="material_media_compatibility",
                rule_category="material_property",
                description=(
                    f"{material} carrying {medium}: compatibility score {cell.get('score')} "
                    f"(higher = worse), predicted life {cell.get('years')} yr, "
                    f"mechanism {cell.get('mech')}"
                ),
                check_value=cell.get("score"),
                value_max=cell.get("years"),
                unit="score",
                keyword=material,
                property_name=medium,
                confidence=1.0 if cell.get("conf") == "established" else 0.5,
                needs_review=cell.get("conf") != "established",
                source_text=f"Source: {cell.get('cite', '')}",
                parameters=json.dumps({**cell, "material": material, "medium": medium}),
            )

    # ── Environment severity classes ──────────────────────────────────────────
    for env_key, data in params.get("environment_severity", {}).items():
        if env_key.startswith("_") or not isinstance(data, dict):
            continue
        _r(
            reference=f"MM-001.ENV.{env_key}",
            rule_type="environment_severity",
            rule_category="reference_config",
            description=f"{env_key}: environment severity {data.get('severity')}",
            check_value=data.get("severity"),
            keyword=env_key,
            source_text=f"Source: {data.get('cite', '')}",
            parameters=json.dumps({**data, "class_key": env_key}),
        )

    # ── Temperature stress bands ──────────────────────────────────────────────
    temp = params.get("temperature_stress", {})
    for index, band in enumerate(temp.get("bands", []) or []):
        if not isinstance(band, dict):
            continue
        low = band.get("min_c")
        high = band.get("max_c")
        _r(
            reference=f"MM-001.TEMP.B{index + 1}",
            rule_type="temperature_stress_band",
            rule_category="threshold_band",
            description=(
                f"Operating temperature {low if low is not None else '-inf'}"
                f"–{high if high is not None else '+inf'} °C: "
                f"temperature stress {band.get('stress')}"
            ),
            check_value=band.get("stress"),
            value_min=low,
            value_max=high,
            operator="between",
            unit="°C",
            source_text=f"Source: {band.get('cite', '')}",
            parameters=json.dumps({**band, "band_index": index + 1}),
        )

    if temp.get("missing_temperature_policy"):
        _r(
            reference="MM-001.TEMP.MISSING_POLICY",
            rule_type="data_quality_policy",
            rule_category="reference_config",
            description=str(temp["missing_temperature_policy"]),
            severity="informational",
            parameters=json.dumps({"policy": temp["missing_temperature_policy"]}),
        )

    # ── Kinetics guard ────────────────────────────────────────────────────────
    guard = params.get("kinetics_guard")
    if isinstance(guard, dict):
        _r(
            reference="MM-001.KINETICS_GUARD",
            rule_type="kinetics_guard",
            rule_category="reference_config",
            description=(
                f"Cells scoring below {guard.get('cell_below')} cap temperature stress at "
                f"{guard.get('cap_temperature_stress_at')}"
            ),
            check_value=guard.get("cell_below"),
            value_max=guard.get("cap_temperature_stress_at"),
            operator="<",
            source_text=f"Source: {guard.get('cite', '')}",
            parameters=json.dumps(guard),
        )

    # ── Unmapped pairing policy ───────────────────────────────────────────────
    if meta.get("unmapped_pairing_policy"):
        _r(
            reference="MM-001.UNMAPPED_PAIRING_POLICY",
            rule_type="data_quality_policy",
            rule_category="reference_config",
            description=str(meta["unmapped_pairing_policy"]),
            severity="informational",
            parameters=json.dumps({"policy": meta["unmapped_pairing_policy"]}),
        )

    print(f"[RulesetSeeder] MM-001: {count} rules seeded")
    return count


# ── XM-001 — Cross-Material Contamination ─────────────────────────────────────


def _seed_xm001(svc: RuleService) -> int:
    """Decompose the XM-001 cross-material pack into individual rule rows."""
    RULESET_ID = "BIMGUARD-XM-001"
    existing = _existing_references(svc, RULESET_ID)

    xm = _load("xm_001_cross_material.json")
    params = xm.get("parameters", {})
    meta = xm.get("metadata", {})
    TARGET = "IfcPipeFitting"
    MECH = "XM-001"
    count = 0

    def _r(**kw):
        nonlocal count
        if kw.get("reference") in existing:
            return
        _create(svc, mechanism=MECH, ruleset_id=RULESET_ID, target_ifc_class=TARGET, **kw)
        existing.add(kw["reference"])
        count += 1

    # ── Scoring model ─────────────────────────────────────────────────────────
    weights = params.get("weights", {})
    _r(
        reference="XM-001.SCORING",
        rule_type="scoring_model",
        rule_category="scoring_model",
        description=(
            f"XM-001 composite = {weights.get('voltage')}*voltage_risk + "
            f"{weights.get('separation')}*separation_risk + "
            f"{weights.get('environment')}*environment_risk"
        ),
        source_text="; ".join(str(s) for s in meta.get("standards", [])),
        parameters=json.dumps({"weights": weights}),
    )

    # ── Risk band thresholds ──────────────────────────────────────────────────
    count += _seed_band_thresholds(
        svc,
        ruleset_id=RULESET_ID,
        prefix="XM-001",
        mechanism=MECH,
        target_ifc_class=TARGET,
        thresholds=params.get("risk_band_thresholds", {}),
        existing=existing,
    )

    # ── Environment → threshold class mapping ─────────────────────────────────
    env_map = params.get("environment_threshold_class", {})
    env_cite = str(env_map.get("cite", ""))
    for env_key, value in env_map.items():
        if env_key.startswith("_") or env_key in {"cite", "conf"}:
            continue
        _r(
            reference=f"XM-001.ENV.{env_key}",
            rule_type="environment_threshold_class",
            rule_category="reference_config",
            description=f"{env_key} maps to the '{value}' galvanic compatibility threshold class",
            keyword=env_key,
            check_value=value,
            source_text=f"Source: {env_cite}",
            parameters=json.dumps({"class_key": env_key, "threshold_class": value}),
        )

    # ── Separation factors ────────────────────────────────────────────────────
    for sep_key, data in params.get("separation_factors", {}).items():
        if sep_key.startswith("_") or not isinstance(data, dict):
            continue
        _r(
            reference=f"XM-001.SEPARATION.{sep_key.upper()}",
            rule_type="separation_factor",
            rule_category="threshold_band",
            description=f"Separation '{sep_key}': coupling factor {data.get('factor')}",
            check_value=data.get("factor"),
            keyword=sep_key,
            source_text=f"Source: {data.get('cite', '')}",
            parameters=json.dumps({**data, "separation_key": sep_key}),
        )

    # ── Mitigation factors by joint type ──────────────────────────────────────
    for mit_key, data in params.get("mitigation_factors", {}).items():
        if not isinstance(data, dict):
            continue
        _r(
            reference=f"XM-001.MITIGATION.{mit_key.strip('_').upper()}",
            rule_type="mitigation_factor",
            rule_category="mitigation",
            description=(
                f"{data.get('label', mit_key)}: applies mitigation factor {data.get('factor')}"
            ),
            check_value=data.get("factor"),
            keyword=mit_key,
            severity="recommended",
            source_text=f"Source: {data.get('cite', '')}",
            parameters=json.dumps({**data, "mitigation_key": mit_key}),
        )

    # ── Single-value configuration entries ────────────────────────────────────
    config_entries = (
        ("VOLTAGE_NORMALISATION", "voltage_normalisation_v", "voltage_normalisation", "V"),
        ("SERIES_CONVENTION", "series_convention", "series_convention", ""),
        ("COMPATIBILITY_FLOOR", "compatibility_floor", "compatibility_floor", ""),
        ("REPORT_ALL_COUPLES", "report_all_couples", "reporting_policy", ""),
    )
    for ref_key, param_key, rule_type, unit in config_entries:
        data = params.get(param_key)
        if not isinstance(data, dict):
            continue
        value = data.get("value", data.get("enabled"))
        note = str(data.get("note") or "")
        if not note:
            rationale = data.get("rationale")
            if isinstance(rationale, list):
                note = " ".join(str(line) for line in rationale if line).strip()
        _r(
            reference=f"XM-001.{ref_key}",
            rule_type=rule_type,
            rule_category="reference_config",
            description=f"{param_key} = {value}. {note}".strip(),
            check_value=value,
            unit=unit,
            keyword=param_key,
            source_text=f"Source: {data.get('cite', '')}",
            parameters=json.dumps(data),
        )

    print(f"[RulesetSeeder] XM-001: {count} rules seeded")
    return count


# ── Public entry point ────────────────────────────────────────────────────────


def seed_engine_rulesets(svc: RuleService) -> dict[str, int]:
    """Seed every engine ruleset the application ships with.

    Covers GC-001, CC-001, MC-001, MM-001, XM-001, the architectural code
    rules and the Blue Halo seismic rules.

    Idempotent: skips any ruleset already present in the DB.
    Returns a dict of {ruleset_id: rows_inserted}.
    """
    seeders = (
        ("BIMGUARD-GC-001", _seed_gc001),
        ("BIMGUARD-CC-001", _seed_cc001),
        ("BIMGUARD-MC-001", _seed_mc001),
        ("BIMGUARD-MM-001", _seed_mm001),
        ("BIMGUARD-XM-001", _seed_xm001),
        ("BUILDING-CODE-PART9-ARCH", seed_architectural_code_rules),
        ("BIMGUARD-SB-001", seed_seismic_rules),
    )

    # Isolated per ruleset. A shared try/except let one unreachable static
    # asset abort every seeder after it: a missing GC-001 payload took CC-001,
    # MC-001, the architectural rules and the seismic rules down with it, so
    # the rules catalogue showed no Piping or seismic folders and the cause
    # was a single warning line.
    seeded: dict[str, int] = {}
    for ruleset_id, seeder in seeders:
        try:
            seeded[ruleset_id] = seeder(svc)
        except Exception as exc:
            print(f"[RulesetSeeder] Warning: {ruleset_id} not seeded: {exc}")
    return seeded
