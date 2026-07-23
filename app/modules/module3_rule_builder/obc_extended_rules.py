"""
module3_rule_builder/obc_extended_rules.py
--------------------------------------------
Extended OBC Part 9 rules covering elements that can be checked via
IFC property sets without requiring geometry computation.

Seeded under ruleset_id "OBC-PART9-EXT" so they are added independently
of the base "OBC-PART9" ruleset already in the database.
"""

OBC_EXTENDED_RULES = [
    # ── STAIR RISER / TREAD COUNTS ────────────────────────────────────────────
    {
        "ref": "OBC 9.8.3.3.(2)",
        "rule_type": "numeric_comparison",
        "target": "IfcStairFlight",
        "property_name": "NumberOfRiser",
        "property_set": "Pset_StairFlightCommon",
        "operator": "<=",
        "check_value": 21,
        "unit": "count",
        "severity": "mandatory",
        "desc": "Private stair — maximum 21 risers per flight",
    },
    {
        "ref": "OBC 9.8.3.3.(2)",
        "rule_type": "numeric_comparison",
        "target": "IfcStairFlight",
        "property_name": "NumberOfTreads",
        "property_set": "Pset_StairFlightCommon",
        "operator": "<=",
        "check_value": 21,
        "unit": "count",
        "severity": "mandatory",
        "desc": "Private stair — maximum 21 treads per flight",
    },
    # ── DOOR PROPERTIES ──────────────────────────────────────────────────────
    {
        "ref": "OBC 9.10.9",
        "rule_type": "prohibition",
        "target": "IfcDoor",
        "property_name": "FireRating",
        "property_set": "Pset_DoorCommon",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "informational",
        "desc": "Fire-rated doors must have a FireRating property declared",
    },
    {
        "ref": "BIMGuard QA",
        "rule_type": "prohibition",
        "target": "IfcDoor",
        "property_name": "IsExternal",
        "property_set": "Pset_DoorCommon",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "informational",
        "desc": "All doors must declare IsExternal to classify as exit or interior",
    },
    # Spatial-relationship checks (ConnectedSpaceCount is derived from
    # IfcRelSpaceBoundary, not a Pset property — see ifc_spatial.py's
    # check_door_space_connection). Scoped by applies_when.location so each
    # rule only evaluates its own subset of doors; requires IfcSpace/space
    # boundary data in the model to resolve at all.
    {
        "ref": "BIMGuard QA",
        "rule_type": "numeric_comparison",
        "target": "IfcDoor",
        "property_name": "ConnectedSpaceCount",
        "property_set": "",
        "operator": "==",
        "check_value": 2,
        "unit": "count",
        "severity": "mandatory",
        "applies_when": {"location": "interior"},
        "desc": "Interior doors must connect exactly two modeled spaces",
    },
    {
        "ref": "BIMGuard QA",
        "rule_type": "numeric_comparison",
        "target": "IfcDoor",
        "property_name": "ConnectedSpaceCount",
        "property_set": "",
        "operator": "==",
        "check_value": 1,
        "unit": "count",
        "severity": "mandatory",
        "applies_when": {"location": "exterior"},
        "desc": "Exterior doors must connect exactly one modeled interior space",
    },
    # ── WINDOW PROPERTIES ─────────────────────────────────────────────────────
    {
        "ref": "BIMGuard QA",
        "rule_type": "prohibition",
        "target": "IfcWindow",
        "property_name": "IsExternal",
        "property_set": "Pset_WindowCommon",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "informational",
        "desc": "All windows must declare IsExternal for daylight and egress classification",
    },
    # ── WALL PROPERTIES ───────────────────────────────────────────────────────
    {
        "ref": "BIMGuard QA",
        "rule_type": "prohibition",
        "target": "IfcWall",
        "property_name": "IsExternal",
        "property_set": "Pset_WallCommon",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "informational",
        "desc": "All walls must declare IsExternal for spatial separation analysis",
    },
    # ── SPACE / ROOM PROPERTIES ───────────────────────────────────────────────
    {
        "ref": "BIMGuard QA",
        "rule_type": "prohibition",
        "target": "IfcSpace",
        "property_name": "OccupancyType",
        "property_set": "Pset_SpaceCommon",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "informational",
        "desc": "All spaces must have OccupancyType set for compliance classification",
    },
    {
        "ref": "BIMGuard QA",
        "rule_type": "prohibition",
        "target": "IfcSpace",
        "property_name": "NetFloorArea",
        "property_set": "Qto_SpaceBaseQuantities",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "informational",
        "desc": "All spaces must have NetFloorArea for floor-area-ratio calculations",
    },
    # ── PLUMBING FIXTURES ─────────────────────────────────────────────────────
    {
        "ref": "BIMGuard QA",
        "rule_type": "prohibition",
        "target": "IfcSanitaryTerminal",
        "property_name": "PredefinedType",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "informational",
        "desc": "All plumbing fixtures must have PredefinedType set (TOILETPAN, BATH, SHOWER, WASHHANDBASIN, SINK)",
    },
    # ── FIRE / CO ALARMS ─────────────────────────────────────────────────────
    {
        "ref": "OBC 9.10.19",
        "rule_type": "prohibition",
        "target": "IfcAlarm",
        "property_name": "PredefinedType",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "mandatory",
        "desc": "All fire and CO alarms must have PredefinedType set (SMOKEALARM, FIREDETECTOR, CO2SENSOR)",
    },
    # ── RAMP PROPERTIES ───────────────────────────────────────────────────────
    {
        "ref": "OBC 3.8.3.4",
        "rule_type": "prohibition",
        "target": "IfcRamp",
        "property_name": "HasNonSkidSurface",
        "property_set": "Pset_RampCommon",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "informational",
        "desc": "Accessible ramps should declare HasNonSkidSurface for slip-resistance compliance",
    },
    # ── SLAB PROPERTIES ───────────────────────────────────────────────────────
    {
        "ref": "BIMGuard QA",
        "rule_type": "prohibition",
        "target": "IfcSlab",
        "property_name": "IsExternal",
        "property_set": "Pset_SlabCommon",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "informational",
        "desc": "All slabs should declare IsExternal to distinguish roof/floor from internal slab",
    },
    # ── WALL FIRE RESISTANCE (quantitative) ───────────────────────────────────
    {
        "ref": "OBC 9.10.9.14",
        "rule_type": "numeric_comparison",
        "target": "IfcWall",
        "property_name": "FireRating",
        "property_set": "Pset_WallCommon",
        "operator": ">=",
        "check_value": 45,
        "unit": "min",
        "severity": "mandatory",
        "desc": "Party walls between dwelling units — minimum 45-minute fire resistance rating",
    },
    # ── DOOR OPENING DIRECTION QA ─────────────────────────────────────────────
    {
        "ref": "BIMGuard QA",
        "rule_type": "prohibition",
        "target": "IfcDoor",
        "property_name": "OperationType",
        "property_set": "Pset_DoorCommon",
        "operator": "exists",
        "check_value": None,
        "unit": None,
        "severity": "informational",
        "desc": "All doors should declare OperationType (SINGLE_SWING_LEFT, DOUBLE_SWING, etc.)",
    },
]
