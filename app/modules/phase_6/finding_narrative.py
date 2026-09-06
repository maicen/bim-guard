"""Deterministic Finding Report narratives for the corrosion mechanisms.

Why this module exists
----------------------
Until now a scored finding carried the description ``"MC-001 assessed this
element as critical."`` — the band restated, and nothing a reviewer could act
on. Every input that produced the verdict (the class each term fell into, the
value that put it there, the threshold it crossed, the standard behind the
class, the weights, the composite and the band boundary) existed at scoring
time and was then discarded. This module rebuilds the sentence from those
inputs.

Everything here is template-based and deterministic: same inputs, same string,
no LLM, no network. Values come from the element and the engine result;
labels, thresholds, standards, weights and band boundaries come from the
ruleset catalog. Nothing is invented — where an input is absent the sentence
says so, because a narrative that silently drops the term it could not read is
indistinguishable from one where the term was fine.

MM-001 and XM-001 already author rich descriptions inside their comparators.
Their builders here restate the same facts in the shared house style, sourced
from the metadata those comparators publish, so all five engines read alike.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

#: Mitigation references look like ``MIT-GC-004`` / ``MIT-MIC-001``.
_MIT_CODE = re.compile(r"^MIT-[A-Z]{2,3}-\d{3}$")

#: Score terms each engine weights, and the words in a mitigation's catalogue
#: text that mark it as addressing that term. Used to fill ``addresses``, which
#: the mitigation catalogue itself does not carry (it is ``{code: description}``
#: and nothing more).
_TERM_KEYWORDS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "GC-001": (
        ("voltage_risk", ("dielectric", "isolation", "spacer", "sleeve", "separation", "continuity")),
        ("area_ratio_risk", ("area", "ratio")),
        ("environment_multiplier", ("environment", "zone", "moisture", "ventilation")),
        ("pren_adequacy", ("pren", "grade", "ss304", "ss316", "stainless")),
    ),
    "CC-001": (
        ("geometry_risk", ("joint", "geometry", "gasket", "flange", "weld", "thread")),
        ("CCT_adequacy", ("cct", "grade", "duplex", "titanium", "temperature")),
        ("environment_severity", ("chloride", "environment", "ventilation", "drainage")),
    ),
    "MC-001": (
        ("flow_velocity_risk", ("velocity", "flow", "flush", "dead-leg", "dead leg", "through-flow")),
        ("temperature_risk", ("temperature", "60", "55", "20", "thermal", "pasteuris")),
        ("dead_leg_risk", ("dead-leg", "dead leg", "reconfigure")),
        ("material_susceptibility", ("copper", "cpvc", "material", "substitution")),
        ("under_insulation_risk", ("insulation",)),
    ),
}


# ── formatting helpers ────────────────────────────────────────────────────────


def _num(value: Any, unit: str = "", places: int = 2) -> str | None:
    """Format a measured number with its unit, or ``None`` when unreadable."""
    if value is None:
        return None
    try:
        text = f"{float(value):.{places}f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return None
    return f"{text or '0'} {unit}".strip()


def _absent(term: str) -> str:
    """Phrase for an input the model did not carry."""
    return f"{term} not recorded in the model; default applied"


def _class_ref(table: Mapping[str, Any], key: str) -> str:
    """Return the standard a class comes from, as published in the catalog."""
    entry = table.get(key) if isinstance(table, Mapping) else None
    if isinstance(entry, Mapping):
        ref = entry.get("reference") or ""
        return str(ref)
    return ""


def _class_label(table: Mapping[str, Any], key: str, field: str = "label") -> str:
    entry = table.get(key) if isinstance(table, Mapping) else None
    if isinstance(entry, Mapping):
        return str(entry.get(field) or "")
    return ""


def _band_sentence(issue: Any, catalog: Mapping[str, Any]) -> str:
    """Close every description with the composite against its band boundary.

    MC-001 currently publishes only a Critical boundary — its Medium and High
    ranges use an en dash the parsers do not split on — so a Medium finding has
    no numeric boundary to quote. Saying that is better than quoting a boundary
    that is not there.
    """
    metadata = getattr(issue, "metadata", None) or {}
    version = str(metadata.get("ruleset_version") or "").strip()
    band = getattr(getattr(issue, "band", None), "value", "") or ""
    score = _num(getattr(issue, "score", None), places=3) or "not scored"
    thresholds = (catalog or {}).get("risk_band_thresholds") or {}
    boundary = thresholds.get(band)
    suffix = f" ({version})" if version else ""
    if boundary is None:
        return (
            f"Composite {score} banded {band.title()}; no numeric boundary is "
            f"published for this band{suffix}."
        )
    return f"Composite {score} against the {band.title()} boundary {boundary}{suffix}."


# ── per-engine description builders ───────────────────────────────────────────


def _describe_mc(issue, catalog, m: Mapping[str, Any]) -> str:
    flow_tbl = catalog.get("flow_velocity_classes") or {}
    temp_tbl = catalog.get("temperature_classes") or {}
    dl_tbl = catalog.get("dead_leg_classes") or {}

    flow_key = str(m.get("flow_velocity_class") or "")
    velocity = _num(m.get("flow_velocity_ms"), "m/s")
    flow_ref = _class_ref(flow_tbl, flow_key)
    flow_label = _class_label(flow_tbl, flow_key) or flow_key
    threshold = _num(_class_threshold(flow_tbl, flow_key), "m/s")
    if velocity:
        flow_txt = f"Flow velocity {velocity} classifies as {flow_label.lower()} ({flow_key}"
        if threshold:
            flow_txt += f", at or below the {threshold} threshold"
    else:
        flow_txt = f"Flow velocity {_absent('flow velocity')}, classified {flow_label.lower()} ({flow_key}"
    flow_txt += f", {flow_ref})" if flow_ref else ")"

    temp_key = str(m.get("temperature_class") or "")
    temp = _num(m.get("operating_temp_c"), "°C")
    temp_range = _class_label(temp_tbl, temp_key, "range") or ""
    temp_ref = _class_ref(temp_tbl, temp_key)
    if temp:
        temp_txt = f"operating temperature {temp} lies in the {temp_range} band ({temp_key}"
    else:
        temp_txt = f"operating temperature {_absent('temperature')}, classified {temp_key} ({temp_range}"
    temp_txt += f", {temp_ref})" if temp_ref else ")"

    dl_key = str(m.get("dead_leg_class") or "")
    dl_label = _class_label(dl_tbl, dl_key) or dl_key
    dl_ratio = _class_label(dl_tbl, dl_key, "length_to_dia_ratio")
    dl_ref = _class_ref(dl_tbl, dl_key)
    dl_len = _num(m.get("dead_leg_length_m"), "m")
    dl_txt = f"the branch is {dl_label.lower()}"
    if dl_len:
        dl_txt += f" at {dl_len}"
    if dl_ratio:
        dl_txt += f" ({dl_key}, {dl_ratio} diameters"
        dl_txt += f", {dl_ref})" if dl_ref else ")"
    else:
        dl_txt += f" ({dl_key})"

    material = str(m.get("material_label") or "").strip()
    if not material or str(m.get("material_source") or "") == "absent":
        mat_txt = (
            " Material not recorded in the model; default susceptibility applied."
        )
    else:
        mat_txt = f" Material {material} carries the biofilm susceptibility term."

    return f"{flow_txt}; {temp_txt}; {dl_txt}.{mat_txt} {_band_sentence(issue, catalog)}"


def _class_threshold(table: Mapping[str, Any], key: str) -> Any:
    entry = table.get(key) if isinstance(table, Mapping) else None
    if isinstance(entry, Mapping):
        return entry.get("threshold_ms")
    return None


def _describe_gc(issue, catalog, m: Mapping[str, Any]) -> str:
    env_tbl = catalog.get("environment_classes") or {}
    env_key = str(m.get("environment_class") or "")
    env_label = _class_label(env_tbl, env_key) or str(m.get("environment_label") or env_key)

    anode = str(m.get("material_anode_label") or "").strip()
    cathode = str(m.get("material_cathode_label") or "").strip()
    gap = _num(m.get("voltage_gap_v"), "V", places=3)
    threshold = _num(m.get("env_threshold_v"), "V", places=3)

    if anode and cathode:
        pair_txt = f"{anode} coupled to {cathode}"
    else:
        pair_txt = f"Couple {_absent('second material')}"
    if gap and threshold:
        volt_txt = (
            f"{pair_txt} gives a {gap} potential gap against the {threshold} "
            f"threshold for {env_label} ({env_key}, NASA-STD-6012)"
        )
    else:
        volt_txt = f"{pair_txt} in {env_label} ({env_key}); potential gap not resolved"

    ratio = _num(m.get("area_ratio"), places=3)
    band = str(m.get("area_ratio_band") or "")
    if ratio:
        area_txt = f"anode/cathode area ratio {ratio} bands as {band}"
    else:
        area_txt = f"area ratio {_absent('surface areas')}, banded {band}"

    basis = str(m.get("galvanic_couple") or "").strip()
    basis_txt = f" Couple basis: {basis.replace('_', ' ')}." if basis else ""

    pren_note = str(m.get("pren_note") or "").strip()
    if pren_note and not pren_note.endswith((".", "!", "?")):
        pren_note += "."
    pren_txt = f" {pren_note}" if pren_note else ""

    return f"{volt_txt}; {area_txt}.{basis_txt}{pren_txt} {_band_sentence(issue, catalog)}"


def _describe_cc(issue, catalog, m: Mapping[str, Any]) -> str:
    geom_tbl = catalog.get("geometry_classes") or {}
    env_tbl = catalog.get("environment_severity") or {}

    joint = str(m.get("joint_type_label") or "").strip()
    geom = str(m.get("geometry_class") or "")
    geom_desc = _class_label(geom_tbl, geom, "description")
    joint_txt = f"Joint {joint or 'type not resolved'} classifies as {geom} geometry"
    if geom_desc:
        joint_txt += f" ({geom_desc}, EN ISO 15329:2007)"

    material = str(m.get("material_label") or "").strip()
    cct = _num(m.get("cct_value_c"), "°C", places=1)
    temp = _num(m.get("operating_temp_c"), "°C", places=1)
    if cct and temp:
        cct_txt = (
            f"{material or 'the specified grade'} has a critical crevice "
            f"temperature of {cct} against an operating temperature of {temp} "
            f"(ASTM G48 Method B)"
        )
    else:
        cct_txt = (
            f"critical crevice temperature {_absent('material grade')} for "
            f"{material or 'the specified grade'}"
        )

    env_key = str(m.get("environment_severity_key") or "")
    env_label = _class_label(env_tbl, env_key) or str(m.get("environment_severity_label") or env_key)
    chloride = _class_label(env_tbl, env_key, "chloride_mgl")
    env_txt = f"environment severity {env_label} ({env_key}"
    env_txt += f", chloride {chloride} mg/l)" if chloride else ")"

    return f"{joint_txt}; {cct_txt}; {env_txt}. {_band_sentence(issue, catalog)}"


def _describe_mm(issue, catalog, m: Mapping[str, Any]) -> str:
    material = str(m.get("material") or "").strip() or "material not recorded"
    medium = str(m.get("medium") or "").strip() or "medium not recorded"
    env = str(m.get("environment_class") or "")
    compat = _num(m.get("compatibility_score"), places=2)
    severity = _num(m.get("environment_severity"), places=2)
    temp = _num(m.get("operating_temperature_c"), "°C", places=1)
    stress = _num(m.get("temperature_stress"), places=2)
    mechanism = str(m.get("failure_mechanism") or "").replace("_", " ").strip()
    lifespan = str(m.get("predicted_lifespan_years") or "").strip()

    cell_txt = (
        f"{material} carrying {medium} matches a compatibility cell scoring "
        f"{compat or 'not scored'}"
    )
    if mechanism:
        cell_txt += f", failure mode {mechanism}"
    env_txt = f"environment {env} contributes severity {severity or 'not scored'}"
    temp_txt = (
        f"operating temperature {temp} contributes stress {stress or 'not scored'}"
        if temp
        else f"operating temperature {_absent('temperature')}"
    )
    life_txt = f" Predicted lifespan at this pairing alone: {lifespan} years." if lifespan else ""

    return f"{cell_txt}; {env_txt}; {temp_txt}.{life_txt} {_band_sentence(issue, catalog)}"


def _describe_xm(issue, catalog, m: Mapping[str, Any]) -> str:
    anode = str(m.get("anode_material") or "").strip() or "material not recorded"
    cathode = str(m.get("cathode_material") or "").strip() or "material not recorded"
    anode_id = str(m.get("anode_id") or "").strip()
    cathode_id = str(m.get("cathode_id") or "").strip()
    gap = _num(m.get("voltage_gap_v"), "V", places=3)
    separation = str(m.get("separation") or "").replace("_", " ").strip()
    sep_factor = _num(m.get("separation_factor"), places=2)
    env = str(m.get("environment_class") or "")
    severity = _num(m.get("environment_severity"), places=2)
    mitigated = str(m.get("mitigated") or "").strip().lower() == "true"

    pair = f"{anode}"
    if anode_id:
        pair += f" ({anode_id})"
    pair += f" sacrifices to {cathode}"
    if cathode_id:
        pair += f" ({cathode_id})"

    gap_txt = f"{pair} across a {gap or 'unresolved'} potential gap (GC-001 galvanic series)"
    joint_txt = (
        f"the joint is {separation or 'of unrecorded type'} "
        f"(separation factor {sep_factor or 'not scored'}, BS 8539)"
    )
    env_txt = f"environment {env} contributes severity {severity or 'not scored'}"
    mit_txt = " The pairing is unmitigated." if not mitigated else " A mitigation factor is applied."

    return f"{gap_txt}; {joint_txt}; {env_txt}.{mit_txt} {_band_sentence(issue, catalog)}"


_DESCRIBERS = {
    "GC-001": _describe_gc,
    "CC-001": _describe_cc,
    "MC-001": _describe_mc,
    "MM-001": _describe_mm,
    "XM-001": _describe_xm,
}


# ── public API ────────────────────────────────────────────────────────────────


def build_description(issue, catalog: Mapping[str, Any] | None = None, measurements=None) -> str:
    """Return the technical explanation of why this element was banded.

    Args:
        issue: The finished :class:`Issue`. Supplies band, score and
            ``metadata["mechanism_code"]`` / ``["ruleset_version"]``.
        catalog: The mechanism's rule catalog, for class labels, thresholds,
            standards and the band boundary.
        measurements: The scored inputs. ``_finding_issue`` passes these from
            the element and engine result, which hold the raw values the Issue
            itself does not carry. Defaults to ``issue.metadata``, which is what
            the network mechanisms (MM-001, XM-001) already publish.

    Returns:
        The narrative, or the issue's existing description when the mechanism
        has no builder (data-quality notes keep their own text).
    """
    metadata = getattr(issue, "metadata", None) or {}
    code = str(metadata.get("mechanism_code") or "")
    builder = _DESCRIBERS.get(code)
    if builder is None:
        return str(getattr(issue, "description", "") or "")
    values: Mapping[str, Any] = measurements if measurements is not None else metadata
    try:
        return builder(issue, catalog or {}, values)
    except Exception:
        # A narrative is an explanation, not a verdict. If one cannot be built
        # the finding must still stand, with the description it already had.
        return str(getattr(issue, "description", "") or "")


def _title_from(description: str) -> str:
    """Derive a short title from the catalogue text, without inventing wording."""
    head = re.split(r"\s+[—–-]\s+", description.strip(), maxsplit=1)[0]
    head = head.split(",")[0].strip()
    if len(head) > 70:
        # Cut on a word boundary: a title ending mid-word reads as corruption,
        # and the full text is shown directly beneath it anyway.
        head = head[:70].rsplit(" ", 1)[0].rstrip(" -—–/")
    return head or "Mitigation"


def _addresses(code: str, description: str, mechanism: str) -> str:
    """Name the score term this mitigation acts on, by the catalogue's own words."""
    text = description.lower()
    for term, keywords in _TERM_KEYWORDS.get(mechanism, ()):  # ordered, first match wins
        if any(word in text for word in keywords):
            return term
    return ""


