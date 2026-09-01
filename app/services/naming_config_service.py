"""ISO 19650 information-container naming configuration.

Holds the master code library and the naming conventions documented in
``docs/experimental/ISO19650_FINDINGS_FROM_NAVISWORKS.md``, and reads and writes
each project's chosen setup in ``public.project_naming_config``.

The catalogs below are static because they are the standard, not a policy: the
discipline, volume and level codes come from ISO 19650-1 Annex A and the
suitability codes from ISO 19650-2 Table 1. A project narrows them and adds its
own codes -- that part is per-project data and lives in the database. This
mirrors the source platform, whose master library is commented "never modified
-- project codes are separate".
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from app.logging_config import get_logger
from app.services.db_adapters import DatabaseAdapter
from app.services.persistence import PersistenceService

logger = get_logger(__name__)

_TABLE = "project_naming_config"

_SCHEMA: dict[str, Any] = {
    "id": int,
    "project_id": int,
    "project_code": str,
    "originator_code": str,
    "type_code": str,
    "suitability": str,
    "revision": str,
    "separator": str,
    "date_format": str,
    "class_a": str,
    "class_b": str,
    "active_convention": str,
    "level_codes": list,
    "type_codes": list,
    "discipline_codes": list,
    "volume_codes": list,
    "custom_conventions": list,
    "created_at": str,
    "updated_at": str,
}

# The convention a project is given before it chooses one. Named in the source
# platform as the recommended default because a container name carrying no date
# cannot be ordered without opening it.
DEFAULT_CONVENTION = "iso19650_date"

# -- Catalogs ----------------------------------------------------------------

#: The five conventions, verbatim from the source platform. ``preset`` entries
#: cannot be edited or deleted by a project; a project adds its own alongside.
ISO_CONVENTIONS: list[dict[str, Any]] = [
    {
        "id": "iso19650",
        "name": "ISO 19650-1:2018",
        "preset": True,
        "separator": "_",
        "format": (
            "{project}_{originator}_{volume}_{level}_{type}"
            "_{disciplines}_{sequence}_{status}_{revision}"
        ),
        "description": "Information container name without a date field.",
        "iso_compliant": True,
    },
    {
        "id": "iso19650_date",
        "name": "ISO 19650-1:2018 + Date",
        "preset": True,
        "separator": "_",
        "format": (
            "{project}_{originator}_{volume}_{level}_{type}"
            "_{disciplines}_{sequence}_{status}_{revision}_{date}"
        ),
        "description": "Recommended default. Adds an issue date to the ISO name.",
        "iso_compliant": True,
    },
    {
        "id": "simple",
        "name": "Simple - Source vs Service",
        "preset": True,
        "separator": "_",
        "format": "[{clashType}]_{sourceA}_vs_{system}_{zone}_{date}",
        # Flagged rather than quietly offered: a project that picks this one is
        # naming for a clash-test list, not for a CDE.
        "description": "Not ISO compliant. For clash test names, which have their own limits.",
        "iso_compliant": False,
    },
    {
        "id": "descriptive",
        "name": "Descriptive - Full detail",
        "preset": True,
        "separator": "-",
        "format": "{sourceA}-vs-{sourceB}-[{system}]-{zone}-{date}",
        "description": "Not ISO compliant. Readable at a glance, long.",
        "iso_compliant": False,
    },
    {
        "id": "uniclass",
        "name": "Uniclass 2015",
        "preset": True,
        "separator": "_",
        "format": "{project}_{originator}_{classA}_{classB}_{level}_{sequence}_{date}",
        "description": "Classification-led naming. Requires the Uniclass tokens to be set.",
        "iso_compliant": True,
    },
]

#: Every token a convention format may contain. ``source`` says where a value
#: comes from: the project's own configuration, the code library, or the run
#: that is naming something.
NAMING_TOKENS: list[dict[str, str]] = [
    {"token": "project", "label": "Project code", "source": "config"},
    {"token": "originator", "label": "Originator code", "source": "config"},
    {"token": "volume", "label": "Volume / system", "source": "library"},
    {"token": "level", "label": "Level / location", "source": "library"},
    {"token": "type", "label": "Information type", "source": "config"},
    {"token": "disciplines", "label": "Discipline(s)", "source": "library"},
    {"token": "disciplineA", "label": "Discipline A", "source": "library"},
    {"token": "disciplineB", "label": "Discipline B", "source": "library"},
    {"token": "sequence", "label": "Sequence number", "source": "runtime"},
    {"token": "status", "label": "Suitability / CDE status", "source": "config"},
    {"token": "revision", "label": "Revision", "source": "config"},
    {"token": "date", "label": "Date", "source": "runtime"},
    {"token": "sourceA", "label": "Clash source A", "source": "runtime"},
    {"token": "sourceB", "label": "Clash source B", "source": "runtime"},
    {"token": "system", "label": "System", "source": "runtime"},
    {"token": "zone", "label": "Zone", "source": "runtime"},
    {"token": "clashType", "label": "Clash type tag", "source": "runtime"},
    {"token": "classA", "label": "Uniclass primary", "source": "config"},
    {"token": "classB", "label": "Uniclass secondary", "source": "config"},
]

#: strftime patterns for the five offered date formats.
DATE_FORMATS: dict[str, str] = {
    "YYMMDD": "%y%m%d",
    "DDMMYY": "%d%m%y",
    "YYYYMMDD": "%Y%m%d",
    "DD-MM-YY": "%d-%m-%y",
    "ISO": "%Y-%m-%d",
}

#: ISO 19650-2 Table 1. ``selectable`` marks the five a project may set as its
#: suitability; B and S7 are reference rows, as in the source platform.
CDE_STATUS_CODES: list[dict[str, Any]] = [
    {"code": "S0", "label": "Work in progress", "colour": "#94A3B8", "selectable": True},
    {"code": "S1", "label": "Suitable for coordination", "colour": "#FF8000", "selectable": True},
    {"code": "S2", "label": "Suitable for information", "colour": "#00AEEF", "selectable": True},
    {"code": "S3", "label": "Suitable for review", "colour": "#2563EB", "selectable": True},
    {"code": "A", "label": "Authorised for use", "colour": "#00B050", "selectable": True},
    {"code": "B", "label": "Partially authorised", "colour": "#FFC000", "selectable": False},
    {"code": "S7", "label": "Archived / superseded", "colour": "#6B7280", "selectable": False},
]

#: The master library. Cited in the source platform as ISO 19650-1 s12, Annex A.
ISO_MASTER_CODES: dict[str, list[dict[str, str]]] = {
    "disciplines": [
        {"code": "S", "label": "Structural"},
        {"code": "M", "label": "MEP / Mechanical"},
        {"code": "A", "label": "Architectural"},
        {"code": "E", "label": "Electrical"},
        {"code": "C", "label": "Civil"},
        {"code": "F", "label": "Fire Protection"},
        {"code": "G", "label": "Geotechnical"},
        {"code": "L", "label": "Landscape"},
        {"code": "I", "label": "Interior Design"},
        {"code": "P", "label": "Public Health / Plumbing"},
        {"code": "T", "label": "Telecommunications"},
        {"code": "X", "label": "External Works"},
    ],
    "volumes": [
        {"code": "ZZ", "label": "Multi-system / All"},
        {"code": "10", "label": "Structural Frame"},
        {"code": "20", "label": "Architectural"},
        {"code": "30", "label": "MEP Services"},
        {"code": "40", "label": "Electrical"},
        {"code": "50", "label": "Civil / External"},
        {"code": "60", "label": "Facade / Envelope"},
        {"code": "70", "label": "Infrastructure"},
        {"code": "XX", "label": "Not applicable"},
    ],
    "levels": [
        {"code": "ZZ", "label": "All levels"},
        {"code": "B03", "label": "Basement 3"},
        {"code": "B02", "label": "Basement 2"},
        {"code": "B01", "label": "Basement 1"},
        {"code": "G00", "label": "Ground"},
        {"code": "M00", "label": "Mezzanine"},
        *({"code": f"L{n:02d}", "label": f"Level {n}"} for n in range(1, 11)),
        {"code": "RF", "label": "Roof"},
        {"code": "XX", "label": "Not applicable"},
    ],
    # Only three, because only three are documented in the source platform. A
    # project that needs DR, SH or M3 adds them as custom codes rather than
    # waiting on this list, which is what the per-project arrays are for.
    "types": [
        {"code": "CO", "label": "Coordination"},
        {"code": "RP", "label": "Report"},
        {"code": "MO", "label": "Model"},
    ],
}

#: Separators a convention may use.
SEPARATORS = ["_", "-", "."]

# Sample values for the tokens no configuration supplies. A preview has to show
# a whole name, and these are what the empty positions stand in as.
_PREVIEW_SAMPLES: dict[str, str] = {
    "volume": "ZZ",
    "level": "G00",
    "disciplines": "A",
    "disciplineA": "A",
    "disciplineB": "S",
    "sequence": "0001",
    "sourceA": "ARCH",
    "sourceB": "STRUCT",
    "system": "HVAC",
    "zone": "L01",
    "clashType": "H",
}

_TOKEN_RE = re.compile(r"\{(\w+)\}")

#: The configuration a project has before it saves one. Returned rather than a
#: 404 so the wizard renders one shape whether or not anything has been saved.
DEFAULTS: dict[str, Any] = {
    "project_code": "",
    "originator_code": "",
    "type_code": "CO",
    "suitability": "S1",
    "revision": "01",
    "separator": "_",
    "date_format": "YYMMDD",
    "class_a": "",
    "class_b": "",
    "active_convention": DEFAULT_CONVENTION,
    "level_codes": [],
    "type_codes": [],
    "discipline_codes": [],
    "volume_codes": [],
    "custom_conventions": [],
}

_WRITABLE = tuple(DEFAULTS)
_JSON_COLUMNS = (
    "level_codes",
    "type_codes",
    "discipline_codes",
    "volume_codes",
    "custom_conventions",
)


def render_date(date_format: str, *, now: datetime | None = None) -> str:
    """Render a date in one of the five offered formats.

    Args:
        date_format: One of the keys of ``DATE_FORMATS``. An unrecognised
            format falls back to YYMMDD rather than raising, so a stored row
            naming a format this build does not know still produces a name.
        now: The moment to render; defaults to the current UTC time.

    Returns:
        The formatted date string.
    """
    moment = now or datetime.now(timezone.utc)
    return moment.strftime(DATE_FORMATS.get(date_format, DATE_FORMATS["YYMMDD"]))


def _coerce_list(value: Any) -> list[Any]:
    """Return a JSON column as a list.

    Supabase hands back JSONB already parsed, SQLite hands back the text it
    stored, and an unset column hands back None. All three have to read as a
    list, and anything that is neither reads as empty rather than raising.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


