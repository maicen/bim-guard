begin;

insert into public.static_data_assets (asset_key, source_path, format, content_json, content_text, content_sha256, migrated_at, active)
values ('ruleset:BUILDING-CODE-PART9', 'data/rulesets/building_code_part9_ruleset.json', 'json', '{"mechanism": "CODE", "rules": [{"check_value": 860, "desc": "Exit stair serving house/dwelling — minimum clear width 860 mm", "operator": ">=", "property_name": "Width", "ref": "9.8.2.1.(2)", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcStairFlight", "unit": "mm"}, {"check_value": 860, "desc": "At least one stair between floor levels — minimum width 860 mm", "operator": ">=", "property_name": "Width", "ref": "9.8.2.1.(4)", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcStairFlight", "unit": "mm"}, {"check_value": 1950, "desc": "Minimum vertical headroom over full stair width — 1950 mm", "operator": ">=", "property_name": "RequiredHeadroom", "ref": "9.8.2.2.(3)", "rule_type": "spatial_clearance", "severity": "mandatory", "target": "IfcStairFlight", "unit": "mm"}, {"check_value": 1950, "desc": "Minimum headroom clearance over stair landings — 1950 mm", "operator": ">=", "property_name": "RequiredHeadroom", "ref": "9.8.2.2.(3)", "rule_type": "spatial_clearance", "severity": "mandatory", "target": "IfcSlab", "unit": "mm"}, {"check_value": null, "desc": "Private stair riser height — min 125 mm, max 200 mm", "operator": "between", "property_name": "RiserHeight", "ref": "Table 9.8.4.1", "rule_type": "numeric_range", "severity": "mandatory", "target": "IfcStairFlight", "unit": "mm", "value_max": 200, "value_min": 125}, {"check_value": null, "desc": "Private stair tread run/depth — min 255 mm, max 355 mm", "operator": "between", "property_name": "TreadLength", "ref": "Table 9.8.4.1", "rule_type": "numeric_range", "severity": "mandatory", "target": "IfcStairFlight", "unit": "mm", "value_max": 355, "value_min": 255}, {"check_value": 3700, "desc": "Maximum vertical height per stair flight — 3700 mm", "operator": "<=", "property_name": "FlightHeight", "ref": "9.8.3.3.(1)", "rule_type": "numeric_comparison", "severity": "recommended", "target": "IfcStairFlight", "unit": "mm"}, {"check_value": 860, "desc": "Landing width must be at minimum equal to stair width — min 860 mm", "operator": ">=", "property_name": "Width", "ref": "9.8.6.3", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcSlab", "unit": "mm"}, {"check_value": 0.02, "desc": "Landing surface slope must not exceed 1:50 (0.02)", "operator": "<=", "property_name": "PitchAngle", "ref": "9.8.6.3", "rule_type": "numeric_comparison", "severity": "recommended", "target": "IfcSlab", "unit": "ratio"}, {"check_value": 90, "desc": "Maximum total winder set turn angle — 90 degrees", "operator": "<=", "property_name": "WinderTurnAngle", "ref": "9.8.4.5.(1)", "rule_type": "numeric_comparison", "severity": "recommended", "target": "IfcStairFlight", "unit": "deg"}, {"check_value": null, "desc": "Each winder tread angle must be between 30° and 45°", "operator": "between", "property_name": "IndividualWinderAngle", "ref": "9.8.4.5.(2)", "rule_type": "numeric_range", "severity": "recommended", "target": "IfcStairFlight", "unit": "deg", "value_max": 45, "value_min": 30}, {"check_value": 1200, "desc": "Minimum plan separation between winder sets — 1200 mm", "operator": ">=", "property_name": "WinderSetSeparation", "ref": "9.8.4.5.(2)", "rule_type": "numeric_comparison", "severity": "recommended", "target": "IfcStairFlight", "unit": "mm"}, {"check_value": 800, "desc": "Egress door minimum clear opening width — 800 mm", "operator": ">=", "property_name": "OverallWidth", "ref": "CODE 9.6.4", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcDoor", "unit": "mm"}, {"check_value": 1980, "desc": "Egress door minimum height — 1980 mm", "operator": ">=", "property_name": "Height", "ref": "CODE 9.6.4", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcDoor", "unit": "mm"}, {"check_value": 900, "desc": "Guard minimum height at floor edges, stairs, landings, balconies — 900 mm", "operator": ">=", "property_name": "Height", "ref": "CODE 9.8.8", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcRailing", "unit": "mm"}, {"check_value": null, "desc": "Handrail height must be between 865 mm and 1070 mm above stair nosings", "operator": "between", "property_name": "HandrailHeight", "ref": "CODE 9.8.7", "rule_type": "numeric_range", "severity": "mandatory", "target": "IfcRailing", "unit": "mm", "value_max": 1070, "value_min": 865}, {"check_value": 0.35, "desc": "Bedroom egress window minimum clear opening area — 0.35 m²", "operator": ">=", "property_name": "Area", "ref": "CODE 9.7.2", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcWindow", "unit": "m2"}, {"check_value": 380, "desc": "Bedroom egress window minimum clear opening height — 380 mm", "operator": ">=", "property_name": "OverallHeight", "ref": "CODE 9.7.2", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcWindow", "unit": "mm"}, {"check_value": 450, "desc": "Bedroom egress window minimum clear opening width — 450 mm", "operator": ">=", "property_name": "OverallWidth", "ref": "CODE 9.7.2", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcWindow", "unit": "mm"}, {"check_value": null, "desc": "Garage-to-dwelling separation walls must have a FireRating property", "operator": "exists", "property_name": "FireRating", "ref": "CODE 9.35", "rule_type": "prohibition", "severity": "mandatory", "target": "IfcWall", "unit": null}, {"check_value": 0, "desc": "Limiting distance from exterior wall face to property line must be calculated", "operator": ">=", "property_name": "LimitingDistance", "ref": "CODE 3.2.3", "rule_type": "spatial_clearance", "severity": "mandatory", "target": "IfcWall", "unit": "m"}, {"check_value": 0.083, "desc": "Accessible ramp slope must not exceed 1:12 (0.083)", "operator": "<=", "property_name": "RequiredSlope", "ref": "CODE 3.8.3.4", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcRamp", "unit": "ratio"}, {"check_value": 1100, "desc": "Accessible ramp clear width minimum — 1100 mm", "operator": ">=", "property_name": "Width", "ref": "CODE 3.8.3.4", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcRamp", "unit": "mm"}, {"check_value": 1100, "desc": "Accessible corridor / aisle minimum clear width — 1100 mm", "operator": ">=", "property_name": "Width", "ref": "CODE 3.8.3.2", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcSpace", "unit": "mm"}, {"check_value": 2400, "desc": "Habitable room minimum ceiling height — 2400 mm", "operator": ">=", "property_name": "Height", "ref": "CODE 9.5.1.1", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcSpace", "unit": "mm"}, {"check_value": 1950, "desc": "Bathroom / utility room minimum ceiling height — 1950 mm", "operator": ">=", "property_name": "Height", "ref": "CODE 9.5.1.2", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcSpace", "unit": "mm"}, {"check_value": null, "desc": "Party walls between dwelling units must have a FireRating property", "operator": "exists", "property_name": "FireRating", "ref": "CODE 9.10.9.13", "rule_type": "prohibition", "severity": "mandatory", "target": "IfcWall", "unit": null}, {"check_value": 45, "desc": "Fire-rated wall between dwelling units — minimum 45-minute fire resistance", "operator": ">=", "property_name": "FireRating", "ref": "CODE 9.10.9.14", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcWall", "unit": "min"}, {"check_value": null, "desc": "All IfcDoor elements must have a Width property — flag if missing", "operator": "exists", "property_name": "Width", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcDoor", "unit": null}, {"check_value": null, "desc": "All rooms/spaces must have a LongName — flag if missing", "operator": "exists", "property_name": "LongName", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcSpace", "unit": null}, {"check_value": null, "desc": "All stair flight elements must have a Name property", "operator": "exists", "property_name": "Name", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcStairFlight", "unit": null}], "ruleset_id": "BUILDING-CODE-PART9"}', '{
  "ruleset_id": "BUILDING-CODE-PART9",
  "mechanism": "CODE",
  "rules": [
    {
      "ref": "9.8.2.1.(2)",
      "rule_type": "numeric_comparison",
      "target": "IfcStairFlight",
      "property_name": "Width",
      "operator": ">=",
      "check_value": 860,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Exit stair serving house/dwelling \u2014 minimum clear width 860 mm"
    },
    {
      "ref": "9.8.2.1.(4)",
      "rule_type": "numeric_comparison",
      "target": "IfcStairFlight",
      "property_name": "Width",
      "operator": ">=",
      "check_value": 860,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "At least one stair between floor levels \u2014 minimum width 860 mm"
    },
    {
      "ref": "9.8.2.2.(3)",
      "rule_type": "spatial_clearance",
      "target": "IfcStairFlight",
      "property_name": "RequiredHeadroom",
      "operator": ">=",
      "check_value": 1950,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Minimum vertical headroom over full stair width \u2014 1950 mm"
    },
    {
      "ref": "9.8.2.2.(3)",
      "rule_type": "spatial_clearance",
      "target": "IfcSlab",
      "property_name": "RequiredHeadroom",
      "operator": ">=",
      "check_value": 1950,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Minimum headroom clearance over stair landings \u2014 1950 mm"
    },
    {
      "ref": "Table 9.8.4.1",
      "rule_type": "numeric_range",
      "target": "IfcStairFlight",
      "property_name": "RiserHeight",
      "operator": "between",
      "check_value": null,
      "value_min": 125,
      "value_max": 200,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Private stair riser height \u2014 min 125 mm, max 200 mm"
    },
    {
      "ref": "Table 9.8.4.1",
      "rule_type": "numeric_range",
      "target": "IfcStairFlight",
      "property_name": "TreadLength",
      "operator": "between",
      "check_value": null,
      "value_min": 255,
      "value_max": 355,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Private stair tread run/depth \u2014 min 255 mm, max 355 mm"
    },
    {
      "ref": "9.8.3.3.(1)",
      "rule_type": "numeric_comparison",
      "target": "IfcStairFlight",
      "property_name": "FlightHeight",
      "operator": "<=",
      "check_value": 3700,
      "unit": "mm",
      "severity": "recommended",
      "desc": "Maximum vertical height per stair flight \u2014 3700 mm"
    },
    {
      "ref": "9.8.6.3",
      "rule_type": "numeric_comparison",
      "target": "IfcSlab",
      "property_name": "Width",
      "operator": ">=",
      "check_value": 860,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Landing width must be at minimum equal to stair width \u2014 min 860 mm"
    },
    {
      "ref": "9.8.6.3",
      "rule_type": "numeric_comparison",
      "target": "IfcSlab",
      "property_name": "PitchAngle",
      "operator": "<=",
      "check_value": 0.02,
      "unit": "ratio",
      "severity": "recommended",
      "desc": "Landing surface slope must not exceed 1:50 (0.02)"
    },
    {
      "ref": "9.8.4.5.(1)",
      "rule_type": "numeric_comparison",
      "target": "IfcStairFlight",
      "property_name": "WinderTurnAngle",
      "operator": "<=",
      "check_value": 90,
      "unit": "deg",
      "severity": "recommended",
      "desc": "Maximum total winder set turn angle \u2014 90 degrees"
    },
    {
      "ref": "9.8.4.5.(2)",
      "rule_type": "numeric_range",
      "target": "IfcStairFlight",
      "property_name": "IndividualWinderAngle",
      "operator": "between",
      "check_value": null,
      "value_min": 30,
      "value_max": 45,
      "unit": "deg",
      "severity": "recommended",
      "desc": "Each winder tread angle must be between 30\u00b0 and 45\u00b0"
    },
    {
      "ref": "9.8.4.5.(2)",
      "rule_type": "numeric_comparison",
      "target": "IfcStairFlight",
      "property_name": "WinderSetSeparation",
      "operator": ">=",
      "check_value": 1200,
      "unit": "mm",
      "severity": "recommended",
      "desc": "Minimum plan separation between winder sets \u2014 1200 mm"
    },
    {
      "ref": "CODE 9.6.4",
      "rule_type": "numeric_comparison",
      "target": "IfcDoor",
      "property_name": "OverallWidth",
      "operator": ">=",
      "check_value": 800,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Egress door minimum clear opening width \u2014 800 mm"
    },
    {
      "ref": "CODE 9.6.4",
      "rule_type": "numeric_comparison",
      "target": "IfcDoor",
      "property_name": "Height",
      "operator": ">=",
      "check_value": 1980,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Egress door minimum height \u2014 1980 mm"
    },
    {
      "ref": "CODE 9.8.8",
      "rule_type": "numeric_comparison",
      "target": "IfcRailing",
      "property_name": "Height",
      "operator": ">=",
      "check_value": 900,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Guard minimum height at floor edges, stairs, landings, balconies \u2014 900 mm"
    },
    {
      "ref": "CODE 9.8.7",
      "rule_type": "numeric_range",
      "target": "IfcRailing",
      "property_name": "HandrailHeight",
      "operator": "between",
      "check_value": null,
      "value_min": 865,
      "value_max": 1070,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Handrail height must be between 865 mm and 1070 mm above stair nosings"
    },
    {
      "ref": "CODE 9.7.2",
      "rule_type": "numeric_comparison",
      "target": "IfcWindow",
      "property_name": "Area",
      "operator": ">=",
      "check_value": 0.35,
      "unit": "m2",
      "severity": "mandatory",
      "desc": "Bedroom egress window minimum clear opening area \u2014 0.35 m\u00b2"
    },
    {
      "ref": "CODE 9.7.2",
      "rule_type": "numeric_comparison",
      "target": "IfcWindow",
      "property_name": "OverallHeight",
      "operator": ">=",
      "check_value": 380,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Bedroom egress window minimum clear opening height \u2014 380 mm"
    },
    {
      "ref": "CODE 9.7.2",
      "rule_type": "numeric_comparison",
      "target": "IfcWindow",
      "property_name": "OverallWidth",
      "operator": ">=",
      "check_value": 450,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Bedroom egress window minimum clear opening width \u2014 450 mm"
    },
    {
      "ref": "CODE 9.35",
      "rule_type": "prohibition",
      "target": "IfcWall",
      "property_name": "FireRating",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "mandatory",
      "desc": "Garage-to-dwelling separation walls must have a FireRating property"
    },
    {
      "ref": "CODE 3.2.3",
      "rule_type": "spatial_clearance",
      "target": "IfcWall",
      "property_name": "LimitingDistance",
      "operator": ">=",
      "check_value": 0,
      "unit": "m",
      "severity": "mandatory",
      "desc": "Limiting distance from exterior wall face to property line must be calculated"
    },
    {
      "ref": "CODE 3.8.3.4",
      "rule_type": "numeric_comparison",
      "target": "IfcRamp",
      "property_name": "RequiredSlope",
      "operator": "<=",
      "check_value": 0.083,
      "unit": "ratio",
      "severity": "mandatory",
      "desc": "Accessible ramp slope must not exceed 1:12 (0.083)"
    },
    {
      "ref": "CODE 3.8.3.4",
      "rule_type": "numeric_comparison",
      "target": "IfcRamp",
      "property_name": "Width",
      "operator": ">=",
      "check_value": 1100,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Accessible ramp clear width minimum \u2014 1100 mm"
    },
    {
      "ref": "CODE 3.8.3.2",
      "rule_type": "numeric_comparison",
      "target": "IfcSpace",
      "property_name": "Width",
      "operator": ">=",
      "check_value": 1100,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Accessible corridor / aisle minimum clear width \u2014 1100 mm"
    },
    {
      "ref": "CODE 9.5.1.1",
      "rule_type": "numeric_comparison",
      "target": "IfcSpace",
      "property_name": "Height",
      "operator": ">=",
      "check_value": 2400,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Habitable room minimum ceiling height \u2014 2400 mm"
    },
    {
      "ref": "CODE 9.5.1.2",
      "rule_type": "numeric_comparison",
      "target": "IfcSpace",
      "property_name": "Height",
      "operator": ">=",
      "check_value": 1950,
      "unit": "mm",
      "severity": "mandatory",
      "desc": "Bathroom / utility room minimum ceiling height \u2014 1950 mm"
    },
    {
      "ref": "CODE 9.10.9.13",
      "rule_type": "prohibition",
      "target": "IfcWall",
      "property_name": "FireRating",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "mandatory",
      "desc": "Party walls between dwelling units must have a FireRating property"
    },
    {
      "ref": "CODE 9.10.9.14",
      "rule_type": "numeric_comparison",
      "target": "IfcWall",
      "property_name": "FireRating",
      "operator": ">=",
      "check_value": 45,
      "unit": "min",
      "severity": "mandatory",
      "desc": "Fire-rated wall between dwelling units \u2014 minimum 45-minute fire resistance"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcDoor",
      "property_name": "Width",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All IfcDoor elements must have a Width property \u2014 flag if missing"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcSpace",
      "property_name": "LongName",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All rooms/spaces must have a LongName \u2014 flag if missing"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcStairFlight",
      "property_name": "Name",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All stair flight elements must have a Name property"
    }
  ]
}
', 'cae02ce04ab35e6babb7abc42b93ffef000d6b4cd150f70efe9e40686aa815f2', '', 1)
on conflict (asset_key) do update set
    source_path = excluded.source_path,
    format = excluded.format,
    content_json = excluded.content_json,
    content_text = excluded.content_text,
    content_sha256 = excluded.content_sha256,
    migrated_at = excluded.migrated_at,
    active = excluded.active;

