"""Shared configuration for the document and rule pipeline.

Shared constants for Module 1 and Module 3 pipeline components.
Imported by rule_generator.py, rule_converter.py, and seed-rule loaders.
"""

import os

from app.environment import load_env_file
from app.services.persistence import PersistenceService

load_env_file()

# ── Database ──────────────────────────────────────────────────────────────────
# Supabase is the sole runtime database backend.
DB_BACKEND = PersistenceService.DB_BACKEND

# ── API Keys ──────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
# ── LLM Standardization (Issue #17) ───────────────────────────────────────────
# Unified LLM configuration for all extraction, rule building, and compliance work.
# All modules use these constants instead of hardcoded values.

# Default model: OpenRouter Auto (via LiteLLM).
# The "openrouter/" prefix is the LiteLLM provider route. Precedence matches
# the API-key block above:
# Environment variable > literal default.
DEFAULT_LLM_MODEL = os.environ.get(
    "BIM_GUARD_LLM_MODEL", "openrouter/auto"
)

# Temperature by use case
# 0.1 = deterministic (compliance, rule validation, structured output)
# 0.3 = balanced (free-text summarisation, pattern matching)
#
# Note: every LLM call in the pipeline today parses its reply with json.loads
# against a fixed schema, so all of them use COMPLIANCE_TEMPERATURE — the
# "structured output" arm of the rule above wins over the "extraction" arm.
# Reproducibility matters here: the same source document must yield the same
# rule set across runs for the output to be auditable.
# RULE_EXTRACTION_TEMPERATURE is reserved for future prose-generating calls.
COMPLIANCE_TEMPERATURE = 0.1  # For compliance validation, BCF decisions
RULE_EXTRACTION_TEMPERATURE = 0.3  # Reserved: non-JSON, free-text generation

# Max tokens by context
MAX_TOKENS_RULE_EXTRACTION = 2000  # Rule definitions are concise
MAX_TOKENS_DOCUMENT_PARSING = 4000  # Documents can be larger
MAX_TOKENS_COMPLIANCE = 1000  # Compliance output is structured

# Retry configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_DELAY_SECONDS = 1.0
RETRY_BACKOFF_MULTIPLIER = 2.0  # Exponential backoff: 1s, 2s, 4s

# ── Document parsing (Unstructured Workflow/Jobs API) ─────────────────────────
# Primary document-text extraction engine (async job per document, several to
# tens of seconds). When UNSTRUCTURED_API_KEY is unset, the pipeline falls
# back to LightExtractor (pypdf/python-docx/openpyxl/csv — no upload, no ML
# models, effectively instant). See module1_doc_parser/document_extractor.py.
UNSTRUCTURED_API_KEY = os.environ.get("UNSTRUCTURED_API_KEY", "")
UNSTRUCTURED_API_URL = os.environ.get("UNSTRUCTURED_API_URL", "")
UNSTRUCTURED_STRATEGY = os.environ.get("UNSTRUCTURED_STRATEGY", "auto")
# Base URL of a self-hosted / local open-source unstructured-api container
# (see docker-compose.yml's `unstructured-api` service, profile "unstructured").
# Used only to seed the `parsing_engine_instances` registry on first boot —
# once instances exist in the database, they are the source of truth and
# these env vars are no longer read. e.g. http://localhost:8001 for a host
# process talking to the container's published port, or
# http://unstructured-api:8000 for the bim-guard app container talking to it
# over the compose network.
UNSTRUCTURED_LOCAL_URL = os.environ.get("UNSTRUCTURED_LOCAL_URL", "")

# Hosted Docling Serve instance (https://developer.dcls.saas.ibm.com). A
# second parsing-engine option alongside Unstructured — used only to seed
# the `parsing_engine_instances` registry's "docling-hosted" row on first
# boot; the registry is the source of truth afterwards.
DOCLING_SERVICE_URL = os.environ.get("DOCLING_SERVICE_URL", "")
DOCLING_API_KEY = os.environ.get("DOCLING_API_KEY", "")

# Base URL of a self-hosted docling-serve container (see docker-compose.yml's
# `docling-serve` service, profile "docling"). Same seed-only role as
# UNSTRUCTURED_LOCAL_URL — e.g. http://localhost:5001 for a host process
# talking to the container's published port, or http://docling-serve:5001
# for the bim-guard app container talking to it over the compose network.
DOCLING_LOCAL_URL = os.environ.get("DOCLING_LOCAL_URL", "")