def build_mitigations(issue, catalog: Mapping[str, Any] | None = None) -> list[dict]:
    """Resolve this finding's mitigation references to catalogue text.

    An unrecognised code yields ``{"code": ..., "title": "Unlisted mitigation",
    "description": ""}`` rather than raising: a mitigation catalogue that has
    drifted behind the engines must not take the whole Finding Report down.
    Free prose (which MM-001 and XM-001 emit instead of codes) is passed
    through as a single recommended action.
    """
    raw = str(getattr(issue, "mitigation", "") or "").strip()
    if not raw:
        return []
    metadata = getattr(issue, "metadata", None) or {}
    mechanism = str(metadata.get("mechanism_code") or "")
    catalogue = (catalog or {}).get("mitigations") or {}

    out: list[dict] = []
    for part in (p.strip() for p in raw.split(";")):
        if not part:
            continue
        if not _MIT_CODE.match(part):
            out.append({"code": "", "title": "Recommended action", "description": part})
            continue
        text = str(catalogue.get(part) or "").strip()
        if not text:
            out.append({"code": part, "title": "Unlisted mitigation", "description": ""})
            continue
        entry = {"code": part, "title": _title_from(text), "description": text}
        term = _addresses(part, text, mechanism)
        if term:
            entry["addresses"] = term
        out.append(entry)
    return out