insert into public.static_data_assets (asset_key, source_path, format, content_json, content_text, content_sha256, migrated_at, active)
values ('ruleset:BUILDING-CODE-PART9-EXT', 'data/rulesets/building_code_part9_ext_ruleset.json', 'json', '{"mechanism": "CODE", "rules": [{"check_value": 21, "desc": "Private stair — maximum 21 risers per flight", "operator": "<=", "property_name": "NumberOfRiser", "property_set": "Pset_StairFlightCommon", "ref": "CODE 9.8.3.3.(2)", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcStairFlight", "unit": "count"}, {"check_value": 21, "desc": "Private stair — maximum 21 treads per flight", "operator": "<=", "property_name": "NumberOfTreads", "property_set": "Pset_StairFlightCommon", "ref": "CODE 9.8.3.3.(2)", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcStairFlight", "unit": "count"}, {"check_value": null, "desc": "Fire-rated doors must have a FireRating property declared", "operator": "exists", "property_name": "FireRating", "property_set": "Pset_DoorCommon", "ref": "CODE 9.10.9", "rule_type": "prohibition", "severity": "informational", "target": "IfcDoor", "unit": null}, {"check_value": null, "desc": "All doors must declare IsExternal to classify as exit or interior", "operator": "exists", "property_name": "IsExternal", "property_set": "Pset_DoorCommon", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcDoor", "unit": null}, {"applies_when": {"location": "interior"}, "check_value": 2, "desc": "Interior doors must connect exactly two modeled spaces", "operator": "==", "property_name": "ConnectedSpaceCount", "property_set": "", "ref": "BIMGuard QA", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcDoor", "unit": "count"}, {"applies_when": {"location": "exterior"}, "check_value": 1, "desc": "Exterior doors must connect exactly one modeled interior space", "operator": "==", "property_name": "ConnectedSpaceCount", "property_set": "", "ref": "BIMGuard QA", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcDoor", "unit": "count"}, {"check_value": null, "desc": "All windows must declare IsExternal for daylight and egress classification", "operator": "exists", "property_name": "IsExternal", "property_set": "Pset_WindowCommon", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcWindow", "unit": null}, {"check_value": null, "desc": "All walls must declare IsExternal for spatial separation analysis", "operator": "exists", "property_name": "IsExternal", "property_set": "Pset_WallCommon", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcWall", "unit": null}, {"check_value": null, "desc": "All spaces must have OccupancyType set for compliance classification", "operator": "exists", "property_name": "OccupancyType", "property_set": "Pset_SpaceCommon", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcSpace", "unit": null}, {"check_value": null, "desc": "All spaces must have NetFloorArea for floor-area-ratio calculations", "operator": "exists", "property_name": "NetFloorArea", "property_set": "Qto_SpaceBaseQuantities", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcSpace", "unit": null}, {"check_value": null, "desc": "All plumbing fixtures must have PredefinedType set (TOILETPAN, BATH, SHOWER, WASHHANDBASIN, SINK)", "operator": "exists", "property_name": "PredefinedType", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcSanitaryTerminal", "unit": null}, {"check_value": null, "desc": "All fire and CO alarms must have PredefinedType set (SMOKEALARM, FIREDETECTOR, CO2SENSOR)", "operator": "exists", "property_name": "PredefinedType", "ref": "CODE 9.10.19", "rule_type": "prohibition", "severity": "mandatory", "target": "IfcAlarm", "unit": null}, {"check_value": null, "desc": "Accessible ramps should declare HasNonSkidSurface for slip-resistance compliance", "operator": "exists", "property_name": "HasNonSkidSurface", "property_set": "Pset_RampCommon", "ref": "CODE 3.8.3.4", "rule_type": "prohibition", "severity": "informational", "target": "IfcRamp", "unit": null}, {"check_value": null, "desc": "All slabs should declare IsExternal to distinguish roof/floor from internal slab", "operator": "exists", "property_name": "IsExternal", "property_set": "Pset_SlabCommon", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcSlab", "unit": null}, {"check_value": 45, "desc": "Party walls between dwelling units — minimum 45-minute fire resistance rating", "operator": ">=", "property_name": "FireRating", "property_set": "Pset_WallCommon", "ref": "CODE 9.10.9.14", "rule_type": "numeric_comparison", "severity": "mandatory", "target": "IfcWall", "unit": "min"}, {"check_value": null, "desc": "All doors should declare OperationType (SINGLE_SWING_LEFT, DOUBLE_SWING, etc.)", "operator": "exists", "property_name": "OperationType", "property_set": "Pset_DoorCommon", "ref": "BIMGuard QA", "rule_type": "prohibition", "severity": "informational", "target": "IfcDoor", "unit": null}], "ruleset_id": "BUILDING-CODE-PART9-EXT"}', '{
  "ruleset_id": "BUILDING-CODE-PART9-EXT",
  "mechanism": "CODE",
  "rules": [
    {
      "ref": "CODE 9.8.3.3.(2)",
      "rule_type": "numeric_comparison",
      "target": "IfcStairFlight",
      "property_name": "NumberOfRiser",
      "property_set": "Pset_StairFlightCommon",
      "operator": "<=",
      "check_value": 21,
      "unit": "count",
      "severity": "mandatory",
      "desc": "Private stair \u2014 maximum 21 risers per flight"
    },
    {
      "ref": "CODE 9.8.3.3.(2)",
      "rule_type": "numeric_comparison",
      "target": "IfcStairFlight",
      "property_name": "NumberOfTreads",
      "property_set": "Pset_StairFlightCommon",
      "operator": "<=",
      "check_value": 21,
      "unit": "count",
      "severity": "mandatory",
      "desc": "Private stair \u2014 maximum 21 treads per flight"
    },
    {
      "ref": "CODE 9.10.9",
      "rule_type": "prohibition",
      "target": "IfcDoor",
      "property_name": "FireRating",
      "property_set": "Pset_DoorCommon",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "Fire-rated doors must have a FireRating property declared"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcDoor",
      "property_name": "IsExternal",
      "property_set": "Pset_DoorCommon",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All doors must declare IsExternal to classify as exit or interior"
    },
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
      "applies_when": {
        "location": "interior"
      },
      "desc": "Interior doors must connect exactly two modeled spaces"
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
      "applies_when": {
        "location": "exterior"
      },
      "desc": "Exterior doors must connect exactly one modeled interior space"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcWindow",
      "property_name": "IsExternal",
      "property_set": "Pset_WindowCommon",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All windows must declare IsExternal for daylight and egress classification"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcWall",
      "property_name": "IsExternal",
      "property_set": "Pset_WallCommon",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All walls must declare IsExternal for spatial separation analysis"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcSpace",
      "property_name": "OccupancyType",
      "property_set": "Pset_SpaceCommon",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All spaces must have OccupancyType set for compliance classification"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcSpace",
      "property_name": "NetFloorArea",
      "property_set": "Qto_SpaceBaseQuantities",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All spaces must have NetFloorArea for floor-area-ratio calculations"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcSanitaryTerminal",
      "property_name": "PredefinedType",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All plumbing fixtures must have PredefinedType set (TOILETPAN, BATH, SHOWER, WASHHANDBASIN, SINK)"
    },
    {
      "ref": "CODE 9.10.19",
      "rule_type": "prohibition",
      "target": "IfcAlarm",
      "property_name": "PredefinedType",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "mandatory",
      "desc": "All fire and CO alarms must have PredefinedType set (SMOKEALARM, FIREDETECTOR, CO2SENSOR)"
    },
    {
      "ref": "CODE 3.8.3.4",
      "rule_type": "prohibition",
      "target": "IfcRamp",
      "property_name": "HasNonSkidSurface",
      "property_set": "Pset_RampCommon",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "Accessible ramps should declare HasNonSkidSurface for slip-resistance compliance"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcSlab",
      "property_name": "IsExternal",
      "property_set": "Pset_SlabCommon",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All slabs should declare IsExternal to distinguish roof/floor from internal slab"
    },
    {
      "ref": "CODE 9.10.9.14",
      "rule_type": "numeric_comparison",
      "target": "IfcWall",
      "property_name": "FireRating",
      "property_set": "Pset_WallCommon",
      "operator": ">=",
      "check_value": 45,
      "unit": "min",
      "severity": "mandatory",
      "desc": "Party walls between dwelling units \u2014 minimum 45-minute fire resistance rating"
    },
    {
      "ref": "BIMGuard QA",
      "rule_type": "prohibition",
      "target": "IfcDoor",
      "property_name": "OperationType",
      "property_set": "Pset_DoorCommon",
      "operator": "exists",
      "check_value": null,
      "unit": null,
      "severity": "informational",
      "desc": "All doors should declare OperationType (SINGLE_SWING_LEFT, DOUBLE_SWING, etc.)"
    }
  ]
}
', 'a3a300b501904fdcce92e1f16173e7e1c2ea7e1ca7d294c2106aa26cfdcc0960', '', 1)
on conflict (asset_key) do update set
    source_path = excluded.source_path,
    format = excluded.format,
    content_json = excluded.content_json,
    content_text = excluded.content_text,
    content_sha256 = excluded.content_sha256,
    migrated_at = excluded.migrated_at,
    active = excluded.active;