# ── Path B feature flags ─────────────────────────────────────────────────
# Gate the MM-001 and XM-001 comparators independently. Both default OFF.
#
# Two flags, not one: MM-001 is APPROVED v1.0 and runs entirely from disk,
# while XM-001 is still DRAFT and its loader reaches the database for the
# GC-001 galvanic series. They must not be wired on the same switch.
# Set to the string "1" to enable; any other value reads as off.
FEATURE_PATH_B_MM = os.environ.get("FEATURE_PATH_B_MM", "0") == "1"
FEATURE_PATH_B_XM = os.environ.get("FEATURE_PATH_B_XM", "0") == "1"

# Tier 3 geometric adjacency in the piping producer (piping_producer.
# _geometric_adjacency). Feeds XM-001: elements Tiers 1 and 2 cannot resolve
# are skipped as connectivity-indeterminable today, and this tier measures
# real tessellated surface distance to recover them.
#
# A third flag rather than a rider on FEATURE_PATH_B_XM, because the cost
# profile is different in kind: the other two gate which comparators run,
# this one gates a tessellation pass during extraction. A site may want
# XM-001 on and this off on large models.
# Set to the string "1" to enable; any other value reads as off.
FEATURE_XM_GEOMETRIC_ADJACENCY = (
    os.environ.get("FEATURE_XM_GEOMETRIC_ADJACENCY", "0") == "1"
)

# ── Source document labels ────────────────────────────────────────────────────
SOURCE_DOC_PDF = "BuildingCode_PDF"
SOURCE_DOC_SEED = "BuildingCode_Seed"

# ── Operators ─────────────────────────────────────────────────────────────────
VALID_OPERATORS = [
    ">=",
    "<=",
    "==",
    "!=",  # numeric comparisons
    "between",  # numeric range (uses value_min / value_max)
    "exists",  # property must be present
    "not_exists",  # property must be absent (prohibition)
    "matches",  # regex / pattern match
    "conforms_to",  # must conform to a referenced standard
    "field_consistency",  # this element's property must match another property
    # of the same element (optionally after a regex transform) — e.g. a wall's
    # Cod_Object code must match the code embedded in its own Name
    "unique_within_scope",  # this element's property value must not be shared
    # by any other element within the same scope (storey / space / building)
]

# ── Rule types ────────────────────────────────────────────────────────────────
# All 8 types. Validation requirements differ per type — see rule_generator.py.
VALID_RULE_TYPES = [
    "numeric_comparison",  # single threshold  e.g. Width >= 860 mm
    "numeric_range",  # band check        e.g. RiserHeight between 125–200 mm
    "prohibition",  # must NOT be used  e.g. glass blocks as loadbearing
    "standard_conformance",  # must conform to   e.g. ASTM C62 for masonry
    "deemed_to_comply",  # alternative path  e.g. sprinklers in lieu of separation
    "table_lookup",  # value from table  e.g. Table 9.8.4.1 tread depths
    "spatial_clearance",  # clearance check   e.g. headroom >= 1950 mm
    "tiered",  # context-dependent e.g. different widths per occupancy
]