class NamingConfigService:
    """Read and write a project's ISO 19650 naming configuration."""

    def __init__(self, *, naming_repo: DatabaseAdapter | None = None) -> None:
        """Bind the naming-config table, creating an adapter if none was injected.

        Args:
            naming_repo: Adapter over ``project_naming_config``. Constructed
                from the declared schema when omitted, which is safe before the
                migration has run: the adapter's create() is a no-op and a read
                degrades to defaults.
        """
        self._repo = (
            naming_repo
            if naming_repo is not None
            else PersistenceService.get_table(_TABLE, _SCHEMA)
        )

    # -- catalogs ------------------------------------------------------------

    @staticmethod
    def conventions() -> list[dict[str, Any]]:
        """Return the five preset naming conventions."""
        return [dict(item) for item in ISO_CONVENTIONS]

    @staticmethod
    def master_codes() -> dict[str, list[dict[str, str]]]:
        """Return the master code library: disciplines, volumes, levels, types."""
        return {key: [dict(c) for c in codes] for key, codes in ISO_MASTER_CODES.items()}

    # -- persistence ---------------------------------------------------------

    def _read_row(self, project_id: int) -> dict[str, Any] | None:
        """Return the stored row for a project, or None if there is none.

        The migration is applied out of band, so between a deploy and that
        migration the table legitimately does not exist. Reading it degrades to
        "this project is unconfigured" rather than taking the wizard down, which
        is why the failure is swallowed here and nowhere else.
        """
        try:
            rows = list(self._repo.rows_where("project_id = ?", [project_id]))
        except Exception as exc:  # noqa: BLE001 - a missing table is not a caller's problem
            logger.debug(
                "project_naming_config unavailable project_id=%d error=%s", project_id, exc
            )
            return None
        return rows[0] if rows else None

    def get_for_project(self, project_id: int) -> dict[str, Any]:
        """Return a project's naming configuration, falling back to defaults.

        Args:
            project_id: ``projects.id`` of the project to read.

        Returns:
            The configuration, always whole. An unconfigured project is not an
            error: it reports the defaults with ``is_configured`` false, so a
            caller can render the form either way and can tell a saved blank
            apart from nothing saved.
        """
        row = self._read_row(project_id)
        if row is None:
            return {"project_id": project_id, "is_configured": False, **DEFAULTS}

        merged = {**DEFAULTS, **{k: v for k, v in row.items() if v is not None}}
        for column in _JSON_COLUMNS:
            merged[column] = _coerce_list(merged.get(column))
        merged["project_id"] = project_id
        merged["is_configured"] = True
        return merged

    def save_for_project(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Create or replace a project's naming configuration.

        Args:
            project_id: ``projects.id`` of the project to configure.
            payload: Fields to write. Only the keys present are taken; anything
                else keeps the value already stored, or the default if nothing
                is stored, so a partial save from one tab of the form cannot
                blank the other tabs.

        Returns:
            The configuration as it now stands.
        """
        current = self._read_row(project_id)
        base = {**DEFAULTS, **{k: v for k, v in (current or {}).items() if v is not None}}
        updates = {
            key: payload[key] for key in _WRITABLE if key in payload and payload[key] is not None
        }
        merged = {**base, **updates}
        record = {key: merged[key] for key in _WRITABLE}
        for column in _JSON_COLUMNS:
            record[column] = _coerce_list(record.get(column))
        record["updated_at"] = datetime.now(timezone.utc).isoformat()

        if current is None:
            self._repo.insert({"project_id": project_id, **record})
            logger.info("Created naming config project_id=%d", project_id)
        else:
            self._repo.update(updates=record, pk_values=current.get("id"))
            logger.info("Updated naming config project_id=%d", project_id)
        return self.get_for_project(project_id)

    def delete_for_project(self, project_id: int) -> bool:
        """Drop a project's naming configuration, returning it to defaults.

        Args:
            project_id: ``projects.id`` of the project to reset.

        Returns:
            True if a row was removed, False if the project had none.
        """
        row = self._read_row(project_id)
        if row is None:
            return False
        self._repo.delete(row.get("id"))
        logger.info("Deleted naming config project_id=%d", project_id)
        return True

    # -- rendering -----------------------------------------------------------

    def resolve_convention(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return the convention a configuration names.

        Args:
            config: A configuration, as returned by ``get_for_project``.

        Returns:
            The matching preset or custom convention. A configuration naming one
            that no longer resolves -- a custom convention since deleted --
            falls back to the default rather than failing, matching the source
            platform, which drops a deleted active convention back to
            ``iso19650_date``.
        """
        wanted = str(config.get("active_convention") or DEFAULT_CONVENTION)
        pool = [*ISO_CONVENTIONS, *_coerce_list(config.get("custom_conventions"))]
        for convention in pool:
            if str(convention.get("id")) == wanted:
                return dict(convention)
        logger.debug("Unknown convention %r; falling back to %s", wanted, DEFAULT_CONVENTION)
        return next(c for c in ISO_CONVENTIONS if c["id"] == DEFAULT_CONVENTION)

    def render_name(
        self,
        config: dict[str, Any],
        *,
        overrides: dict[str, str] | None = None,
        now: datetime | None = None,
    ) -> str:
        """Render one information-container name from a configuration.

        Args:
            config: A configuration, as returned by ``get_for_project``.
            overrides: Values for the tokens no configuration supplies, such as
                the sequence number or the two sides of a clash.
            now: The moment the ``{date}`` token renders; defaults to now.

        Returns:
            The rendered name. A token that nothing resolves is left as the
            literal ``{token}`` rather than replaced with nothing: an empty
            segment between two separators is easy to miss, which is how the
            source platform's Uniclass convention shipped producing names with
            two blank fields.
        """
        convention = self.resolve_convention(config)
        separator = str(config.get("separator") or convention.get("separator") or "_")
        values: dict[str, str] = {
            **_PREVIEW_SAMPLES,
            "project": str(config.get("project_code") or "").strip(),
            "originator": str(config.get("originator_code") or "").strip(),
            "type": str(config.get("type_code") or "").strip(),
            "status": str(config.get("suitability") or "").strip(),
            "revision": str(config.get("revision") or "").strip(),
            "classA": str(config.get("class_a") or "").strip(),
            "classB": str(config.get("class_b") or "").strip(),
            "date": render_date(str(config.get("date_format") or "YYMMDD"), now=now),
        }
        values = {key: value for key, value in values.items() if value}
        values.update({k: v for k, v in (overrides or {}).items() if v})

        return _TOKEN_RE.sub(
            lambda match: values.get(match.group(1), match.group(0)),
            self.applied_format(convention, separator),
        )

    @staticmethod
    def applied_format(convention: dict[str, Any], separator: str) -> str:
        """Return a convention's format string written with a project's separator.

        A project has one separator across every name it issues -- that is what
        the ISO base code is for -- so it wins over the separator a convention
        was authored with. Substituting into the format rather than re-joining
        the fields leaves a format's literal text ("_vs_", "[...]") intact.

        Args:
            convention: The convention being applied.
            separator: The separator the project has chosen.

        Returns:
            The format string as it will actually be rendered. Callers show this
            rather than ``convention["format"]``, so the format a form displays
            and the name it previews cannot disagree.
        """
        authored = str(convention.get("separator") or "_")
        if not separator or separator == authored:
            return str(convention["format"])
        return str(convention["format"]).replace(authored, separator)