insert into public.static_data_assets (asset_key, source_path, format, content_json, content_text, content_sha256, migrated_at, active)
values ('ruleset:BIMGUARD-GC-001', 'data/rulesets/galvanic_corrosion_ruleset.json', 'json', '{"area_ratio_bands": {"bands": [{"label": "Favourable", "min_ratio": 5.0, "risk_score": 0.2}, {"label": "Acceptable", "min_ratio": 2.0, "risk_score": 0.4}, {"label": "Moderate", "min_ratio": 0.5, "risk_score": 0.6}, {"label": "Unfavourable", "min_ratio": 0.1, "risk_score": 0.8}, {"label": "Critical", "min_ratio": 0.0, "risk_score": 1.0}], "source": "Prosoco Technical Note 104 / AUCSC Basic Corrosion Course (2024)"}, "common_mep_pairings": [{"anode": "galv_steel", "application": "Galvanised steel support bracket / copper pipe", "band": "Critical", "cathode": "copper", "env": "E3_HUMID", "gap_v": 0.54, "id": "P-001"}, {"anode": "carbon_steel", "application": "Carbon steel structure / SS316 process pipe", "band": "Critical", "cathode": "ss316_passive", "env": "E3_HUMID", "gap_v": 0.47, "id": "P-002"}, {"anode": "aluminium", "application": "Aluminium cable tray / copper pipework", "band": "High", "cathode": "copper", "env": "E2_NORMAL", "gap_v": 0.42, "id": "P-003"}, {"anode": "carbon_steel", "application": "Carbon steel pipe / copper fittings", "band": "Medium", "cathode": "copper", "env": "E2_NORMAL", "gap_v": 0.27, "id": "P-004"}, {"anode": "ss304_passive", "application": "SS304 fittings / SS316 pipe", "band": "Low", "cathode": "ss316_passive", "env": "E2_NORMAL", "gap_v": 0.04, "id": "P-005"}, {"anode": "galv_steel", "application": "Galvanised unistrut / SS316 process pipe", "band": "Critical", "cathode": "ss316_passive", "env": "E3_HUMID", "gap_v": 0.74, "id": "P-006"}, {"anode": "carbon_steel", "application": "Carbon steel pipe / brass valve", "band": "Medium", "cathode": "brass", "env": "E2_NORMAL", "gap_v": 0.23, "id": "P-007"}, {"anode": "cast_iron", "application": "Cast iron pump body / copper distribution", "band": "Medium", "cathode": "copper", "env": "E2_NORMAL", "gap_v": 0.24, "id": "P-008"}, {"anode": "aluminium", "application": "Aluminium ductwork / SS316 pipework", "band": "Critical", "cathode": "ss316_passive", "env": "E3_HUMID", "gap_v": 0.62, "id": "P-009"}, {"anode": "titanium", "application": "Titanium pipe / SS316 fittings in pool", "band": "Low", "cathode": "ss316_passive", "env": "E6_POOL", "gap_v": 0.03, "id": "P-010"}], "description": "BIMGUARD AI compliance ruleset for galvanic corrosion risk assessment in MEP building services. Checks electrochemical potential difference between dissimilar metal pairs, area ratio risk, PREN adequacy for stainless steel grades, and environment class severity.", "environment_classes": {"E1_CONTROLLED": {"label": "Fully controlled / dry indoor", "multiplier": 0.2, "voltage_threshold_v": 0.5}, "E2_NORMAL": {"label": "Normal heated indoor", "multiplier": 0.4, "voltage_threshold_v": 0.25}, "E3_HUMID": {"label": "Humid plant room", "multiplier": 0.65, "voltage_threshold_v": 0.15}, "E4_SHELTERED": {"label": "External sheltered", "multiplier": 0.7, "voltage_threshold_v": 0.15}, "E5_EXPOSED": {"label": "External exposed", "multiplier": 0.85, "voltage_threshold_v": 0.1}, "E6_POOL": {"label": "Pool or spa enclosure", "multiplier": 0.9, "voltage_threshold_v": 0.1}, "E7_COASTAL": {"label": "Coastal or marine", "multiplier": 1.0, "voltage_threshold_v": 0.05}, "source": "NASA-STD-6012 Table 1"}, "galvanic_series": {"materials": {"aluminium": {"label": "Aluminium alloys", "noble": false, "potential_v": 0.7}, "brass": {"label": "Brass (70/30)", "noble": false, "potential_v": 0.32}, "bronze": {"label": "Bronze", "noble": false, "potential_v": 0.34}, "cadmium": {"label": "Cadmium", "noble": false, "potential_v": 0.75}, "carbon_steel": {"label": "Carbon / mild steel", "noble": false, "potential_v": 0.55}, "cast_iron": {"label": "Cast iron", "noble": false, "potential_v": 0.52}, "copper": {"label": "Copper", "noble": true, "potential_v": 0.28}, "galv_steel": {"label": "Galvanised steel", "noble": false, "potential_v": 0.82}, "gold": {"label": "Gold", "noble": true, "potential_v": 0.02}, "graphite": {"label": "Graphite", "noble": true, "potential_v": 0.03}, "hastelloy_c": {"label": "Hastelloy C", "noble": true, "potential_v": 0.14}, "magnesium": {"label": "Magnesium alloys", "noble": false, "potential_v": 0.95}, "platinum": {"label": "Platinum", "noble": true, "potential_v": 0.0}, "silver_solder": {"label": "Silver solder", "noble": true, "potential_v": 0.18}, "ss304_active": {"label": "SS 304 (active)", "noble": false, "potential_v": 0.38, "pren_typical": 19}, "ss304_passive": {"label": "SS 304 (passive)", "noble": true, "potential_v": 0.12, "pren_typical": 19}, "ss316_active": {"label": "SS 316 (active)", "noble": false, "potential_v": 0.22, "pren_typical": 25}, "ss316_passive": {"label": "SS 316 (passive)", "noble": true, "potential_v": 0.08, "pren_typical": 25}, "titanium": {"label": "Titanium", "noble": true, "potential_v": 0.05}, "zinc": {"label": "Zinc", "noble": false, "potential_v": 0.8}}, "note": "Lower potential = more noble (cathodic). Higher potential = more active (anodic) — corrodes preferentially.", "reference_electrode": "Ag/AgCl", "reference_electrolyte": "Seawater at ambient temperature", "source": "WorldStainless / Euro Inox (2025) and AUCSC Basic Corrosion Course (2024)"}, "ifc_data_sources": {"material": ["Pset_MaterialCommon.Name", "IfcMaterial.Name"], "nominal_diameter": ["Pset_PipeSegmentOccurrence.NominalDiameter"], "surface_area": ["Qto_PipeSegmentBaseQuantities.OuterSurfaceArea", "Calculated via ifcopenshell.geom"], "system_type": ["IfcDistributionSystem.PredefinedType", "IfcDistributionSystem.LongName"], "zone_category": ["IfcZone.LongName", "IfcZone.Name", "Pset_ZoneCommon.Category"]}, "mechanism": "Galvanic Corrosion", "mitigation_catalogue": {"MIT-GC-001": "Install dielectric isolation gaskets at all contact points between dissimilar metals", "MIT-GC-002": "Specify non-conductive spacers or sleeves between dissimilar metal surfaces", "MIT-GC-003": "Replace less noble metal with grade compatible with adjacent material", "MIT-GC-004": "Apply protective organic coating to both metallic surfaces at contact zone", "MIT-GC-005": "Install cathodic protection system — sacrificial anode or impressed current", "MIT-GC-006": "Increase separation distance to prevent moisture bridge formation", "MIT-GC-007": "Upgrade stainless steel grade to meet PREN requirement for environment class (IMOA Design Manual 4th Ed.)", "MIT-GC-008": "Replace galvanised steel fittings with SS304 or SS316 in this zone", "MIT-GC-009": "Use corrosion-inhibiting sealant at all dissimilar metal joints", "MIT-GC-010": "Implement corrosion monitoring programme at identified high-risk junctions"}, "pren_thresholds": {"by_environment": {"E1_CONTROLLED": {"min_pren": 18, "note": "SS304 adequate"}, "E2_NORMAL": {"min_pren": 18, "note": "SS304 adequate"}, "E3_HUMID": {"min_pren": 25, "note": "SS316 required"}, "E4_SHELTERED": {"min_pren": 25, "note": "SS316 required"}, "E5_EXPOSED": {"min_pren": 32, "note": "Duplex 2205 or better required"}, "E6_POOL": {"min_pren": 32, "note": "Duplex 2205 or better required"}, "E7_COASTAL": {"min_pren": 40, "note": "Super Duplex 2507 or Titanium required"}}, "formula": "PREN = %Cr + 3.3 x %Mo + 16 x %N", "grade_pren_values": {"Duplex 2205": 35, "SS 304": 19, "SS 316": 25, "Super Duplex 2507": 42, "Titanium Grade 2": 45}, "source": "IMOA Design Manual 4th Ed."}, "pset_corrosion_risk_schema": {"ifc_entities": ["IfcPipeSegment", "IfcPipeFitting", "IfcFlowSegment"], "properties": [{"description": "GC-001 composite risk score 0.0-1.0", "name": "GC001_CompositeScore", "type": "IfcReal"}, {"description": "Low / Medium / High / Critical", "name": "GC001_RiskBand", "type": "IfcLabel"}, {"description": "Electrochemical potential difference (V)", "name": "GC001_VoltageGap_V", "type": "IfcReal"}, {"description": "Voltage risk sub-score 0.0-1.0", "name": "GC001_VoltageRisk", "type": "IfcReal"}, {"description": "Area ratio classification", "name": "GC001_AreaRatioBand", "type": "IfcLabel"}, {"description": "Area ratio risk sub-score 0.0-1.0", "name": "GC001_AreaRatioRisk", "type": "IfcReal"}, {"description": "E1_CONTROLLED through E7_COASTAL", "name": "GC001_EnvironmentClass", "type": "IfcLabel"}, {"description": "Environment severity multiplier 0.20-1.00", "name": "GC001_EnvironmentMultiplier", "type": "IfcReal"}, {"description": "PREN adequacy check result", "name": "GC001_PRENAdequate", "type": "IfcBoolean"}, {"description": "PREN check explanation", "name": "GC001_PRENNote", "type": "IfcText"}, {"description": "Pipe-separated mitigation codes", "name": "GC001_RecommendedMitigation", "type": "IfcText"}, {"description": "BIMGUARD-GC-001 ruleset version", "name": "GC001_RulesetVersion", "type": "IfcLabel"}, {"description": "ISO 8601 UTC timestamp of assessment", "name": "GC001_AssessmentDate", "type": "IfcDateTime"}], "pset_name": "Pset_CorrosionRisk"}, "risk_bands": {"Critical": {"bcf_action": "BCF Critical priority — immediate remediation", "range": "> 0.85"}, "High": {"bcf_action": "BCF Major priority", "range": "0.65 - 0.85"}, "Low": {"bcf_action": "Asset register only — no BCF issue", "range": "< 0.35"}, "Medium": {"bcf_action": "BCF Normal priority", "range": "0.35 - 0.65"}}, "ruleset_id": "BIMGUARD-GC-001", "ruleset_version": "1.0.0", "scoring_model": {"formula": "Score_GC = (0.50 x voltage_risk) + (0.30 x area_ratio_risk) + (0.20 x environment_multiplier)", "pren_escalation": "PREN adequacy failure escalates minimum composite score to 0.35 (Medium band floor).", "voltage_risk_calculation": "Normalised score = min(1.0, voltage_gap / (2 x environment_threshold)). Score = 0.00 at zero gap, 0.50 at threshold, 1.00 at twice the threshold.", "weights": {"area_ratio_risk": 0.3, "environment_multiplier": 0.2, "voltage_risk": 0.5}}, "standards_referenced": ["NASA-STD-6012 — Corrosion Control and Treatment for Aerospace Vehicles (voltage thresholds by environment class)", "WorldStainless / Euro Inox (2025) — Galvanic series and corrosion rate data", "AUCSC Basic Corrosion Course (2024) — Galvanic series, electrolyte conductivity", "IMOA Design Manual 4th Ed. — PREN formula and grade selection", "Prosoco Technical Note 104 — Area ratio analysis for mechanical anchors", "American Galvanizers Association (2023) — Coating life data for galvanised steel", "ISO 19650 — BIM information management and IFC property set framework", "buildingSMART BCF 2.1 — Issue tracking specification"]}', '{
  "ruleset_id": "BIMGUARD-GC-001",
  "ruleset_version": "1.0.0",
  "mechanism": "Galvanic Corrosion",
  "description": "BIMGUARD AI compliance ruleset for galvanic corrosion risk assessment in MEP building services. Checks electrochemical potential difference between dissimilar metal pairs, area ratio risk, PREN adequacy for stainless steel grades, and environment class severity.",
  "standards_referenced": [
    "NASA-STD-6012 — Corrosion Control and Treatment for Aerospace Vehicles (voltage thresholds by environment class)",
    "WorldStainless / Euro Inox (2025) — Galvanic series and corrosion rate data",
    "AUCSC Basic Corrosion Course (2024) — Galvanic series, electrolyte conductivity",
    "IMOA Design Manual 4th Ed. — PREN formula and grade selection",
    "Prosoco Technical Note 104 — Area ratio analysis for mechanical anchors",
    "American Galvanizers Association (2023) — Coating life data for galvanised steel",
    "ISO 19650 — BIM information management and IFC property set framework",
    "buildingSMART BCF 2.1 — Issue tracking specification"
  ],
  "scoring_model": {
    "formula": "Score_GC = (0.50 x voltage_risk) + (0.30 x area_ratio_risk) + (0.20 x environment_multiplier)",
    "weights": { "voltage_risk": 0.50, "area_ratio_risk": 0.30, "environment_multiplier": 0.20 },
    "voltage_risk_calculation": "Normalised score = min(1.0, voltage_gap / (2 x environment_threshold)). Score = 0.00 at zero gap, 0.50 at threshold, 1.00 at twice the threshold.",
    "pren_escalation": "PREN adequacy failure escalates minimum composite score to 0.35 (Medium band floor)."
  },
  "risk_bands": {
    "Low":      { "range": "< 0.35",      "bcf_action": "Asset register only — no BCF issue" },
    "Medium":   { "range": "0.35 - 0.65", "bcf_action": "BCF Normal priority" },
    "High":     { "range": "0.65 - 0.85", "bcf_action": "BCF Major priority" },
    "Critical": { "range": "> 0.85",      "bcf_action": "BCF Critical priority — immediate remediation" }
  },
  "galvanic_series": {
    "reference_electrolyte": "Seawater at ambient temperature",
    "reference_electrode": "Ag/AgCl",
    "source": "WorldStainless / Euro Inox (2025) and AUCSC Basic Corrosion Course (2024)",
    "note": "Lower potential = more noble (cathodic). Higher potential = more active (anodic) — corrodes preferentially.",
    "materials": {
      "platinum":      { "potential_v": 0.00, "label": "Platinum",            "noble": true  },
      "gold":          { "potential_v": 0.02, "label": "Gold",                "noble": true  },
      "graphite":      { "potential_v": 0.03, "label": "Graphite",            "noble": true  },
      "titanium":      { "potential_v": 0.05, "label": "Titanium",            "noble": true  },
      "ss316_passive": { "potential_v": 0.08, "label": "SS 316 (passive)",    "noble": true,  "pren_typical": 25 },
      "ss304_passive": { "potential_v": 0.12, "label": "SS 304 (passive)",    "noble": true,  "pren_typical": 19 },
      "hastelloy_c":   { "potential_v": 0.14, "label": "Hastelloy C",         "noble": true  },
      "silver_solder": { "potential_v": 0.18, "label": "Silver solder",       "noble": true  },
      "ss316_active":  { "potential_v": 0.22, "label": "SS 316 (active)",     "noble": false, "pren_typical": 25 },
      "copper":        { "potential_v": 0.28, "label": "Copper",              "noble": true  },
      "brass":         { "potential_v": 0.32, "label": "Brass (70/30)",       "noble": false },
      "bronze":        { "potential_v": 0.34, "label": "Bronze",              "noble": false },
      "ss304_active":  { "potential_v": 0.38, "label": "SS 304 (active)",     "noble": false, "pren_typical": 19 },
      "cast_iron":     { "potential_v": 0.52, "label": "Cast iron",           "noble": false },
      "carbon_steel":  { "potential_v": 0.55, "label": "Carbon / mild steel", "noble": false },
      "aluminium":     { "potential_v": 0.70, "label": "Aluminium alloys",    "noble": false },
      "cadmium":       { "potential_v": 0.75, "label": "Cadmium",             "noble": false },
      "zinc":          { "potential_v": 0.80, "label": "Zinc",                "noble": false },
      "galv_steel":    { "potential_v": 0.82, "label": "Galvanised steel",    "noble": false },
      "magnesium":     { "potential_v": 0.95, "label": "Magnesium alloys",    "noble": false }
    }
  },
  "environment_classes": {
    "source": "NASA-STD-6012 Table 1",
    "E1_CONTROLLED": { "label": "Fully controlled / dry indoor",   "voltage_threshold_v": 0.50, "multiplier": 0.20 },
    "E2_NORMAL":     { "label": "Normal heated indoor",            "voltage_threshold_v": 0.25, "multiplier": 0.40 },
    "E3_HUMID":      { "label": "Humid plant room",                "voltage_threshold_v": 0.15, "multiplier": 0.65 },
    "E4_SHELTERED":  { "label": "External sheltered",              "voltage_threshold_v": 0.15, "multiplier": 0.70 },
    "E5_EXPOSED":    { "label": "External exposed",                "voltage_threshold_v": 0.10, "multiplier": 0.85 },
    "E6_POOL":       { "label": "Pool or spa enclosure",           "voltage_threshold_v": 0.10, "multiplier": 0.90 },
    "E7_COASTAL":    { "label": "Coastal or marine",               "voltage_threshold_v": 0.05, "multiplier": 1.00 }
  },
  "area_ratio_bands": {
    "source": "Prosoco Technical Note 104 / AUCSC Basic Corrosion Course (2024)",
    "bands": [
      { "label": "Favourable",   "min_ratio": 5.0, "risk_score": 0.20 },
      { "label": "Acceptable",   "min_ratio": 2.0, "risk_score": 0.40 },
      { "label": "Moderate",     "min_ratio": 0.5, "risk_score": 0.60 },
      { "label": "Unfavourable", "min_ratio": 0.1, "risk_score": 0.80 },
      { "label": "Critical",     "min_ratio": 0.0, "risk_score": 1.00 }
    ]
  },
  "pren_thresholds": {
    "formula": "PREN = %Cr + 3.3 x %Mo + 16 x %N",
    "source": "IMOA Design Manual 4th Ed.",
    "by_environment": {
      "E1_CONTROLLED": { "min_pren": 18, "note": "SS304 adequate" },
      "E2_NORMAL":     { "min_pren": 18, "note": "SS304 adequate" },
      "E3_HUMID":      { "min_pren": 25, "note": "SS316 required" },
      "E4_SHELTERED":  { "min_pren": 25, "note": "SS316 required" },
      "E5_EXPOSED":    { "min_pren": 32, "note": "Duplex 2205 or better required" },
      "E6_POOL":       { "min_pren": 32, "note": "Duplex 2205 or better required" },
      "E7_COASTAL":    { "min_pren": 40, "note": "Super Duplex 2507 or Titanium required" }
    },
    "grade_pren_values": {
      "SS 304": 19, "SS 316": 25, "Duplex 2205": 35, "Super Duplex 2507": 42, "Titanium Grade 2": 45
    }
  },
  "common_mep_pairings": [
    { "id": "P-001", "anode": "galv_steel",    "cathode": "copper",        "gap_v": 0.54, "env": "E3_HUMID",   "band": "Critical", "application": "Galvanised steel support bracket / copper pipe" },
    { "id": "P-002", "anode": "carbon_steel",  "cathode": "ss316_passive", "gap_v": 0.47, "env": "E3_HUMID",   "band": "Critical", "application": "Carbon steel structure / SS316 process pipe" },
    { "id": "P-003", "anode": "aluminium",     "cathode": "copper",        "gap_v": 0.42, "env": "E2_NORMAL",  "band": "High",     "application": "Aluminium cable tray / copper pipework" },
    { "id": "P-004", "anode": "carbon_steel",  "cathode": "copper",        "gap_v": 0.27, "env": "E2_NORMAL",  "band": "Medium",   "application": "Carbon steel pipe / copper fittings" },
    { "id": "P-005", "anode": "ss304_passive", "cathode": "ss316_passive", "gap_v": 0.04, "env": "E2_NORMAL",  "band": "Low",      "application": "SS304 fittings / SS316 pipe" },
    { "id": "P-006", "anode": "galv_steel",    "cathode": "ss316_passive", "gap_v": 0.74, "env": "E3_HUMID",   "band": "Critical", "application": "Galvanised unistrut / SS316 process pipe" },
    { "id": "P-007", "anode": "carbon_steel",  "cathode": "brass",         "gap_v": 0.23, "env": "E2_NORMAL",  "band": "Medium",   "application": "Carbon steel pipe / brass valve" },
    { "id": "P-008", "anode": "cast_iron",     "cathode": "copper",        "gap_v": 0.24, "env": "E2_NORMAL",  "band": "Medium",   "application": "Cast iron pump body / copper distribution" },
    { "id": "P-009", "anode": "aluminium",     "cathode": "ss316_passive", "gap_v": 0.62, "env": "E3_HUMID",   "band": "Critical", "application": "Aluminium ductwork / SS316 pipework" },
    { "id": "P-010", "anode": "titanium",      "cathode": "ss316_passive", "gap_v": 0.03, "env": "E6_POOL",    "band": "Low",      "application": "Titanium pipe / SS316 fittings in pool" }
  ],
  "mitigation_catalogue": {
    "MIT-GC-001": "Install dielectric isolation gaskets at all contact points between dissimilar metals",
    "MIT-GC-002": "Specify non-conductive spacers or sleeves between dissimilar metal surfaces",
    "MIT-GC-003": "Replace less noble metal with grade compatible with adjacent material",
    "MIT-GC-004": "Apply protective organic coating to both metallic surfaces at contact zone",
    "MIT-GC-005": "Install cathodic protection system — sacrificial anode or impressed current",
    "MIT-GC-006": "Increase separation distance to prevent moisture bridge formation",
    "MIT-GC-007": "Upgrade stainless steel grade to meet PREN requirement for environment class (IMOA Design Manual 4th Ed.)",
    "MIT-GC-008": "Replace galvanised steel fittings with SS304 or SS316 in this zone",
    "MIT-GC-009": "Use corrosion-inhibiting sealant at all dissimilar metal joints",
    "MIT-GC-010": "Implement corrosion monitoring programme at identified high-risk junctions"
  },
  "pset_corrosion_risk_schema": {
    "pset_name": "Pset_CorrosionRisk",
    "ifc_entities": ["IfcPipeSegment", "IfcPipeFitting", "IfcFlowSegment"],
    "properties": [
      { "name": "GC001_CompositeScore",        "type": "IfcReal",     "description": "GC-001 composite risk score 0.0-1.0" },
      { "name": "GC001_RiskBand",              "type": "IfcLabel",    "description": "Low / Medium / High / Critical" },
      { "name": "GC001_VoltageGap_V",          "type": "IfcReal",     "description": "Electrochemical potential difference (V)" },
      { "name": "GC001_VoltageRisk",           "type": "IfcReal",     "description": "Voltage risk sub-score 0.0-1.0" },
      { "name": "GC001_AreaRatioBand",         "type": "IfcLabel",    "description": "Area ratio classification" },
      { "name": "GC001_AreaRatioRisk",         "type": "IfcReal",     "description": "Area ratio risk sub-score 0.0-1.0" },
      { "name": "GC001_EnvironmentClass",      "type": "IfcLabel",    "description": "E1_CONTROLLED through E7_COASTAL" },
      { "name": "GC001_EnvironmentMultiplier", "type": "IfcReal",     "description": "Environment severity multiplier 0.20-1.00" },
      { "name": "GC001_PRENAdequate",          "type": "IfcBoolean",  "description": "PREN adequacy check result" },
      { "name": "GC001_PRENNote",              "type": "IfcText",     "description": "PREN check explanation" },
      { "name": "GC001_RecommendedMitigation", "type": "IfcText",     "description": "Pipe-separated mitigation codes" },
      { "name": "GC001_RulesetVersion",        "type": "IfcLabel",    "description": "BIMGUARD-GC-001 ruleset version" },
      { "name": "GC001_AssessmentDate",        "type": "IfcDateTime", "description": "ISO 8601 UTC timestamp of assessment" }
    ]
  },
  "ifc_data_sources": {
    "material":        ["Pset_MaterialCommon.Name", "IfcMaterial.Name"],
    "nominal_diameter":["Pset_PipeSegmentOccurrence.NominalDiameter"],
    "surface_area":    ["Qto_PipeSegmentBaseQuantities.OuterSurfaceArea", "Calculated via ifcopenshell.geom"],
    "zone_category":   ["IfcZone.LongName", "IfcZone.Name", "Pset_ZoneCommon.Category"],
    "system_type":     ["IfcDistributionSystem.PredefinedType", "IfcDistributionSystem.LongName"]
  }
}
', '02f3e20e56e26759906a03574bfe59b22053c76821f4c852586bb6bac227970d', '', 1)
on conflict (asset_key) do update set
    source_path = excluded.source_path,
    format = excluded.format,
    content_json = excluded.content_json,
    content_text = excluded.content_text,
    content_sha256 = excluded.content_sha256,
    migrated_at = excluded.migrated_at,
    active = excluded.active;