# ── IFC class → plain-language keyword mapping ────────────────────────────────
# Used by _enrich_target() to auto-correct free-text entity names.
# Multi-word phrases must come before their component words so they win first.
CODE_TO_IFC_MAP = {
    # Stairs
    "stair": "IfcStairFlight",
    "step": "IfcStairFlight",
    "flight": "IfcStairFlight",
    "riser": "IfcStairFlight",
    "tread": "IfcStairFlight",
    "nosing": "IfcStairFlight",
    "winder": "IfcStairFlight",
    # Doors
    "door": "IfcDoor",
    "exit": "IfcDoor",
    "egress": "IfcDoor",
    "doorway": "IfcDoor",
    # Windows
    "window": "IfcWindow",
    "skylight": "IfcWindow",
    # Curtain walls / glazing systems (check before "wall" and "glazing")
    "curtain wall": "IfcCurtainWall",
    "curtain-wall": "IfcCurtainWall",
    "glazing system": "IfcCurtainWall",
    "storefront": "IfcCurtainWall",
    "glazing": "IfcCurtainWall",
    # Ramps
    "ramp": "IfcRamp",
    "slope": "IfcRamp",
    # Guards & handrails
    "guard": "IfcRailing",
    "handrail": "IfcRailing",
    "railing": "IfcRailing",
    "balustrade": "IfcRailing",
    # Walls
    "wall": "IfcWall",
    "partition": "IfcWall",
    "firewall": "IfcWall",
    "separation": "IfcWall",
    # Ceilings / soffits
    "suspended ceiling": "IfcCovering",
    "drop ceiling": "IfcCovering",
    "ceiling": "IfcCovering",
    "soffit": "IfcCovering",
    # Roofing
    "roof": "IfcRoof",
    "roofing": "IfcRoof",
    # Slabs / landings
    "slab": "IfcSlab",
    "landing": "IfcSlab",
    "floor": "IfcSlab",
    "platform": "IfcSlab",
    # Spaces / rooms
    "space": "IfcSpace",
    "room": "IfcSpace",
    "corridor": "IfcSpace",
    "zone": "IfcZone",
    # Plumbing fixtures (check multi-word before single-word)
    "water closet": "IfcSanitaryTerminal",
    "floor drain": "IfcSanitaryTerminal",
    "wash basin": "IfcSanitaryTerminal",
    "hand basin": "IfcSanitaryTerminal",
    "toilet": "IfcSanitaryTerminal",
    "lavatory": "IfcSanitaryTerminal",
    "urinal": "IfcSanitaryTerminal",
    "bathtub": "IfcSanitaryTerminal",
    "shower": "IfcSanitaryTerminal",
    "basin": "IfcSanitaryTerminal",
    "sink": "IfcSanitaryTerminal",
    "plumbing fixture": "IfcSanitaryTerminal",
    "sanitary": "IfcSanitaryTerminal",
    # Fire / life safety alarms & detectors (multi-word first)
    "smoke detector": "IfcAlarm",
    "fire alarm": "IfcAlarm",
    "smoke alarm": "IfcAlarm",
    "heat detector": "IfcAlarm",
    "carbon monoxide": "IfcAlarm",
    "co detector": "IfcAlarm",
    "alarm": "IfcAlarm",
    "detector": "IfcSensor",
    "sensor": "IfcSensor",
    # Structural members
    "column": "IfcColumn",
    "footing": "IfcFooting",
    "foundation": "IfcFooting",
    "beam": "IfcBeam",
    "truss": "IfcMember",
    "joist": "IfcMember",
    "rafter": "IfcMember",
    "lintel": "IfcMember",
    "member": "IfcMember",
    # Furniture / casework
    "furniture": "IfcFurnishingElement",
    "workstation": "IfcFurnishingElement",
    "casework": "IfcFurnishingElement",
    "cabinet": "IfcFurnishingElement",
    # MEP
    "sprinkler": "IfcFlowTerminal",
    "diffuser": "IfcFlowTerminal",
    "pipe": "IfcPipeSegment",
    "duct": "IfcDuctSegment",
}

# ── IFC class → default Pset mapping ─────────────────────────────────────────
# Used by _enrich_property_set() to populate property_set when the LLM omits it.
IFC_PROPERTY_SET_MAP = {
    "IfcStairFlight": "Pset_StairFlightCommon",
    "IfcDoor": "Pset_DoorCommon",
    "IfcWindow": "Pset_WindowCommon",
    "IfcRailing": "Pset_RailingCommon",
    "IfcRamp": "Pset_RampCommon",
    "IfcRampFlight": "Pset_RampFlightCommon",
    "IfcSlab": "Pset_SlabCommon",
    "IfcWall": "Pset_WallCommon",
    "IfcCurtainWall": "Pset_CurtainWallCommon",
    "IfcSpace": "Pset_SpaceCommon",
    "IfcCovering": "Pset_CoveringCommon",
    "IfcRoof": "Pset_RoofCommon",
    "IfcColumn": "Pset_ColumnCommon",
    "IfcBeam": "Pset_BeamCommon",
    "IfcMember": "Pset_MemberCommon",
    "IfcFooting": "Pset_FootingCommon",
    "IfcSanitaryTerminal": "Pset_SanitaryTerminalCommon",
    "IfcAlarm": "Pset_AlarmCommon",
    "IfcSensor": "Pset_SensorCommon",
    "IfcFlowTerminal": "Pset_FlowTerminalCommon",
}

# ── Rule type → minimum required fields ──────────────────────────────────────
# Validation in rule_generator.py is driven by this map.
RULE_TYPE_REQUIRED_FIELDS = {
    "numeric_comparison": ["target", "property_name", "operator", "check_value"],
    "numeric_range": ["target", "property_name", "value_min", "value_max"],
    "prohibition": ["target", "desc"],
    "standard_conformance": ["target", "desc"],
    "deemed_to_comply": ["target", "desc"],
    "table_lookup": ["target", "property_name"],
    "spatial_clearance": ["target", "property_name", "operator", "check_value"],
    "tiered": ["target", "desc"],
}