def measurements_for(code: str, element, result) -> dict:
    """Collect the scored inputs a description needs from element and result.

    Kept here rather than in the orchestrator so that the fields each narrative
    depends on are declared next to the sentence that consumes them. Reads only;
    no engine is touched.
    """

    def g(obj, name, default=None):
        return getattr(obj, name, default)

    if code == "MC-001":
        return {
            "flow_velocity_class": g(result, "flow_velocity_class"),
            "temperature_class": g(result, "temperature_class"),
            "dead_leg_class": g(result, "dead_leg_class"),
            "material_label": g(result, "material_label"),
            "material_source": g(element, "material_source"),
            "flow_velocity_ms": g(element, "flow_velocity_ms"),
            "operating_temp_c": g(element, "operating_temp_c"),
            "dead_leg_length_m": g(element, "dead_leg_length_m"),
        }
    if code == "GC-001":
        return {
            "material_anode_label": g(result, "material_anode_label"),
            "material_cathode_label": g(result, "material_cathode_label"),
            "voltage_gap_v": g(result, "voltage_gap_v"),
            "env_threshold_v": g(result, "env_threshold_v"),
            "environment_class": g(result, "environment_class"),
            "environment_label": g(result, "environment_label"),
            "area_ratio": g(result, "area_ratio"),
            "area_ratio_band": g(result, "area_ratio_band"),
            "pren_note": g(result, "pren_note"),
        }
    if code == "CC-001":
        return {
            "joint_type_label": g(result, "joint_type_label"),
            "geometry_class": g(result, "geometry_class"),
            "material_label": g(result, "material_label"),
            "cct_value_c": g(result, "cct_value_c"),
            "operating_temp_c": g(result, "operating_temp_c"),
            "environment_severity_key": g(result, "environment_severity_key"),
            "environment_severity_label": g(result, "environment_severity_label"),
        }
    return {}