insert into public.static_data_assets (asset_key, source_path, format, content_json, content_text, content_sha256, migrated_at, active)
values ('ruleset:BIMGUARD-CC-001', 'data/rulesets/crevice_corrosion_ruleset.json', 'json', '{"cct_table": {"description": "Critical Crevice Corrosion Temperature for common MEP stainless grades. Below CCT = passive film stable. Above CCT = crevice attack initiates.", "grades": {"duplex2205": {"cct_c": 25, "label": "Duplex 2205 / 1.4462", "pren_typical": 35, "uns": "S32205"}, "hastelloy_c": {"cct_c": 85, "label": "Hastelloy C-276", "pren_typical": 70, "uns": "N10276"}, "ss304_active": {"cct_c": -5, "label": "SS 304 (active)", "pren_typical": 19, "uns": "S30400"}, "ss304_passive": {"cct_c": -5, "label": "SS 304 / 1.4301", "pren_typical": 19, "uns": "S30400"}, "ss316_active": {"cct_c": 10, "label": "SS 316 (active)", "pren_typical": 25, "uns": "S31600"}, "ss316_passive": {"cct_c": 10, "label": "SS 316 / 1.4401", "pren_typical": 25, "uns": "S31600"}, "superduplex2507": {"cct_c": 50, "label": "Super Duplex 2507 / 1.4410", "pren_typical": 42, "uns": "S32750"}, "titanium": {"cct_c": 120, "label": "Titanium Grade 2", "pren_typical": 45, "uns": "R50400"}}, "source": "ASTM G48 Method B / CIRIA C692 / Sandvik Corrosion Handbook", "test_conditions": "6% FeCl3 solution per ASTM G48 Method B"}, "description": "BIMGUARD AI compliance ruleset for crevice corrosion risk assessment in MEP building services. Checks Critical Crevice Corrosion Temperature (CCT) adequacy of stainless steel grades against operating temperature, joint geometry class, and environment severity. The defining finding of CC-001: SS316 in a pool plant room scores 0.00 galvanic (GC-001) but 0.89 Critical on CC-001 — demonstrating that galvanic checking alone is insufficient.", "environment_severity": {"classes": {"BUILDING_SERVICES": {"chloride_mgl": "variable", "label": "Internal building services pipework", "reference": "CIBSE Guide G", "severity": 0.35, "wetness": "continuous internal"}, "T0_DRY": {"chloride_mgl": "0", "label": "Essentially dry — controlled indoor", "severity": 0.05, "wetness": "< 1% annual"}, "T1_OCCASIONAL": {"chloride_mgl": "< 10", "label": "Occasional condensation — normal indoor", "severity": 0.2, "wetness": "< 10% annual"}, "T2_INTERMITTENT": {"chloride_mgl": "< 50", "label": "Intermittent wetting — humid plant room", "severity": 0.4, "wetness": "10-50% annual"}, "T3_FREQUENT": {"chloride_mgl": "50-200", "label": "Frequent wetting — external sheltered", "severity": 0.6, "wetness": "50-75% annual"}, "T4_PERSISTENT": {"chloride_mgl": "200-1000", "label": "Persistent wetting — external exposed", "severity": 0.8, "wetness": "> 75% annual"}, "T5_IMMERSION": {"chloride_mgl": "> 1000", "label": "Immersion / pool / marine — most severe", "severity": 1.0, "wetness": "continuous"}}, "description": "Seven severity classes per EN ISO 15329:2007 wetting classification framework.", "source": "EN ISO 15329:2007"}, "geometry_classes": {"Critical": {"crevice_width_mm": "< 0.1", "description": "Threaded connections, under clamps, gasket contact — maximum crevice conditions", "risk": 1.0}, "Moderate": {"crevice_width_mm": "0.5 - 2.0", "description": "Socket welds, slip-on flanges, press fittings — some flow restriction", "risk": 0.45}, "Open": {"crevice_width_mm": "> 2.0", "description": "Butt welds, open pipe ends — free electrolyte circulation", "risk": 0.1}, "Tight": {"crevice_width_mm": "0.1 - 0.5", "description": "Weld neck flanges, compression fittings, lap joints — significant restriction", "risk": 0.75}, "description": "Four geometry classes describing the degree of crevice restriction. Source: CIBSE Guide G / CIRIA C692."}, "high_risk_configurations": [{"academic_significance": "GC-001 score 0.00 (Low) — this is the defining finding justifying the dual-engine architecture", "config_id": "CC-HRC-001", "description": "SS316 flanged connection in pool plant room", "environment": "T5_IMMERSION", "expected_band": "Critical", "expected_score": 0.89, "joint": "JT-004", "material": "ss316_passive", "typical_temp_c": 35}, {"config_id": "CC-HRC-002", "description": "SS304 flanged connection in pool enclosure", "environment": "T5_IMMERSION", "expected_band": "Critical", "expected_score": 0.91, "joint": "JT-004", "material": "ss304_passive", "note": "SS304 CCT = -5 degrees C — at risk in any above-freezing environment with chloride", "typical_temp_c": 25}, {"config_id": "CC-HRC-003", "description": "SS316 threaded connection in humid plant room above 40°C", "environment": "T2_INTERMITTENT", "expected_band": "Critical", "expected_score": 0.85, "joint": "JT-005", "material": "ss316_passive", "note": "Threaded joint (Critical geometry) combined with operating above CCT", "typical_temp_c": 40}, {"config_id": "CC-HRC-004", "description": "SS304 compression fitting in normal indoor environment at 15°C", "environment": "T1_OCCASIONAL", "expected_band": "High", "expected_score": 0.66, "joint": "JT-006", "material": "ss304_passive", "note": "SS304 CCT only -5°C — modest temperature still 20°C above CCT", "typical_temp_c": 15}, {"config_id": "CC-HRC-005", "description": "Super Duplex 2507 flanged in pool environment at 45°C", "environment": "T5_IMMERSION", "expected_band": "High", "expected_score": 0.69, "joint": "JT-004", "material": "superduplex2507", "note": "CCT +50°C — only 5°C margin at 45°C operating temperature", "typical_temp_c": 45}], "ifc_data_sources": {"joint_type": ["IfcPipeFitting.PredefinedType", "Pset_PipeFittingOccurrence.ConnectionType", "IfcPipeSegmentType.ObjectType"], "material": ["Pset_MaterialCommon.Name", "IfcMaterial.Name"], "operating_temp": ["Pset_PipeSegmentOccurrence.OperatingTemperature", "Pset_ZoneCommon.SetPointTemperature"], "system_type": ["IfcDistributionSystem.PredefinedType", "IfcDistributionSystem.LongName"], "zone_category": ["IfcZone.LongName", "IfcZone.Name", "Pset_ZoneCommon.Category"]}, "joint_type_library": {"description": "14-type joint library mapping IFC element types and joint descriptions to geometry class. JT-014 (unknown) defaults to Tight — conservative fallback when joint data is absent from IFC model.", "types": {"JT-001": {"geometry": "Open", "ifc_keywords": ["butt", "buttweld", "butt weld"], "label": "Butt weld", "risk": 0.1}, "JT-002": {"geometry": "Moderate", "ifc_keywords": ["socket", "socketweld", "socket weld"], "label": "Socket weld", "risk": 0.45}, "JT-003": {"geometry": "Moderate", "ifc_keywords": ["slip-on", "slipon", "slip on", "so flange"], "label": "Slip-on flange", "risk": 0.45}, "JT-004": {"geometry": "Tight", "ifc_keywords": ["weld neck", "weldneck", "wnrf", "wn flange"], "label": "Weld neck flange", "risk": 0.75}, "JT-005": {"geometry": "Critical", "ifc_keywords": ["threaded", "npt", "thread"], "label": "Threaded NPT", "risk": 1.0}, "JT-006": {"geometry": "Tight", "ifc_keywords": ["compression", "compr", "olive"], "label": "Compression fitting", "risk": 0.75}, "JT-007": {"geometry": "Moderate", "ifc_keywords": ["press fit", "pressfit", "push fit", "pushfit"], "label": "Push-fit press", "risk": 0.45}, "JT-008": {"geometry": "Moderate", "ifc_keywords": ["victaulic", "groove", "grooved coupling"], "label": "Victaulic groove coupling", "risk": 0.45}, "JT-009": {"geometry": "Critical", "ifc_keywords": ["bsp", "screwed bsp", "bspt"], "label": "Screwed BSP", "risk": 1.0}, "JT-010": {"geometry": "Tight", "ifc_keywords": ["lap joint", "lapjoint", "stub end"], "label": "Lap joint flange", "risk": 0.75}, "JT-011": {"geometry": "Tight", "ifc_keywords": ["rtj", "ring type joint", "ring-type"], "label": "Ring-type joint flange", "risk": 0.75}, "JT-012": {"geometry": "Critical", "ifc_keywords": ["under insulation", "clamp", "u-bolt"], "label": "Pipe clamp under insulation", "risk": 1.0}, "JT-013": {"geometry": "Tight", "ifc_keywords": ["anchor", "mechanical anchor"], "label": "Mechanical anchor contact", "risk": 0.75}, "JT-014": {"geometry": "Tight", "ifc_keywords": [], "label": "Unknown / unclassified", "note": "Conservative default when joint type cannot be determined from IFC data", "risk": 0.75}}}, "mechanism": "Crevice Corrosion", "mechanism_description": {"four_stage_process": {"reference": "Fontana & Greene (1967) — Corrosion Engineering, McGraw-Hill", "stage_1_initiation": "Confined electrolyte initially identical to bulk solution. Oxygen depletion begins as cathodic reduction consumes O2 faster than diffusion can replenish it.", "stage_2_differential_aeration": "O2-depleted crevice becomes anodic. Metal dissolution begins: M -> M2+ + 2e-. Electrons travel to oxygenated exterior (cathodic).", "stage_3_autocatalytic": "Metal cation hydrolysis lowers local pH. Chloride ions migrate in to maintain charge neutrality. Passive film destroyed by low pH and high Cl- concentration.", "stage_4_propagation": "Autocatalytic chemistry is self-sustaining. Corrosion continues even if external conditions improve — until crevice is eliminated or pipe perforated."}, "summary": "Crevice corrosion initiates in geometrically confined spaces where restricted electrolyte circulation creates an aggressive local chemistry that destroys the passive film on stainless steel — the same passive film that makes these grades resistant to galvanic attack."}, "mitigation_catalogue": {"MIT-CC-001": "Upgrade stainless steel grade — specify Duplex 2205 (CCT +25°C) or Super Duplex 2507 (CCT +50°C) per CIRIA C692", "MIT-CC-002": "Change joint type to reduce geometry class — specify butt weld instead of flanged or threaded connection", "MIT-CC-003": "Specify PTFE or elastomer gaskets with minimum crevice geometry at flange interface", "MIT-CC-004": "Apply crevice-resistant surface treatment — electropolishing or passivation per ASTM A967", "MIT-CC-005": "Reduce chloride concentration in operating environment — improve ventilation or drainage", "MIT-CC-006": "Lower operating temperature below material CCT — review system temperature setpoints", "MIT-CC-007": "Specify titanium Grade 2 (CCT +120°C) for elements in permanent high-chloride high-temperature service", "MIT-CC-008": "Implement periodic inspection regime at identified crevice geometry locations"}, "pset_crevice_corrosion_risk_schema": {"ifc_entities": ["IfcPipeSegment", "IfcPipeFitting", "IfcFlowSegment"], "properties": [{"description": "CC-001 composite risk score 0.0-1.0", "name": "CC001_CompositeScore", "type": "IfcReal"}, {"description": "Low / Medium / High / Critical", "name": "CC001_RiskBand", "type": "IfcLabel"}, {"description": "Joint type code JT-001 through JT-014", "name": "CC001_JointTypeCode", "type": "IfcLabel"}, {"description": "Open / Moderate / Tight / Critical", "name": "CC001_GeometryClass", "type": "IfcLabel"}, {"description": "Geometry risk sub-score 0.0-1.0", "name": "CC001_GeometryRisk", "type": "IfcReal"}, {"description": "Operating temperature in degrees C", "name": "CC001_OperatingTemp_C", "type": "IfcReal"}, {"description": "Critical Crevice Corrosion Temperature for specified grade", "name": "CC001_CCT_C", "type": "IfcReal"}, {"description": "CCT adequacy sub-score 0.0-1.0", "name": "CC001_CCTAdequacyScore", "type": "IfcReal"}, {"description": "CCT adequacy explanation and margin", "name": "CC001_CCTNote", "type": "IfcText"}, {"description": "T0_DRY through T5_IMMERSION per EN ISO 15329:2007", "name": "CC001_EnvironmentKey", "type": "IfcLabel"}, {"description": "Environment severity score 0.0-1.0", "name": "CC001_EnvironmentSeverity", "type": "IfcReal"}, {"description": "Pipe-separated mitigation codes", "name": "CC001_RecommendedMitigation", "type": "IfcText"}, {"description": "BIMGUARD-CC-001 ruleset version", "name": "CC001_RulesetVersion", "type": "IfcLabel"}, {"description": "ISO 8601 UTC timestamp of assessment", "name": "CC001_AssessmentDate", "type": "IfcDateTime"}], "pset_name": "Pset_CreviceCorrosionRisk"}, "risk_bands": {"Critical": {"bcf_action": "BCF Critical priority — immediate material substitution or redesign", "range": "> 0.80"}, "High": {"bcf_action": "BCF Major priority — material or joint type upgrade required", "range": "0.55 - 0.80"}, "Low": {"bcf_action": "Asset register only — no BCF issue", "range": "< 0.30"}, "Medium": {"bcf_action": "BCF Normal priority — monitor and review joint specification", "range": "0.30 - 0.55"}}, "ruleset_id": "BIMGUARD-CC-001", "ruleset_version": "1.0.0", "scoring_model": {"cct_adequacy_calculation": "Linear interpolation: score 0.00 when operating temp is 20+ degrees below CCT (fully adequate). Score 0.60 when at CCT. Score 1.00 when 30+ degrees above CCT. Extrapolated linearly between these points.", "formula": "Score_CC = (0.35 x geometry_risk) + (0.40 x CCT_adequacy) + (0.25 x environment_severity)", "rationale": "CCT adequacy receives highest weight (0.40) as it is the most material-specific determinant — whether the specified grade can resist crevice attack at the operating temperature is the central question. Geometry (0.35) determines whether crevice conditions can establish. Environment severity (0.25) reflects chloride concentration and wetting frequency.", "weights": {"CCT_adequacy": 0.4, "environment_severity": 0.25, "geometry_risk": 0.35}}, "standards_referenced": ["EN ISO 15329:2007 — Crevice corrosion testing, wetting classification T0-T5", "ASTM G48 Method B — CCT determination for stainless steel grades", "CIRIA C692 — Stainless steel in construction, CCT data table", "CIBSE Guide G — Public health engineering, crevice corrosion guidance", "IMOA Design Manual 4th Ed. — PREN formula and stainless grade selection", "EN 1993-1-4 — Structural stainless steel", "BS 8539 — Fixings in construction, bi-metallic assembly", "buildingSMART BCF 2.1 — Issue tracking specification", "ISO 19650 — BIM information management, IFC property set framework"]}', '{
  "ruleset_id": "BIMGUARD-CC-001",
  "ruleset_version": "1.0.0",
  "mechanism": "Crevice Corrosion",
  "description": "BIMGUARD AI compliance ruleset for crevice corrosion risk assessment in MEP building services. Checks Critical Crevice Corrosion Temperature (CCT) adequacy of stainless steel grades against operating temperature, joint geometry class, and environment severity. The defining finding of CC-001: SS316 in a pool plant room scores 0.00 galvanic (GC-001) but 0.89 Critical on CC-001 — demonstrating that galvanic checking alone is insufficient.",
  "standards_referenced": [
    "EN ISO 15329:2007 — Crevice corrosion testing, wetting classification T0-T5",
    "ASTM G48 Method B — CCT determination for stainless steel grades",
    "CIRIA C692 — Stainless steel in construction, CCT data table",
    "CIBSE Guide G — Public health engineering, crevice corrosion guidance",
    "IMOA Design Manual 4th Ed. — PREN formula and stainless grade selection",
    "EN 1993-1-4 — Structural stainless steel",
    "BS 8539 — Fixings in construction, bi-metallic assembly",
    "buildingSMART BCF 2.1 — Issue tracking specification",
    "ISO 19650 — BIM information management, IFC property set framework"
  ],
  "mechanism_description": {
    "summary": "Crevice corrosion initiates in geometrically confined spaces where restricted electrolyte circulation creates an aggressive local chemistry that destroys the passive film on stainless steel — the same passive film that makes these grades resistant to galvanic attack.",
    "four_stage_process": {
      "stage_1_initiation": "Confined electrolyte initially identical to bulk solution. Oxygen depletion begins as cathodic reduction consumes O2 faster than diffusion can replenish it.",
      "stage_2_differential_aeration": "O2-depleted crevice becomes anodic. Metal dissolution begins: M -> M2+ + 2e-. Electrons travel to oxygenated exterior (cathodic).",
      "stage_3_autocatalytic": "Metal cation hydrolysis lowers local pH. Chloride ions migrate in to maintain charge neutrality. Passive film destroyed by low pH and high Cl- concentration.",
      "stage_4_propagation": "Autocatalytic chemistry is self-sustaining. Corrosion continues even if external conditions improve — until crevice is eliminated or pipe perforated.",
      "reference": "Fontana & Greene (1967) — Corrosion Engineering, McGraw-Hill"
    }
  },
  "scoring_model": {
    "formula": "Score_CC = (0.35 x geometry_risk) + (0.40 x CCT_adequacy) + (0.25 x environment_severity)",
    "weights": {
      "geometry_risk": 0.35,
      "CCT_adequacy": 0.40,
      "environment_severity": 0.25
    },
    "rationale": "CCT adequacy receives highest weight (0.40) as it is the most material-specific determinant — whether the specified grade can resist crevice attack at the operating temperature is the central question. Geometry (0.35) determines whether crevice conditions can establish. Environment severity (0.25) reflects chloride concentration and wetting frequency.",
    "cct_adequacy_calculation": "Linear interpolation: score 0.00 when operating temp is 20+ degrees below CCT (fully adequate). Score 0.60 when at CCT. Score 1.00 when 30+ degrees above CCT. Extrapolated linearly between these points."
  },
  "risk_bands": {
    "Low":      { "range": "< 0.30",      "bcf_action": "Asset register only — no BCF issue" },
    "Medium":   { "range": "0.30 - 0.55", "bcf_action": "BCF Normal priority — monitor and review joint specification" },
    "High":     { "range": "0.55 - 0.80", "bcf_action": "BCF Major priority — material or joint type upgrade required" },
    "Critical": { "range": "> 0.80",      "bcf_action": "BCF Critical priority — immediate material substitution or redesign" }
  },
  "cct_table": {
    "description": "Critical Crevice Corrosion Temperature for common MEP stainless grades. Below CCT = passive film stable. Above CCT = crevice attack initiates.",
    "source": "ASTM G48 Method B / CIRIA C692 / Sandvik Corrosion Handbook",
    "test_conditions": "6% FeCl3 solution per ASTM G48 Method B",
    "grades": {
      "ss304_passive":   { "cct_c": -5,   "pren_typical": 19, "label": "SS 304 / 1.4301", "uns": "S30400" },
      "ss304_active":    { "cct_c": -5,   "pren_typical": 19, "label": "SS 304 (active)",  "uns": "S30400" },
      "ss316_passive":   { "cct_c": 10,   "pren_typical": 25, "label": "SS 316 / 1.4401", "uns": "S31600" },
      "ss316_active":    { "cct_c": 10,   "pren_typical": 25, "label": "SS 316 (active)",  "uns": "S31600" },
      "duplex2205":      { "cct_c": 25,   "pren_typical": 35, "label": "Duplex 2205 / 1.4462", "uns": "S32205" },
      "superduplex2507": { "cct_c": 50,   "pren_typical": 42, "label": "Super Duplex 2507 / 1.4410", "uns": "S32750" },
      "titanium":        { "cct_c": 120,  "pren_typical": 45, "label": "Titanium Grade 2", "uns": "R50400" },
      "hastelloy_c":     { "cct_c": 85,   "pren_typical": 70, "label": "Hastelloy C-276",  "uns": "N10276" }
    }
  },
  "geometry_classes": {
    "description": "Four geometry classes describing the degree of crevice restriction. Source: CIBSE Guide G / CIRIA C692.",
    "Open":     { "risk": 0.10, "crevice_width_mm": "> 2.0",     "description": "Butt welds, open pipe ends — free electrolyte circulation" },
    "Moderate": { "risk": 0.45, "crevice_width_mm": "0.5 - 2.0", "description": "Socket welds, slip-on flanges, press fittings — some flow restriction" },
    "Tight":    { "risk": 0.75, "crevice_width_mm": "0.1 - 0.5", "description": "Weld neck flanges, compression fittings, lap joints — significant restriction" },
    "Critical": { "risk": 1.00, "crevice_width_mm": "< 0.1",     "description": "Threaded connections, under clamps, gasket contact — maximum crevice conditions" }
  },
  "joint_type_library": {
    "description": "14-type joint library mapping IFC element types and joint descriptions to geometry class. JT-014 (unknown) defaults to Tight — conservative fallback when joint data is absent from IFC model.",
    "types": {
      "JT-001": { "label": "Butt weld",                   "geometry": "Open",     "risk": 0.10, "ifc_keywords": ["butt", "buttweld", "butt weld"] },
      "JT-002": { "label": "Socket weld",                 "geometry": "Moderate", "risk": 0.45, "ifc_keywords": ["socket", "socketweld", "socket weld"] },
      "JT-003": { "label": "Slip-on flange",              "geometry": "Moderate", "risk": 0.45, "ifc_keywords": ["slip-on", "slipon", "slip on", "so flange"] },
      "JT-004": { "label": "Weld neck flange",            "geometry": "Tight",    "risk": 0.75, "ifc_keywords": ["weld neck", "weldneck", "wnrf", "wn flange"] },
      "JT-005": { "label": "Threaded NPT",                "geometry": "Critical", "risk": 1.00, "ifc_keywords": ["threaded", "npt", "thread"] },
      "JT-006": { "label": "Compression fitting",         "geometry": "Tight",    "risk": 0.75, "ifc_keywords": ["compression", "compr", "olive"] },
      "JT-007": { "label": "Push-fit press",              "geometry": "Moderate", "risk": 0.45, "ifc_keywords": ["press fit", "pressfit", "push fit", "pushfit"] },
      "JT-008": { "label": "Victaulic groove coupling",   "geometry": "Moderate", "risk": 0.45, "ifc_keywords": ["victaulic", "groove", "grooved coupling"] },
      "JT-009": { "label": "Screwed BSP",                 "geometry": "Critical", "risk": 1.00, "ifc_keywords": ["bsp", "screwed bsp", "bspt"] },
      "JT-010": { "label": "Lap joint flange",            "geometry": "Tight",    "risk": 0.75, "ifc_keywords": ["lap joint", "lapjoint", "stub end"] },
      "JT-011": { "label": "Ring-type joint flange",      "geometry": "Tight",    "risk": 0.75, "ifc_keywords": ["rtj", "ring type joint", "ring-type"] },
      "JT-012": { "label": "Pipe clamp under insulation", "geometry": "Critical", "risk": 1.00, "ifc_keywords": ["under insulation", "clamp", "u-bolt"] },
      "JT-013": { "label": "Mechanical anchor contact",  "geometry": "Tight",    "risk": 0.75, "ifc_keywords": ["anchor", "mechanical anchor"] },
      "JT-014": { "label": "Unknown / unclassified",      "geometry": "Tight",    "risk": 0.75, "ifc_keywords": [], "note": "Conservative default when joint type cannot be determined from IFC data" }
    }
  },
  "environment_severity": {
    "description": "Seven severity classes per EN ISO 15329:2007 wetting classification framework.",
    "source": "EN ISO 15329:2007",
    "classes": {
      "T0_DRY":          { "severity": 0.05, "chloride_mgl": "0",         "label": "Essentially dry — controlled indoor",       "wetness": "< 1% annual" },
      "T1_OCCASIONAL":   { "severity": 0.20, "chloride_mgl": "< 10",      "label": "Occasional condensation — normal indoor",   "wetness": "< 10% annual" },
      "T2_INTERMITTENT": { "severity": 0.40, "chloride_mgl": "< 50",      "label": "Intermittent wetting — humid plant room",   "wetness": "10-50% annual" },
      "T3_FREQUENT":     { "severity": 0.60, "chloride_mgl": "50-200",    "label": "Frequent wetting — external sheltered",     "wetness": "50-75% annual" },
      "T4_PERSISTENT":   { "severity": 0.80, "chloride_mgl": "200-1000",  "label": "Persistent wetting — external exposed",     "wetness": "> 75% annual" },
      "T5_IMMERSION":    { "severity": 1.00, "chloride_mgl": "> 1000",    "label": "Immersion / pool / marine — most severe",   "wetness": "continuous" },
      "BUILDING_SERVICES": { "severity": 0.35, "chloride_mgl": "variable", "label": "Internal building services pipework",       "wetness": "continuous internal", "reference": "CIBSE Guide G" }
    }
  },
  "high_risk_configurations": [
    {
      "config_id": "CC-HRC-001",
      "description": "SS316 flanged connection in pool plant room",
      "material": "ss316_passive", "joint": "JT-004", "environment": "T5_IMMERSION",
      "typical_temp_c": 35, "expected_score": 0.89, "expected_band": "Critical",
      "academic_significance": "GC-001 score 0.00 (Low) — this is the defining finding justifying the dual-engine architecture"
    },
    {
      "config_id": "CC-HRC-002",
      "description": "SS304 flanged connection in pool enclosure",
      "material": "ss304_passive", "joint": "JT-004", "environment": "T5_IMMERSION",
      "typical_temp_c": 25, "expected_score": 0.91, "expected_band": "Critical",
      "note": "SS304 CCT = -5 degrees C — at risk in any above-freezing environment with chloride"
    },
    {
      "config_id": "CC-HRC-003",
      "description": "SS316 threaded connection in humid plant room above 40°C",
      "material": "ss316_passive", "joint": "JT-005", "environment": "T2_INTERMITTENT",
      "typical_temp_c": 40, "expected_score": 0.85, "expected_band": "Critical",
      "note": "Threaded joint (Critical geometry) combined with operating above CCT"
    },
    {
      "config_id": "CC-HRC-004",
      "description": "SS304 compression fitting in normal indoor environment at 15°C",
      "material": "ss304_passive", "joint": "JT-006", "environment": "T1_OCCASIONAL",
      "typical_temp_c": 15, "expected_score": 0.66, "expected_band": "High",
      "note": "SS304 CCT only -5°C — modest temperature still 20°C above CCT"
    },
    {
      "config_id": "CC-HRC-005",
      "description": "Super Duplex 2507 flanged in pool environment at 45°C",
      "material": "superduplex2507", "joint": "JT-004", "environment": "T5_IMMERSION",
      "typical_temp_c": 45, "expected_score": 0.69, "expected_band": "High",
      "note": "CCT +50°C — only 5°C margin at 45°C operating temperature"
    }
  ],
  "mitigation_catalogue": {
    "MIT-CC-001": "Upgrade stainless steel grade — specify Duplex 2205 (CCT +25°C) or Super Duplex 2507 (CCT +50°C) per CIRIA C692",
    "MIT-CC-002": "Change joint type to reduce geometry class — specify butt weld instead of flanged or threaded connection",
    "MIT-CC-003": "Specify PTFE or elastomer gaskets with minimum crevice geometry at flange interface",
    "MIT-CC-004": "Apply crevice-resistant surface treatment — electropolishing or passivation per ASTM A967",
    "MIT-CC-005": "Reduce chloride concentration in operating environment — improve ventilation or drainage",
    "MIT-CC-006": "Lower operating temperature below material CCT — review system temperature setpoints",
    "MIT-CC-007": "Specify titanium Grade 2 (CCT +120°C) for elements in permanent high-chloride high-temperature service",
    "MIT-CC-008": "Implement periodic inspection regime at identified crevice geometry locations"
  },
  "pset_crevice_corrosion_risk_schema": {
    "pset_name": "Pset_CreviceCorrosionRisk",
    "ifc_entities": ["IfcPipeSegment", "IfcPipeFitting", "IfcFlowSegment"],
    "properties": [
      { "name": "CC001_CompositeScore",        "type": "IfcReal",     "description": "CC-001 composite risk score 0.0-1.0" },
      { "name": "CC001_RiskBand",              "type": "IfcLabel",    "description": "Low / Medium / High / Critical" },
      { "name": "CC001_JointTypeCode",         "type": "IfcLabel",    "description": "Joint type code JT-001 through JT-014" },
      { "name": "CC001_GeometryClass",         "type": "IfcLabel",    "description": "Open / Moderate / Tight / Critical" },
      { "name": "CC001_GeometryRisk",          "type": "IfcReal",     "description": "Geometry risk sub-score 0.0-1.0" },
      { "name": "CC001_OperatingTemp_C",       "type": "IfcReal",     "description": "Operating temperature in degrees C" },
      { "name": "CC001_CCT_C",                 "type": "IfcReal",     "description": "Critical Crevice Corrosion Temperature for specified grade" },
      { "name": "CC001_CCTAdequacyScore",      "type": "IfcReal",     "description": "CCT adequacy sub-score 0.0-1.0" },
      { "name": "CC001_CCTNote",               "type": "IfcText",     "description": "CCT adequacy explanation and margin" },
      { "name": "CC001_EnvironmentKey",        "type": "IfcLabel",    "description": "T0_DRY through T5_IMMERSION per EN ISO 15329:2007" },
      { "name": "CC001_EnvironmentSeverity",   "type": "IfcReal",     "description": "Environment severity score 0.0-1.0" },
      { "name": "CC001_RecommendedMitigation", "type": "IfcText",     "description": "Pipe-separated mitigation codes" },
      { "name": "CC001_RulesetVersion",        "type": "IfcLabel",    "description": "BIMGUARD-CC-001 ruleset version" },
      { "name": "CC001_AssessmentDate",        "type": "IfcDateTime", "description": "ISO 8601 UTC timestamp of assessment" }
    ]
  },
  "ifc_data_sources": {
    "material":           ["Pset_MaterialCommon.Name", "IfcMaterial.Name"],
    "joint_type":         ["IfcPipeFitting.PredefinedType", "Pset_PipeFittingOccurrence.ConnectionType", "IfcPipeSegmentType.ObjectType"],
    "operating_temp":     ["Pset_PipeSegmentOccurrence.OperatingTemperature", "Pset_ZoneCommon.SetPointTemperature"],
    "zone_category":      ["IfcZone.LongName", "IfcZone.Name", "Pset_ZoneCommon.Category"],
    "system_type":        ["IfcDistributionSystem.PredefinedType", "IfcDistributionSystem.LongName"]
  }
}
', '6c9c3d916b54461147bb2a461ea40f087ed25f85df6ec1ff549342d8fd958290', '', 1)
on conflict (asset_key) do update set
    source_path = excluded.source_path,
    format = excluded.format,
    content_json = excluded.content_json,
    content_text = excluded.content_text,
    content_sha256 = excluded.content_sha256,
    migrated_at = excluded.migrated_at,
    active = excluded.active;

insert into public.static_data_assets (asset_key, source_path, format, content_json, content_text, content_sha256, migrated_at, active)
values ('ruleset:BIMGUARD-MC-001', 'data/rulesets/mic_corrosion_ruleset.json', 'json', '{"dead_leg_classes": {"DL0_THROUGH": {"label": "Through-flow", "length_to_dia_ratio": "0", "reference": "HSE HSG274 Part 2", "risk": 0.05}, "DL1_SHORT": {"label": "Short (< 3D)", "length_to_dia_ratio": "< 3", "reference": "HSE HSG274 — below threshold", "risk": 0.3}, "DL2_MODERATE": {"label": "Moderate (3D–10D)", "length_to_dia_ratio": "3–10", "reference": "HSE HSG274 — exceeds threshold", "risk": 0.65}, "DL3_LONG": {"label": "Long (10D–20D)", "length_to_dia_ratio": "10–20", "reference": "HSE HSG274 — high risk", "risk": 0.85}, "DL4_CRITICAL": {"label": "Critical (> 20D)", "length_to_dia_ratio": "> 20", "reference": "HSE HSG274 — eliminate", "risk": 1.0}, "DL5_UNKNOWN": {"label": "Unknown topology", "length_to_dia_ratio": "n/a", "reference": "Conservative default", "risk": 0.5}}, "description": "BIMGUARD AI compliance ruleset for Microbially Influenced Corrosion (MIC) in MEP building services pipework. Covers dead-leg stagnation, Legionella risk temperature zones, under-insulation corrosion, and biofilm susceptibility by material and system type.", "flow_velocity_classes": {"FV0_STAGNANT": {"label": "Stagnant / dead-leg", "reference": "CIBSE TM13:2013", "risk": 1.0, "threshold_ms": 0.0}, "FV1_VERY_LOW": {"label": "Very low < 0.1 m/s", "reference": "HSE HSG274 Part 2", "risk": 0.8, "threshold_ms": 0.1}, "FV2_LOW": {"label": "Low 0.1–0.3 m/s", "reference": "HSE HSG274 Part 2", "risk": 0.55, "threshold_ms": 0.3}, "FV3_ACCEPTABLE": {"label": "Acceptable 0.3–0.6 m/s", "reference": "CIBSE Guide G", "risk": 0.25, "threshold_ms": 0.6}, "FV4_GOOD": {"label": "Good 0.6–1.5 m/s", "reference": "CIBSE Guide G", "risk": 0.1, "threshold_ms": 1.5}, "FV5_TURBULENT": {"label": "Turbulent > 1.5 m/s", "reference": "CIBSE Guide G", "risk": 0.02, "threshold_ms": 999}}, "high_risk_configurations": [{"config_id": "MIC-HRC-001", "description": "Domestic hot water dead-leg at Legionella danger zone temperature", "expected_band": "Critical", "expected_score_range": "0.85–1.00", "material": "carbon_steel", "reference": "HSE HSG274 Part 2 — hot water dead-legs", "system_type": "DOMESTICHOTWATER", "typical_dead_leg_ratio": ">10D", "typical_flow_velocity_ms": 0.0, "typical_temperature_c": 35.0}, {"config_id": "MIC-HRC-002", "description": "Fire suppression system — effectively permanent dead-leg", "expected_band": "Critical", "expected_score_range": "0.90–1.00", "material": "carbon_steel", "reference": "HSE HSG274 Part 3 — infrequent use systems", "system_type": "FIREPROTECTION", "typical_dead_leg_ratio": ">100D", "typical_flow_velocity_ms": 0.0, "typical_temperature_c": 22.0}, {"config_id": "MIC-HRC-003", "description": "Chilled water system with under-insulation wet condition", "expected_band": "High", "expected_score_range": "0.65–0.80", "insulation_condition": "wet", "material": "carbon_steel", "reference": "NACE SP0198 — under-insulation corrosion", "system_type": "CHILLEDWATER", "typical_flow_velocity_ms": 0.1, "typical_temperature_c": 10.0}, {"config_id": "MIC-HRC-004", "description": "Domestic cold water storage — temperature above 20°C due to heat gain", "expected_band": "Critical", "expected_score_range": "0.75–0.90", "material": "carbon_steel", "reference": "CIBSE TM13 — cold water storage risk", "system_type": "DOMESTICCOLDWATER", "typical_flow_velocity_ms": 0.05, "typical_temperature_c": 24.0}, {"config_id": "MIC-HRC-005", "description": "Condenser water warm loop with low recirculation", "expected_band": "High", "expected_score_range": "0.55–0.75", "material": "galv_steel", "reference": "HSE HSG274 Part 1 — evaporative cooling systems", "system_type": "CONDENSERWATER", "typical_flow_velocity_ms": 0.2, "typical_temperature_c": 30.0}], "ifc_data_sources": {"dead_leg_length": ["Calculated from IfcDistributionSystem topology — distance from last active junction to terminal"], "flow_velocity": ["Pset_PipeSegmentOccurrence.FlowVelocity", "Pset_Duct.AirFlowRate (converted)"], "insulation_condition": ["Pset_CoveringCommon.ThermalTransmittance (proxy for condition)", "Custom Pset_MaintenanceRecord.InsulationCondition"], "material": ["Pset_MaterialCommon.Name", "IfcMaterial.Name"], "operating_temperature": ["Pset_PipeSegmentOccurrence.OperatingTemperature", "Pset_ZoneCommon.SetPointTemperature"], "system_type": ["IfcDistributionSystem.PredefinedType", "IfcDistributionSystem.LongName"]}, "material_susceptibility": {"brass": {"label": "Brass (70/30)", "reference": "CIBSE Guide G", "score": 0.25}, "carbon_steel": {"label": "Carbon / mild steel", "reference": "ASTM G-187 / NACCE TPC 11", "score": 1.0}, "cast_iron": {"label": "Cast iron", "reference": "NACCE TPC 11", "score": 0.9}, "copper": {"label": "Copper", "reference": "CIBSE Guide G — antimicrobial properties", "score": 0.15}, "cpvc": {"label": "CPVC", "reference": "Non-metallic — biofilm substrate only", "score": 0.05}, "duplex2205": {"label": "Duplex 2205", "reference": "NACE / ASTM G-187", "score": 0.1}, "galv_steel": {"label": "Galvanised steel", "reference": "NACCE TPC 11", "score": 0.75}, "ss304": {"label": "Stainless steel 304", "reference": "ASTM G-187", "score": 0.3}, "ss316": {"label": "Stainless steel 316", "reference": "ASTM G-187", "score": 0.2}, "titanium": {"label": "Titanium", "reference": "ASTM G-187 — exceptional MIC resistance", "score": 0.05}}, "mechanism": "Microbially Influenced Corrosion (MIC)", "microbial_groups": {"APB": {"corrosion_mechanism": "Organic acid production lowers local pH — destroys passive films on stainless steel grades. Enables pitting initiation below normal CCT.", "flow_preference": "Biofilm — can be aerobic or anaerobic", "name": "Acid-Producing Bacteria", "pipe_materials_at_risk": ["ss304", "ss316", "carbon_steel", "aluminium"], "reference": "CIBSE Guide G / NACCE TPC 11", "temperature_range_c": "15–45"}, "IOB": {"corrosion_mechanism": "Creates differential aeration cells — accelerated pitting at aerobic/anaerobic interfaces. Tubercle formation restricts flow.", "flow_preference": "Aerobic zones — low flow allows oxygen stratification", "name": "Iron-Oxidising Bacteria", "pipe_materials_at_risk": ["carbon_steel", "cast_iron"], "reference": "NACCE TPC 11", "temperature_range_c": "10–35"}, "Legionella": {"corrosion_mechanism": "Not a direct corrosion agent — health hazard through inhalation of contaminated aerosol. Biofilm forms on pipe scale and corrosion products.", "flow_preference": "Stagnant warm water — dead-legs and low-use outlets", "name": "Legionella pneumophila", "pipe_materials_at_risk": ["all_system_types"], "reference": "CIBSE TM13:2013 / HSE HSG274", "temperature_range_c": "20–45 (optimal 35–46, survival to 55, killed at 60+)"}, "SRB": {"corrosion_mechanism": "Hydrogen sulphide production under biofilm — aggressive pitting of carbon steel and cast iron. Forms iron sulphide (FeS) corrosion product.", "flow_preference": "Anaerobic — stagnant or very low flow", "name": "Sulphate-Reducing Bacteria", "pipe_materials_at_risk": ["carbon_steel", "cast_iron", "galv_steel", "ss304"], "reference": "ASTM G-187 / NACCE TPC 11", "temperature_range_c": "15–65 (mesophilic 25–35, thermophilic 45–65)"}}, "mitigation_catalogue": {"MIT-MIC-001": "Eliminate dead-leg — reconfigure pipework to active through-flow configuration (HSE HSG274 preferred solution)", "MIT-MIC-002": "Install automatic flushing device — programme to flush weekly at minimum (CIBSE TM13 requirement)", "MIT-MIC-003": "Increase design flow velocity to minimum 0.3 m/s — revise pipe sizing or reroute to reduce network length", "MIT-MIC-004": "Raise hot water storage and distribution temperature to minimum 60°C storage / 55°C at outlets (HSE HSG274 Part 2)", "MIT-MIC-005": "Reduce cold water temperature to below 20°C — review insulation against heat gain from adjacent services", "MIT-MIC-006": "Specify copper or CPVC pipework in replacement — antimicrobial material substitution", "MIT-MIC-007": "Repair or replace damaged/wet insulation — prevent under-insulation moisture accumulation", "MIT-MIC-008": "Implement biocide dosing programme — chlorination or alternative biocide per BS 8552", "MIT-MIC-009": "Introduce microbiological monitoring programme — EN ISO 9308-1 sampling at identified risk points", "MIT-MIC-010": "Conduct thermal disinfection — pasteurisation at minimum 70°C for 1 hour (CIBSE TM13 emergency response)"}, "pset_mic_risk_schema": {"properties": [{"description": "MC-001 composite risk score (0.0–1.0)", "name": "MICRiskScore", "type": "IfcReal"}, {"description": "Risk band: Low / Medium / High / Critical", "name": "MICRiskBand", "type": "IfcLabel"}, {"description": "Flow velocity classification per CIBSE TM13", "name": "FlowVelocityClass", "type": "IfcLabel"}, {"description": "Temperature risk class per CIBSE TM13 / HSE HSG274", "name": "TemperatureClass", "type": "IfcLabel"}, {"description": "Dead-leg geometry classification per HSE HSG274", "name": "DeadLegClass", "type": "IfcLabel"}, {"description": "Material MIC susceptibility sub-score (0.0–1.0)", "name": "MaterialSusceptibility", "type": "IfcReal"}, {"description": "Under-insulation corrosion pathway risk (0.0–1.0)", "name": "UnderInsulationRisk", "type": "IfcReal"}, {"description": "System type risk multiplier", "name": "SystemTypeModifier", "type": "IfcReal"}, {"description": "Pipe-separated list of mitigation codes from MC-001 catalogue", "name": "RecommendedMitigation", "type": "IfcText"}, {"description": "MC-001 ruleset version string", "name": "RulesetVersion", "type": "IfcLabel"}, {"description": "ISO 8601 timestamp of assessment run", "name": "AssessmentDate", "type": "IfcDateTime"}], "pset_name": "Pset_MICRisk"}, "risk_bands": {"Critical": {"bcf_action": "BCF Critical priority — immediate remediation or shutdown required", "range": "> 0.75"}, "High": {"bcf_action": "BCF Major priority — remediation required within 3 months", "range": "0.50 – 0.75"}, "Low": {"bcf_action": "Record in asset register — no BCF issue", "range": "< 0.25"}, "Medium": {"bcf_action": "BCF Normal priority — schedule monitoring programme", "range": "0.25 – 0.50"}}, "ruleset_id": "BIMGUARD-MC-001", "ruleset_version": "1.0.0", "scoring_model": {"formula": "Score_MC = (0.35 × flow_velocity_risk) + (0.30 × temperature_risk) + (0.25 × dead_leg_risk) + (0.10 × material_susceptibility)", "rationale": "Flow velocity receives highest weight (0.35) because stagnation is the necessary precondition for all MIC mechanisms — without stagnation, biofilms cannot establish at scale. Temperature receives 0.30 because it determines which microbial communities are active and whether Legionella proliferation is possible. Dead-leg geometry receives 0.25 as the structural enabler of stagnation. Material susceptibility receives 0.10 because it modifies the consequence of biofilm establishment but does not prevent it.", "system_modifier": "Base score × system_type_multiplier (capped at 1.00)", "under_insulation_pathway": "If under-insulation risk × 0.85 > modified score, UIC pathway score used instead (worst-case of two independent pathways)", "weights": {"dead_leg_risk": 0.25, "flow_velocity_risk": 0.35, "material_susceptibility": 0.1, "temperature_risk": 0.3}}, "standards_referenced": ["CIBSE TM13:2013 — Minimising the Risk of Legionella", "HSE HSG274 Part 1 — Evaporative Cooling Systems", "HSE HSG274 Part 2 — Hot and Cold Water Systems", "HSE HSG274 Part 3 — Other Risk Systems", "BS 8552:2012 — Sampling and Monitoring of Water Systems", "ASTM G-187 — Standard Practice for Measurement of Soil Resistivity", "EN ISO 9308-1 — Water Quality Microbiological Methods", "WHO Guidelines for Drinking Water Quality 4th Ed. (2011)", "NACCE TPC 11 — MIC in Industrial Water Systems", "NACE SP0198 — Control of Corrosion Under Thermal Insulation", "CIBSE Guide G — Public Health Engineering"], "system_type_modifiers": {"CHILLEDWATER": {"multiplier": 1.15, "rationale": "7–12°C chilled water — biofilm active, low flow zones at risk"}, "CONDENSERWATER": {"multiplier": 1.2, "rationale": "Warm recirculating system — high MIC risk — HSE HSG274 Part 1"}, "DOMESTICCOLDWATER": {"multiplier": 1.3, "rationale": "Primary Legionella risk system — CIBSE TM13 mandatory risk assessment"}, "DOMESTICHOTWATER": {"multiplier": 1.25, "rationale": "Legionella proliferation if distribution temperature < 55°C — HSE HSG274 Part 2"}, "FIREPROTECTION": {"multiplier": 1.4, "rationale": "Infrequent / zero flow — highest dead-leg stagnation risk — HSE HSG274 Part 3"}, "IRRIGATION": {"multiplier": 1.1, "rationale": "Intermittent flow — warm conditions in summer"}, "PROCESSWATER": {"multiplier": 1.0, "rationale": "Risk depends on operating conditions — no modifier"}, "UNKNOWN": {"multiplier": 1.05, "rationale": "Conservative uplift for unknown system type"}, "WASTEWATER": {"multiplier": 0.8, "rationale": "Anaerobic SRB active but Legionella consequence lower"}}, "temperature_classes": {"T0_COLD": {"range": "< 20°C", "reference": "WHO GDWQ 4th Ed. — cold water <20°C", "risk": 0.15}, "T1_MARGINAL": {"range": "20–25°C", "reference": "CIBSE TM13 — marginal zone", "risk": 0.35}, "T2_DANGER": {"range": "25–45°C", "reference": "CIBSE TM13:2013 — Legionella danger zone", "risk": 1.0}, "T3_TOLERABLE": {"range": "45–55°C", "reference": "HSE HSG274 — Legionella above optimum", "risk": 0.45}, "T4_SAFE_HOT": {"range": "> 55°C", "reference": "CIBSE TM13 — Legionella destroyed >60°C", "risk": 0.05}, "T5_UNKNOWN": {"range": "Unknown", "reference": "Conservative default", "risk": 0.65}}, "under_insulation_risk": {"damaged": 0.8, "good_condition": 0.1, "none": 0.0, "unknown": 0.35, "weathered": 0.45, "wet": 1.0}}', '{
  "ruleset_id": "BIMGUARD-MC-001",
  "ruleset_version": "1.0.0",
  "mechanism": "Microbially Influenced Corrosion (MIC)",
  "description": "BIMGUARD AI compliance ruleset for Microbially Influenced Corrosion (MIC) in MEP building services pipework. Covers dead-leg stagnation, Legionella risk temperature zones, under-insulation corrosion, and biofilm susceptibility by material and system type.",
  "standards_referenced": [
    "CIBSE TM13:2013 — Minimising the Risk of Legionella",
    "HSE HSG274 Part 1 — Evaporative Cooling Systems",
    "HSE HSG274 Part 2 — Hot and Cold Water Systems",
    "HSE HSG274 Part 3 — Other Risk Systems",
    "BS 8552:2012 — Sampling and Monitoring of Water Systems",
    "ASTM G-187 — Standard Practice for Measurement of Soil Resistivity",
    "EN ISO 9308-1 — Water Quality Microbiological Methods",
    "WHO Guidelines for Drinking Water Quality 4th Ed. (2011)",
    "NACCE TPC 11 — MIC in Industrial Water Systems",
    "NACE SP0198 — Control of Corrosion Under Thermal Insulation",
    "CIBSE Guide G — Public Health Engineering"
  ],
  "scoring_model": {
    "formula": "Score_MC = (0.35 × flow_velocity_risk) + (0.30 × temperature_risk) + (0.25 × dead_leg_risk) + (0.10 × material_susceptibility)",
    "system_modifier": "Base score × system_type_multiplier (capped at 1.00)",
    "under_insulation_pathway": "If under-insulation risk × 0.85 > modified score, UIC pathway score used instead (worst-case of two independent pathways)",
    "weights": {
      "flow_velocity_risk": 0.35,
      "temperature_risk": 0.30,
      "dead_leg_risk": 0.25,
      "material_susceptibility": 0.10
    },
    "rationale": "Flow velocity receives highest weight (0.35) because stagnation is the necessary precondition for all MIC mechanisms — without stagnation, biofilms cannot establish at scale. Temperature receives 0.30 because it determines which microbial communities are active and whether Legionella proliferation is possible. Dead-leg geometry receives 0.25 as the structural enabler of stagnation. Material susceptibility receives 0.10 because it modifies the consequence of biofilm establishment but does not prevent it."
  },
  "risk_bands": {
    "Low":     {"range": "< 0.25",      "bcf_action": "Record in asset register — no BCF issue"},
    "Medium":  {"range": "0.25 – 0.50", "bcf_action": "BCF Normal priority — schedule monitoring programme"},
    "High":    {"range": "0.50 – 0.75", "bcf_action": "BCF Major priority — remediation required within 3 months"},
    "Critical":{"range": "> 0.75",      "bcf_action": "BCF Critical priority — immediate remediation or shutdown required"}
  },
  "microbial_groups": {
    "SRB": {
      "name": "Sulphate-Reducing Bacteria",
      "temperature_range_c": "15–65 (mesophilic 25–35, thermophilic 45–65)",
      "flow_preference": "Anaerobic — stagnant or very low flow",
      "corrosion_mechanism": "Hydrogen sulphide production under biofilm — aggressive pitting of carbon steel and cast iron. Forms iron sulphide (FeS) corrosion product.",
      "pipe_materials_at_risk": ["carbon_steel", "cast_iron", "galv_steel", "ss304"],
      "reference": "ASTM G-187 / NACCE TPC 11"
    },
    "IOB": {
      "name": "Iron-Oxidising Bacteria",
      "temperature_range_c": "10–35",
      "flow_preference": "Aerobic zones — low flow allows oxygen stratification",
      "corrosion_mechanism": "Creates differential aeration cells — accelerated pitting at aerobic/anaerobic interfaces. Tubercle formation restricts flow.",
      "pipe_materials_at_risk": ["carbon_steel", "cast_iron"],
      "reference": "NACCE TPC 11"
    },
    "APB": {
      "name": "Acid-Producing Bacteria",
      "temperature_range_c": "15–45",
      "flow_preference": "Biofilm — can be aerobic or anaerobic",
      "corrosion_mechanism": "Organic acid production lowers local pH — destroys passive films on stainless steel grades. Enables pitting initiation below normal CCT.",
      "pipe_materials_at_risk": ["ss304", "ss316", "carbon_steel", "aluminium"],
      "reference": "CIBSE Guide G / NACCE TPC 11"
    },
    "Legionella": {
      "name": "Legionella pneumophila",
      "temperature_range_c": "20–45 (optimal 35–46, survival to 55, killed at 60+)",
      "flow_preference": "Stagnant warm water — dead-legs and low-use outlets",
      "corrosion_mechanism": "Not a direct corrosion agent — health hazard through inhalation of contaminated aerosol. Biofilm forms on pipe scale and corrosion products.",
      "pipe_materials_at_risk": ["all_system_types"],
      "reference": "CIBSE TM13:2013 / HSE HSG274"
    }
  },
  "flow_velocity_classes": {
    "FV0_STAGNANT":   {"label": "Stagnant / dead-leg",       "threshold_ms": 0.0,  "risk": 1.00, "reference": "CIBSE TM13:2013"},
    "FV1_VERY_LOW":   {"label": "Very low < 0.1 m/s",        "threshold_ms": 0.1,  "risk": 0.80, "reference": "HSE HSG274 Part 2"},
    "FV2_LOW":        {"label": "Low 0.1–0.3 m/s",           "threshold_ms": 0.3,  "risk": 0.55, "reference": "HSE HSG274 Part 2"},
    "FV3_ACCEPTABLE": {"label": "Acceptable 0.3–0.6 m/s",    "threshold_ms": 0.6,  "risk": 0.25, "reference": "CIBSE Guide G"},
    "FV4_GOOD":       {"label": "Good 0.6–1.5 m/s",          "threshold_ms": 1.5,  "risk": 0.10, "reference": "CIBSE Guide G"},
    "FV5_TURBULENT":  {"label": "Turbulent > 1.5 m/s",       "threshold_ms": 999,  "risk": 0.02, "reference": "CIBSE Guide G"}
  },
  "temperature_classes": {
    "T0_COLD":      {"range": "< 20°C",   "risk": 0.15, "reference": "WHO GDWQ 4th Ed. — cold water <20°C"},
    "T1_MARGINAL":  {"range": "20–25°C",  "risk": 0.35, "reference": "CIBSE TM13 — marginal zone"},
    "T2_DANGER":    {"range": "25–45°C",  "risk": 1.00, "reference": "CIBSE TM13:2013 — Legionella danger zone"},
    "T3_TOLERABLE": {"range": "45–55°C",  "risk": 0.45, "reference": "HSE HSG274 — Legionella above optimum"},
    "T4_SAFE_HOT":  {"range": "> 55°C",   "risk": 0.05, "reference": "CIBSE TM13 — Legionella destroyed >60°C"},
    "T5_UNKNOWN":   {"range": "Unknown",   "risk": 0.65, "reference": "Conservative default"}
  },
  "dead_leg_classes": {
    "DL0_THROUGH":  {"label": "Through-flow",       "length_to_dia_ratio": "0",      "risk": 0.05, "reference": "HSE HSG274 Part 2"},
    "DL1_SHORT":    {"label": "Short (< 3D)",        "length_to_dia_ratio": "< 3",    "risk": 0.30, "reference": "HSE HSG274 — below threshold"},
    "DL2_MODERATE": {"label": "Moderate (3D–10D)",   "length_to_dia_ratio": "3–10",   "risk": 0.65, "reference": "HSE HSG274 — exceeds threshold"},
    "DL3_LONG":     {"label": "Long (10D–20D)",      "length_to_dia_ratio": "10–20",  "risk": 0.85, "reference": "HSE HSG274 — high risk"},
    "DL4_CRITICAL": {"label": "Critical (> 20D)",    "length_to_dia_ratio": "> 20",   "risk": 1.00, "reference": "HSE HSG274 — eliminate"},
    "DL5_UNKNOWN":  {"label": "Unknown topology",    "length_to_dia_ratio": "n/a",    "risk": 0.50, "reference": "Conservative default"}
  },
  "material_susceptibility": {
    "carbon_steel":  {"score": 1.00, "label": "Carbon / mild steel",    "reference": "ASTM G-187 / NACCE TPC 11"},
    "cast_iron":     {"score": 0.90, "label": "Cast iron",              "reference": "NACCE TPC 11"},
    "galv_steel":    {"score": 0.75, "label": "Galvanised steel",       "reference": "NACCE TPC 11"},
    "ss304":         {"score": 0.30, "label": "Stainless steel 304",    "reference": "ASTM G-187"},
    "ss316":         {"score": 0.20, "label": "Stainless steel 316",    "reference": "ASTM G-187"},
    "duplex2205":    {"score": 0.10, "label": "Duplex 2205",            "reference": "NACE / ASTM G-187"},
    "copper":        {"score": 0.15, "label": "Copper",                 "reference": "CIBSE Guide G — antimicrobial properties"},
    "brass":         {"score": 0.25, "label": "Brass (70/30)",          "reference": "CIBSE Guide G"},
    "cpvc":          {"score": 0.05, "label": "CPVC",                   "reference": "Non-metallic — biofilm substrate only"},
    "titanium":      {"score": 0.05, "label": "Titanium",               "reference": "ASTM G-187 — exceptional MIC resistance"}
  },
  "system_type_modifiers": {
    "DOMESTICCOLDWATER": {"multiplier": 1.30, "rationale": "Primary Legionella risk system — CIBSE TM13 mandatory risk assessment"},
    "DOMESTICHOTWATER":  {"multiplier": 1.25, "rationale": "Legionella proliferation if distribution temperature < 55°C — HSE HSG274 Part 2"},
    "CONDENSERWATER":    {"multiplier": 1.20, "rationale": "Warm recirculating system — high MIC risk — HSE HSG274 Part 1"},
    "CHILLEDWATER":      {"multiplier": 1.15, "rationale": "7–12°C chilled water — biofilm active, low flow zones at risk"},
    "FIREPROTECTION":    {"multiplier": 1.40, "rationale": "Infrequent / zero flow — highest dead-leg stagnation risk — HSE HSG274 Part 3"},
    "IRRIGATION":        {"multiplier": 1.10, "rationale": "Intermittent flow — warm conditions in summer"},
    "WASTEWATER":        {"multiplier": 0.80, "rationale": "Anaerobic SRB active but Legionella consequence lower"},
    "PROCESSWATER":      {"multiplier": 1.00, "rationale": "Risk depends on operating conditions — no modifier"},
    "UNKNOWN":           {"multiplier": 1.05, "rationale": "Conservative uplift for unknown system type"}
  },
  "under_insulation_risk": {
    "none":            0.00,
    "good_condition":  0.10,
    "weathered":       0.45,
    "damaged":         0.80,
    "wet":             1.00,
    "unknown":         0.35
  },
  "mitigation_catalogue": {
    "MIT-MIC-001": "Eliminate dead-leg — reconfigure pipework to active through-flow configuration (HSE HSG274 preferred solution)",
    "MIT-MIC-002": "Install automatic flushing device — programme to flush weekly at minimum (CIBSE TM13 requirement)",
    "MIT-MIC-003": "Increase design flow velocity to minimum 0.3 m/s — revise pipe sizing or reroute to reduce network length",
    "MIT-MIC-004": "Raise hot water storage and distribution temperature to minimum 60°C storage / 55°C at outlets (HSE HSG274 Part 2)",
    "MIT-MIC-005": "Reduce cold water temperature to below 20°C — review insulation against heat gain from adjacent services",
    "MIT-MIC-006": "Specify copper or CPVC pipework in replacement — antimicrobial material substitution",
    "MIT-MIC-007": "Repair or replace damaged/wet insulation — prevent under-insulation moisture accumulation",
    "MIT-MIC-008": "Implement biocide dosing programme — chlorination or alternative biocide per BS 8552",
    "MIT-MIC-009": "Introduce microbiological monitoring programme — EN ISO 9308-1 sampling at identified risk points",
    "MIT-MIC-010": "Conduct thermal disinfection — pasteurisation at minimum 70°C for 1 hour (CIBSE TM13 emergency response)"
  },
  "pset_mic_risk_schema": {
    "pset_name": "Pset_MICRisk",
    "properties": [
      {"name": "MICRiskScore",          "type": "IfcReal",   "description": "MC-001 composite risk score (0.0–1.0)"},
      {"name": "MICRiskBand",           "type": "IfcLabel",  "description": "Risk band: Low / Medium / High / Critical"},
      {"name": "FlowVelocityClass",     "type": "IfcLabel",  "description": "Flow velocity classification per CIBSE TM13"},
      {"name": "TemperatureClass",      "type": "IfcLabel",  "description": "Temperature risk class per CIBSE TM13 / HSE HSG274"},
      {"name": "DeadLegClass",          "type": "IfcLabel",  "description": "Dead-leg geometry classification per HSE HSG274"},
      {"name": "MaterialSusceptibility","type": "IfcReal",   "description": "Material MIC susceptibility sub-score (0.0–1.0)"},
      {"name": "UnderInsulationRisk",   "type": "IfcReal",   "description": "Under-insulation corrosion pathway risk (0.0–1.0)"},
      {"name": "SystemTypeModifier",    "type": "IfcReal",   "description": "System type risk multiplier"},
      {"name": "RecommendedMitigation", "type": "IfcText",   "description": "Pipe-separated list of mitigation codes from MC-001 catalogue"},
      {"name": "RulesetVersion",        "type": "IfcLabel",  "description": "MC-001 ruleset version string"},
      {"name": "AssessmentDate",        "type": "IfcDateTime","description": "ISO 8601 timestamp of assessment run"}
    ]
  },
  "high_risk_configurations": [
    {
      "config_id": "MIC-HRC-001",
      "description": "Domestic hot water dead-leg at Legionella danger zone temperature",
      "system_type": "DOMESTICHOTWATER",
      "material": "carbon_steel",
      "typical_flow_velocity_ms": 0.0,
      "typical_temperature_c": 35.0,
      "typical_dead_leg_ratio": ">10D",
      "expected_score_range": "0.85–1.00",
      "expected_band": "Critical",
      "reference": "HSE HSG274 Part 2 — hot water dead-legs"
    },
    {
      "config_id": "MIC-HRC-002",
      "description": "Fire suppression system — effectively permanent dead-leg",
      "system_type": "FIREPROTECTION",
      "material": "carbon_steel",
      "typical_flow_velocity_ms": 0.0,
      "typical_temperature_c": 22.0,
      "typical_dead_leg_ratio": ">100D",
      "expected_score_range": "0.90–1.00",
      "expected_band": "Critical",
      "reference": "HSE HSG274 Part 3 — infrequent use systems"
    },
    {
      "config_id": "MIC-HRC-003",
      "description": "Chilled water system with under-insulation wet condition",
      "system_type": "CHILLEDWATER",
      "material": "carbon_steel",
      "typical_flow_velocity_ms": 0.1,
      "typical_temperature_c": 10.0,
      "insulation_condition": "wet",
      "expected_score_range": "0.65–0.80",
      "expected_band": "High",
      "reference": "NACE SP0198 — under-insulation corrosion"
    },
    {
      "config_id": "MIC-HRC-004",
      "description": "Domestic cold water storage — temperature above 20°C due to heat gain",
      "system_type": "DOMESTICCOLDWATER",
      "material": "carbon_steel",
      "typical_flow_velocity_ms": 0.05,
      "typical_temperature_c": 24.0,
      "expected_score_range": "0.75–0.90",
      "expected_band": "Critical",
      "reference": "CIBSE TM13 — cold water storage risk"
    },
    {
      "config_id": "MIC-HRC-005",
      "description": "Condenser water warm loop with low recirculation",
      "system_type": "CONDENSERWATER",
      "material": "galv_steel",
      "typical_flow_velocity_ms": 0.2,
      "typical_temperature_c": 30.0,
      "expected_score_range": "0.55–0.75",
      "expected_band": "High",
      "reference": "HSE HSG274 Part 1 — evaporative cooling systems"
    }
  ],
  "ifc_data_sources": {
    "flow_velocity": ["Pset_PipeSegmentOccurrence.FlowVelocity", "Pset_Duct.AirFlowRate (converted)"],
    "operating_temperature": ["Pset_PipeSegmentOccurrence.OperatingTemperature", "Pset_ZoneCommon.SetPointTemperature"],
    "dead_leg_length": ["Calculated from IfcDistributionSystem topology — distance from last active junction to terminal"],
    "material": ["Pset_MaterialCommon.Name", "IfcMaterial.Name"],
    "insulation_condition": ["Pset_CoveringCommon.ThermalTransmittance (proxy for condition)", "Custom Pset_MaintenanceRecord.InsulationCondition"],
    "system_type": ["IfcDistributionSystem.PredefinedType", "IfcDistributionSystem.LongName"]
  }
}
', '6222747a77c073fd667b610048f3349ba6010c2863393ad292a17b9856e6b3df', '', 1)
on conflict (asset_key) do update set
    source_path = excluded.source_path,
    format = excluded.format,
    content_json = excluded.content_json,
    content_text = excluded.content_text,
    content_sha256 = excluded.content_sha256,
    migrated_at = excluded.migrated_at,
    active = excluded.active;

insert into public.static_data_assets (asset_key, source_path, format, content_json, content_text, content_sha256, migrated_at, active)
values ('ifc-schema:bimguard-ifc4-export', 'data/BIMGuard_IFC4_Export.json', 'json', '{"ActivePhaseId": -1, "COBieCompanyInfo": "", "COBieProjectInfo": "", "CategoryMapping": null, "ClassificationSettings": {"ClassificationEdition": null, "ClassificationEditionDate": "/Date(1782777600000)/", "ClassificationFieldName": null, "ClassificationLocation": null, "ClassificationName": null, "ClassificationSource": null}, "ExchangeRequirement": 3, "ExcludeFilter": "", "Export2DElements": false, "ExportBarsInUniformSetsAsSeparateIFCEntities": false, "ExportBaseQuantities": true, "ExportBoundingBox": false, "ExportCeilingGrids": false, "ExportHostAsSingleEntity": false, "ExportIFCCommonPropertySets": true, "ExportInternalRevitPropertySets": true, "ExportLinkedFiles": 0, "ExportMaterialPsets": true, "ExportPartsAsBuildingElements": false, "ExportRoomsInView": false, "ExportSchedulesAsPsets": false, "ExportSolidModelRep": false, "ExportSpecificSchedules": false, "ExportUserDefinedParameterMapping": false, "ExportUserDefinedParameterMappingFileName": "", "ExportUserDefinedPsets": false, "ExportUserDefinedPsetsFileName": "", "FacilityPredefinedType": null, "FacilityType": 0, "GeoRefCRSDesc": "", "GeoRefCRSName": "", "GeoRefEPSGCode": "", "GeoRefGeodeticDatum": "", "GeoRefMapUnit": "", "IFCFileType": 0, "IFCVersion": 26, "IncludeSiteElevation": false, "IncludeSteelElements": true, "Name": "BIMGuard IFC4 Export", "OwnerHistoryLastModified": false, "ProjectAddress": {"AssignAddressToBuilding": true, "AssignAddressToSite": false, "UpdateProjectInformation": false}, "SelectedSite": "Internal", "SitePlacement": 0, "SpaceBoundaries": 1, "SplitWallsAndColumns": false, "StoreIFCGUID": true, "TessellationLevelOfDetail": 0.5, "Use2DRoomBoundaryForVolume": true, "UseActiveViewGeometry": false, "UseFamilyAndTypeNameForReference": false, "UseOnlyTriangulation": false, "UseTypeNameOnlyForIfcType": false, "UseTypePropertiesInInstacePSets": true, "UseVisibleRevitNameAsEntityName": true, "VisibleElementsOfCurrentView": false}', '{
  "IFCVersion": 26,
  "ExchangeRequirement": 3,
  "FacilityType": 0,
  "FacilityPredefinedType": null,
  "CategoryMapping": null,
  "IFCFileType": 0,
  "ActivePhaseId": -1,
  "SpaceBoundaries": 1,
  "SplitWallsAndColumns": false,
  "IncludeSteelElements": true,
  "ProjectAddress": {
    "UpdateProjectInformation": false,
    "AssignAddressToSite": false,
    "AssignAddressToBuilding": true
  },
  "Export2DElements": false,
  "ExportLinkedFiles": 0,
  "VisibleElementsOfCurrentView": false,
  "ExportRoomsInView": false,
  "ExportInternalRevitPropertySets": true,
  "ExportIFCCommonPropertySets": true,
  "ExportBaseQuantities": true,
  "ExportCeilingGrids": false,
  "ExportMaterialPsets": true,
  "ExportSchedulesAsPsets": false,
  "ExportSpecificSchedules": false,
  "ExportUserDefinedPsets": false,
  "ExportUserDefinedPsetsFileName": "",
  "UseTypePropertiesInInstacePSets": true,
  "ExportUserDefinedParameterMapping": false,
  "ExportUserDefinedParameterMappingFileName": "",
  "ClassificationSettings": {
    "ClassificationName": null,
    "ClassificationEdition": null,
    "ClassificationSource": null,
    "ClassificationEditionDate": "\/Date(1782777600000)\/",
    "ClassificationLocation": null,
    "ClassificationFieldName": null
  },
  "TessellationLevelOfDetail": 0.5,
  "ExportPartsAsBuildingElements": false,
  "ExportSolidModelRep": false,
  "UseActiveViewGeometry": false,
  "UseFamilyAndTypeNameForReference": false,
  "Use2DRoomBoundaryForVolume": true,
  "IncludeSiteElevation": false,
  "StoreIFCGUID": true,
  "ExportBoundingBox": false,
  "UseOnlyTriangulation": false,
  "UseTypeNameOnlyForIfcType": false,
  "ExportHostAsSingleEntity": false,
  "OwnerHistoryLastModified": false,
  "ExportBarsInUniformSetsAsSeparateIFCEntities": false,
  "UseVisibleRevitNameAsEntityName": true,
  "SelectedSite": "Internal",
  "SitePlacement": 0,
  "GeoRefCRSName": "",
  "GeoRefCRSDesc": "",
  "GeoRefEPSGCode": "",
  "GeoRefGeodeticDatum": "",
  "GeoRefMapUnit": "",
  "ExcludeFilter": "",
  "COBieCompanyInfo": "",
  "COBieProjectInfo": "",
  "Name": "BIMGuard IFC4 Export"
}
', 'c28b6838b7f9ca46ee6fd75ad40b857490e2ed320775ef95cb487471400fc0d1', '', 1)
on conflict (asset_key) do update set
    source_path = excluded.source_path,
    format = excluded.format,
    content_json = excluded.content_json,
    content_text = excluded.content_text,
    content_sha256 = excluded.content_sha256,
    migrated_at = excluded.migrated_at,
    active = excluded.active;

insert into public.static_data_assets (asset_key, source_path, format, content_json, content_text, content_sha256, migrated_at, active)
values ('issue-history:legacy', 'data/bimguard_issue_history.json', 'json', '{"0FQ6pMwzXBJucYaRTqfuw2": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "90a6965a", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "b74a1703", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "0FQ6pMwzXBJucYaRTqfuw2", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "0RPLlDbKvCJwFzsj8RPg4X": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "b9716788", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "391c2cb0", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "0RPLlDbKvCJwFzsj8RPg4X", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "0SESIjUgvFsOoEqvCaV5Br": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "3f281fb5", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "f25ee45e", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "0SESIjUgvFsOoEqvCaV5Br", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "0URFt4JXXD6OjZF8OrkR8N": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "d5284ac1", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "eefd4754", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "0URFt4JXXD6OjZF8OrkR8N", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "0X_fsZ0Kj9a8olHcZQNbJM": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "5c1d392d", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "f909ee92", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "0X_fsZ0Kj9a8olHcZQNbJM", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "0_AaoqH0fA_wWg2hQ6QoLY": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "43f0fbf5", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "473a899e", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "0_AaoqH0fA_wWg2hQ6QoLY", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "0tZgj2n4j7neNsQ08k3WsT": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "f1893d82", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "f901fe88", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "0tZgj2n4j7neNsQ08k3WsT", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "0uGYOC9Nz33PfGM5uuVHhW": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "e3b50860", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "2753c4ad", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "0uGYOC9Nz33PfGM5uuVHhW", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "0yh8Z9_qzCIgcsXg7r4Ix6": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "cd62cde0", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "adbd98a7", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "0yh8Z9_qzCIgcsXg7r4Ix6", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "11LWvWX7HAOghcDUC_Fsn5": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "e4a65927", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "525dd7d3", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "11LWvWX7HAOghcDUC_Fsn5", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "1F4KLUGJf1aAa0YXxTvOR5": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "0afc84b5", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "34a5f915", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "1F4KLUGJf1aAa0YXxTvOR5", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "1FDcvNA_L4dfRDGP$UNpz1": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "8b28b69f", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "a1aa0795", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "1FDcvNA_L4dfRDGP$UNpz1", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "1GXiy3xWf0fOQdC$gO8JfW": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "7043a589", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "fe7ce517", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "1GXiy3xWf0fOQdC$gO8JfW", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "1PI8m4Ts17Z8hvG889Pb1i": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "ef787585", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "19052b96", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "1PI8m4Ts17Z8hvG889Pb1i", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "1PYbWto7LA0hTpEdNPg6Df": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "3c84d835", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "632fdd66", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "1PYbWto7LA0hTpEdNPg6Df", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "1kpVA_DFf3PRJR$l8yqtLr": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "8f516cac", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "a697326e", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "1kpVA_DFf3PRJR$l8yqtLr", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "1wwTT4jtX3C9e82mYC6YGT": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "eb76e367", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "e8d0b37c", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "1wwTT4jtX3C9e82mYC6YGT", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "22Xr2mF15CbQCVR$W_$VLh": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "c4894d11", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "9b2d8db7", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "22Xr2mF15CbQCVR$W_$VLh", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "259jK4QKD3OPEdfCl4GH_l": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "f2783c3c", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "ddd95d9b", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "259jK4QKD3OPEdfCl4GH_l", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "2L8jfzclb09OjhbeQoBDvs": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "65357f21", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "e09f2679", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "2L8jfzclb09OjhbeQoBDvs", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "335CA3DF-171F-4E3F-BA4": {"current_band": "Medium", "current_status": "open", "element_type": "IfcFastener", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.58, "event_id": "72f67851", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "335CA3DF-171F-4E3F-BA4", "last_seen": "2026-04-09T18:47:08Z", "material": "Aluminum_alloy_6063", "system_type": "Weathering"}, "398dvTdH9FKwML6pMEemhK": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "da80e252", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "352443dc", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "398dvTdH9FKwML6pMEemhK", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "3Awuj1sjH8ERw7F1J6oBZs": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "ad7ae7f8", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "c499b4f7", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "3Awuj1sjH8ERw7F1J6oBZs", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "3D4ahkhjP7dujyPNisZ2F$": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "7167a485", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "e2b7164f", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "3D4ahkhjP7dujyPNisZ2F$", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "3ctB5z6nHCoQBWFJYnFhI5": {"current_band": "Medium", "current_status": "resolved", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "56d2d32f", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:44:13Z"}, {"author": "BIMGUARD AI", "comment": "Element no longer flagged in compliance run — marked resolved", "composite_score": 0.0, "event_id": "960f1e28", "event_type": "resolved", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:44:13Z", "global_id": "3ctB5z6nHCoQBWFJYnFhI5", "last_seen": "2026-04-09T18:44:13Z", "material": "concrete_reinforced_prefab", "system_type": "road wastewater system"}, "43E1B7D4-E7BA-4A2B-A99": {"current_band": "Medium", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4575, "event_id": "3f80e58a", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "43E1B7D4-E7BA-4A2B-A99", "last_seen": "2026-04-09T18:47:08Z", "material": "Carbon_steel_mild", "system_type": "Gas"}, "474B2DD3-A61D-414B-BED": {"current_band": "Medium", "current_status": "open", "element_type": "IfcPipeFitting", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4767, "event_id": "5703c4df", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "474B2DD3-A61D-414B-BED", "last_seen": "2026-04-09T18:47:08Z", "material": "Cast_iron", "system_type": "Drainage"}, "4B137C34-0617-4DD4-B6D": {"current_band": "Critical", "current_status": "open", "element_type": "IfcHeatExchanger", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.975, "event_id": "24383785", "event_type": "raised", "risk_band": "Critical", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "4B137C34-0617-4DD4-B6D", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_316_passive", "system_type": "Pool Heating"}, "4E003109-A258-44C2-A03": {"current_band": "Critical", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.9125, "event_id": "a35b8da2", "event_type": "raised", "risk_band": "Critical", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "4E003109-A258-44C2-A03", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_316_passive", "system_type": "Marine Services"}, "503AA852-EC9B-4FDB-A81": {"current_band": "High", "current_status": "open", "element_type": "IfcMember", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.73, "event_id": "54774c35", "event_type": "raised", "risk_band": "High", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "503AA852-EC9B-4FDB-A81", "last_seen": "2026-04-09T18:47:08Z", "material": "Carbon_steel_mild", "system_type": "Structure"}, "6D3CA398-AAE8-4E8C-807": {"current_band": "Medium", "current_status": "open", "element_type": "IfcDistributionElement", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4575, "event_id": "515997c3", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "6D3CA398-AAE8-4E8C-807", "last_seen": "2026-04-09T18:47:08Z", "material": "Aluminum_alloy_6063", "system_type": "Electrical"}, "6F89DF81-4F86-4790-B8C": {"current_band": "Medium", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4767, "event_id": "58d52631", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "6F89DF81-4F86-4790-B8C", "last_seen": "2026-04-09T18:47:08Z", "material": "Copper", "system_type": "CWS"}, "713F9559-E217-4C71-9E0": {"current_band": "Medium", "current_status": "open", "element_type": "IfcValve", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "33cfaa72", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "713F9559-E217-4C71-9E0", "last_seen": "2026-04-09T18:47:08Z", "material": "Bronze", "system_type": "CWS"}, "7323090D-60BF-4063-864": {"current_band": "Medium", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.31, "event_id": "612da8fc", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "7323090D-60BF-4063-864", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_316_passive", "system_type": "Chilled Water"}, "79A54E79-23C9-44E9-A72": {"current_band": "High", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.69, "event_id": "a710926a", "event_type": "raised", "risk_band": "High", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "79A54E79-23C9-44E9-A72", "last_seen": "2026-04-09T18:47:08Z", "material": "Carbon_steel_mild", "system_type": "Fire Protection"}, "86CB434D-5CDB-45DF-8A9": {"current_band": "Medium", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4825, "event_id": "31027400", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "86CB434D-5CDB-45DF-8A9", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_316_passive", "system_type": "Cooling"}, "8ACF81E9-373D-4AF0-BE2": {"current_band": "High", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.73, "event_id": "21b1df20", "event_type": "raised", "risk_band": "High", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "8ACF81E9-373D-4AF0-BE2", "last_seen": "2026-04-09T18:47:08Z", "material": "Copper", "system_type": "Cooling"}, "8D7BBAE1-449D-42CF-856": {"current_band": "Critical", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.8875, "event_id": "a2d9bfcb", "event_type": "raised", "risk_band": "Critical", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "8D7BBAE1-449D-42CF-856", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_316_passive", "system_type": "Pool Heating"}, "9E06B76F-1341-4CA9-9D1": {"current_band": "Medium", "current_status": "open", "element_type": "IfcDuctSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.4075, "event_id": "ede84843", "event_type": "raised", "risk_band": "Medium", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "9E06B76F-1341-4CA9-9D1", "last_seen": "2026-04-09T18:47:08Z", "material": "Galvanized_steel", "system_type": "Ventilation"}, "AF059F09-81B3-4FE1-A60": {"current_band": "Critical", "current_status": "open", "element_type": "IfcPipeFitting", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.8875, "event_id": "0a753887", "event_type": "raised", "risk_band": "Critical", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "AF059F09-81B3-4FE1-A60", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_316_passive", "system_type": "Pool Heating"}, "BAF273AA-4557-4598-A62": {"current_band": "High", "current_status": "open", "element_type": "IfcFastener", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.82, "event_id": "1845b399", "event_type": "raised", "risk_band": "High", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "BAF273AA-4557-4598-A62", "last_seen": "2026-04-09T18:47:08Z", "material": "Galvanized_steel", "system_type": "Drainage"}, "BBC71047-8F05-4B87-BBF": {"current_band": "High", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.69, "event_id": "589f4854", "event_type": "raised", "risk_band": "High", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "BBC71047-8F05-4B87-BBF", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_316_passive", "system_type": "Chilled Water"}, "D6AA94A4-2E25-4B80-B20": {"current_band": "High", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.69, "event_id": "b8670df9", "event_type": "raised", "risk_band": "High", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "D6AA94A4-2E25-4B80-B20", "last_seen": "2026-04-09T18:47:08Z", "material": "Copper", "system_type": "Hot Water Services"}, "D99B1FEF-C775-48C0-855": {"current_band": "Critical", "current_status": "open", "element_type": "IfcValve", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.8875, "event_id": "0badfec2", "event_type": "raised", "risk_band": "Critical", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "D99B1FEF-C775-48C0-855", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_304_passive", "system_type": "Pool Heating"}, "E4BDCAE2-C83F-4218-86C": {"current_band": "High", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.7375, "event_id": "c7f3f9bd", "event_type": "raised", "risk_band": "High", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "E4BDCAE2-C83F-4218-86C", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_304_passive", "system_type": "Domestic Hot Water"}, "EC67D720-4F7C-4EFD-9FC": {"current_band": "Critical", "current_status": "open", "element_type": "IfcPipeSegment", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.875, "event_id": "ec638b57", "event_type": "raised", "risk_band": "Critical", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "EC67D720-4F7C-4EFD-9FC", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_316_passive", "system_type": "External Services"}, "ED8966AE-2A1F-4C8B-9D9": {"current_band": "Critical", "current_status": "open", "element_type": "IfcFastener", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.96, "event_id": "c5369720", "event_type": "raised", "risk_band": "Critical", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "ED8966AE-2A1F-4C8B-9D9", "last_seen": "2026-04-09T18:47:08Z", "material": "Aluminum_alloy_6063", "system_type": "Facade"}, "F2E97F57-D65E-467E-98B": {"current_band": "Critical", "current_status": "open", "element_type": "IfcPipeFitting", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.8375, "event_id": "5d2581c7", "event_type": "raised", "risk_band": "Critical", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "F2E97F57-D65E-467E-98B", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_316_passive", "system_type": "Process"}, "FBD11737-24CB-4B36-90B": {"current_band": "Critical", "current_status": "open", "element_type": "IfcPlate", "events": [{"author": "BIMGUARD AI", "comment": "", "composite_score": 0.9625, "event_id": "6b8f9fcd", "event_type": "raised", "risk_band": "Critical", "timestamp": "2026-04-09T18:47:08Z"}], "first_seen": "2026-04-09T18:47:08Z", "global_id": "FBD11737-24CB-4B36-90B", "last_seen": "2026-04-09T18:47:08Z", "material": "SS_316_passive", "system_type": "Facade"}}', '{
  "1F4KLUGJf1aAa0YXxTvOR5": {
    "global_id": "1F4KLUGJf1aAa0YXxTvOR5",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "0afc84b5",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "34a5f915",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "0uGYOC9Nz33PfGM5uuVHhW": {
    "global_id": "0uGYOC9Nz33PfGM5uuVHhW",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "e3b50860",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "2753c4ad",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "259jK4QKD3OPEdfCl4GH_l": {
    "global_id": "259jK4QKD3OPEdfCl4GH_l",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "f2783c3c",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "ddd95d9b",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "0_AaoqH0fA_wWg2hQ6QoLY": {
    "global_id": "0_AaoqH0fA_wWg2hQ6QoLY",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "43f0fbf5",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "473a899e",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "0X_fsZ0Kj9a8olHcZQNbJM": {
    "global_id": "0X_fsZ0Kj9a8olHcZQNbJM",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "5c1d392d",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "f909ee92",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "3Awuj1sjH8ERw7F1J6oBZs": {
    "global_id": "3Awuj1sjH8ERw7F1J6oBZs",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "ad7ae7f8",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "c499b4f7",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "3D4ahkhjP7dujyPNisZ2F$": {
    "global_id": "3D4ahkhjP7dujyPNisZ2F$",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "7167a485",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "e2b7164f",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "0FQ6pMwzXBJucYaRTqfuw2": {
    "global_id": "0FQ6pMwzXBJucYaRTqfuw2",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "90a6965a",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "b74a1703",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "0yh8Z9_qzCIgcsXg7r4Ix6": {
    "global_id": "0yh8Z9_qzCIgcsXg7r4Ix6",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "cd62cde0",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "adbd98a7",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "1PI8m4Ts17Z8hvG889Pb1i": {
    "global_id": "1PI8m4Ts17Z8hvG889Pb1i",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "ef787585",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "19052b96",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "398dvTdH9FKwML6pMEemhK": {
    "global_id": "398dvTdH9FKwML6pMEemhK",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "da80e252",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "352443dc",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "0tZgj2n4j7neNsQ08k3WsT": {
    "global_id": "0tZgj2n4j7neNsQ08k3WsT",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "f1893d82",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "f901fe88",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "22Xr2mF15CbQCVR$W_$VLh": {
    "global_id": "22Xr2mF15CbQCVR$W_$VLh",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "c4894d11",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "9b2d8db7",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "1wwTT4jtX3C9e82mYC6YGT": {
    "global_id": "1wwTT4jtX3C9e82mYC6YGT",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "eb76e367",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "e8d0b37c",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "1GXiy3xWf0fOQdC$gO8JfW": {
    "global_id": "1GXiy3xWf0fOQdC$gO8JfW",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "7043a589",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "fe7ce517",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "0URFt4JXXD6OjZF8OrkR8N": {
    "global_id": "0URFt4JXXD6OjZF8OrkR8N",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "d5284ac1",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "eefd4754",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "1kpVA_DFf3PRJR$l8yqtLr": {
    "global_id": "1kpVA_DFf3PRJR$l8yqtLr",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "8f516cac",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "a697326e",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "3ctB5z6nHCoQBWFJYnFhI5": {
    "global_id": "3ctB5z6nHCoQBWFJYnFhI5",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "56d2d32f",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "960f1e28",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "11LWvWX7HAOghcDUC_Fsn5": {
    "global_id": "11LWvWX7HAOghcDUC_Fsn5",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "e4a65927",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "525dd7d3",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "2L8jfzclb09OjhbeQoBDvs": {
    "global_id": "2L8jfzclb09OjhbeQoBDvs",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "65357f21",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "e09f2679",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "0SESIjUgvFsOoEqvCaV5Br": {
    "global_id": "0SESIjUgvFsOoEqvCaV5Br",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "3f281fb5",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "f25ee45e",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "1FDcvNA_L4dfRDGP$UNpz1": {
    "global_id": "1FDcvNA_L4dfRDGP$UNpz1",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "8b28b69f",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "a1aa0795",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "0RPLlDbKvCJwFzsj8RPg4X": {
    "global_id": "0RPLlDbKvCJwFzsj8RPg4X",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "b9716788",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "391c2cb0",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "1PYbWto7LA0hTpEdNPg6Df": {
    "global_id": "1PYbWto7LA0hTpEdNPg6Df",
    "element_type": "IfcPipeSegment",
    "system_type": "road wastewater system",
    "material": "concrete_reinforced_prefab",
    "first_seen": "2026-04-09T18:44:13Z",
    "last_seen": "2026-04-09T18:44:13Z",
    "current_status": "resolved",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "3c84d835",
        "timestamp": "2026-04-09T18:44:13Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      },
      {
        "event_id": "632fdd66",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "resolved",
        "risk_band": "Medium",
        "composite_score": 0.0,
        "author": "BIMGUARD AI",
        "comment": "Element no longer flagged in compliance run \u2014 marked resolved"
      }
    ]
  },
  "BBC71047-8F05-4B87-BBF": {
    "global_id": "BBC71047-8F05-4B87-BBF",
    "element_type": "IfcPipeSegment",
    "system_type": "Chilled Water",
    "material": "SS_316_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "High",
    "events": [
      {
        "event_id": "589f4854",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "High",
        "composite_score": 0.69,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "D6AA94A4-2E25-4B80-B20": {
    "global_id": "D6AA94A4-2E25-4B80-B20",
    "element_type": "IfcPipeSegment",
    "system_type": "Hot Water Services",
    "material": "Copper",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "High",
    "events": [
      {
        "event_id": "b8670df9",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "High",
        "composite_score": 0.69,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "8D7BBAE1-449D-42CF-856": {
    "global_id": "8D7BBAE1-449D-42CF-856",
    "element_type": "IfcPipeSegment",
    "system_type": "Pool Heating",
    "material": "SS_316_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Critical",
    "events": [
      {
        "event_id": "a2d9bfcb",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Critical",
        "composite_score": 0.8875,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "AF059F09-81B3-4FE1-A60": {
    "global_id": "AF059F09-81B3-4FE1-A60",
    "element_type": "IfcPipeFitting",
    "system_type": "Pool Heating",
    "material": "SS_316_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Critical",
    "events": [
      {
        "event_id": "0a753887",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Critical",
        "composite_score": 0.8875,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "ED8966AE-2A1F-4C8B-9D9": {
    "global_id": "ED8966AE-2A1F-4C8B-9D9",
    "element_type": "IfcFastener",
    "system_type": "Facade",
    "material": "Aluminum_alloy_6063",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Critical",
    "events": [
      {
        "event_id": "c5369720",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Critical",
        "composite_score": 0.96,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "BAF273AA-4557-4598-A62": {
    "global_id": "BAF273AA-4557-4598-A62",
    "element_type": "IfcFastener",
    "system_type": "Drainage",
    "material": "Galvanized_steel",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "High",
    "events": [
      {
        "event_id": "1845b399",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "High",
        "composite_score": 0.82,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "503AA852-EC9B-4FDB-A81": {
    "global_id": "503AA852-EC9B-4FDB-A81",
    "element_type": "IfcMember",
    "system_type": "Structure",
    "material": "Carbon_steel_mild",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "High",
    "events": [
      {
        "event_id": "54774c35",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "High",
        "composite_score": 0.73,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "6F89DF81-4F86-4790-B8C": {
    "global_id": "6F89DF81-4F86-4790-B8C",
    "element_type": "IfcPipeSegment",
    "system_type": "CWS",
    "material": "Copper",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "58d52631",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4767,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "7323090D-60BF-4063-864": {
    "global_id": "7323090D-60BF-4063-864",
    "element_type": "IfcPipeSegment",
    "system_type": "Chilled Water",
    "material": "SS_316_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "612da8fc",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.31,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "EC67D720-4F7C-4EFD-9FC": {
    "global_id": "EC67D720-4F7C-4EFD-9FC",
    "element_type": "IfcPipeSegment",
    "system_type": "External Services",
    "material": "SS_316_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Critical",
    "events": [
      {
        "event_id": "ec638b57",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Critical",
        "composite_score": 0.875,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "4B137C34-0617-4DD4-B6D": {
    "global_id": "4B137C34-0617-4DD4-B6D",
    "element_type": "IfcHeatExchanger",
    "system_type": "Pool Heating",
    "material": "SS_316_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Critical",
    "events": [
      {
        "event_id": "24383785",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Critical",
        "composite_score": 0.975,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "474B2DD3-A61D-414B-BED": {
    "global_id": "474B2DD3-A61D-414B-BED",
    "element_type": "IfcPipeFitting",
    "system_type": "Drainage",
    "material": "Cast_iron",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "5703c4df",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4767,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "43E1B7D4-E7BA-4A2B-A99": {
    "global_id": "43E1B7D4-E7BA-4A2B-A99",
    "element_type": "IfcPipeSegment",
    "system_type": "Gas",
    "material": "Carbon_steel_mild",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "3f80e58a",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4575,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "4E003109-A258-44C2-A03": {
    "global_id": "4E003109-A258-44C2-A03",
    "element_type": "IfcPipeSegment",
    "system_type": "Marine Services",
    "material": "SS_316_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Critical",
    "events": [
      {
        "event_id": "a35b8da2",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Critical",
        "composite_score": 0.9125,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "6D3CA398-AAE8-4E8C-807": {
    "global_id": "6D3CA398-AAE8-4E8C-807",
    "element_type": "IfcDistributionElement",
    "system_type": "Electrical",
    "material": "Aluminum_alloy_6063",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "515997c3",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4575,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "9E06B76F-1341-4CA9-9D1": {
    "global_id": "9E06B76F-1341-4CA9-9D1",
    "element_type": "IfcDuctSegment",
    "system_type": "Ventilation",
    "material": "Galvanized_steel",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "ede84843",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "8ACF81E9-373D-4AF0-BE2": {
    "global_id": "8ACF81E9-373D-4AF0-BE2",
    "element_type": "IfcPipeSegment",
    "system_type": "Cooling",
    "material": "Copper",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "High",
    "events": [
      {
        "event_id": "21b1df20",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "High",
        "composite_score": 0.73,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "FBD11737-24CB-4B36-90B": {
    "global_id": "FBD11737-24CB-4B36-90B",
    "element_type": "IfcPlate",
    "system_type": "Facade",
    "material": "SS_316_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Critical",
    "events": [
      {
        "event_id": "6b8f9fcd",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Critical",
        "composite_score": 0.9625,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "79A54E79-23C9-44E9-A72": {
    "global_id": "79A54E79-23C9-44E9-A72",
    "element_type": "IfcPipeSegment",
    "system_type": "Fire Protection",
    "material": "Carbon_steel_mild",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "High",
    "events": [
      {
        "event_id": "a710926a",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "High",
        "composite_score": 0.69,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "E4BDCAE2-C83F-4218-86C": {
    "global_id": "E4BDCAE2-C83F-4218-86C",
    "element_type": "IfcPipeSegment",
    "system_type": "Domestic Hot Water",
    "material": "SS_304_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "High",
    "events": [
      {
        "event_id": "c7f3f9bd",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "High",
        "composite_score": 0.7375,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "D99B1FEF-C775-48C0-855": {
    "global_id": "D99B1FEF-C775-48C0-855",
    "element_type": "IfcValve",
    "system_type": "Pool Heating",
    "material": "SS_304_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Critical",
    "events": [
      {
        "event_id": "0badfec2",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Critical",
        "composite_score": 0.8875,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "F2E97F57-D65E-467E-98B": {
    "global_id": "F2E97F57-D65E-467E-98B",
    "element_type": "IfcPipeFitting",
    "system_type": "Process",
    "material": "SS_316_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Critical",
    "events": [
      {
        "event_id": "5d2581c7",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Critical",
        "composite_score": 0.8375,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "335CA3DF-171F-4E3F-BA4": {
    "global_id": "335CA3DF-171F-4E3F-BA4",
    "element_type": "IfcFastener",
    "system_type": "Weathering",
    "material": "Aluminum_alloy_6063",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "72f67851",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.58,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "713F9559-E217-4C71-9E0": {
    "global_id": "713F9559-E217-4C71-9E0",
    "element_type": "IfcValve",
    "system_type": "CWS",
    "material": "Bronze",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "33cfaa72",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4075,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  },
  "86CB434D-5CDB-45DF-8A9": {
    "global_id": "86CB434D-5CDB-45DF-8A9",
    "element_type": "IfcPipeSegment",
    "system_type": "Cooling",
    "material": "SS_316_passive",
    "first_seen": "2026-04-09T18:47:08Z",
    "last_seen": "2026-04-09T18:47:08Z",
    "current_status": "open",
    "current_band": "Medium",
    "events": [
      {
        "event_id": "31027400",
        "timestamp": "2026-04-09T18:47:08Z",
        "event_type": "raised",
        "risk_band": "Medium",
        "composite_score": 0.4825,
        "author": "BIMGUARD AI",
        "comment": ""
      }
    ]
  }
}', '09adb94acf0f5a0d108eda2c1a20ec9e5c8e4bc2947586619e3ff3643c1f807c', '', 1)
on conflict (asset_key) do update set
    source_path = excluded.source_path,
    format = excluded.format,
    content_json = excluded.content_json,
    content_text = excluded.content_text,
    content_sha256 = excluded.content_sha256,
    migrated_at = excluded.migrated_at,
    active = excluded.active;

commit;