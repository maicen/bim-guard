// Building-element categories for Ontario Building Code Part 9 architectural
// compliance, mirroring the domain breakdown shown on the ARCH Analysis
// results page (ArchAnalyzeView.svelte's DOMAIN_CARDS). Kept as a separate,
// small reference here rather than imported from that view, so this page
// never risks destabilizing the (already complex) results view.
//
// The property suggestion lists below are NOT guessed from the IFC schema —
// they're mined directly from every property_name/property_set combination
// already in use across the live Arch rule catalog (grouped by
// target_ifc_class), so what's offered here is exactly what BIM-Guard's
// existing rules actually check today. Re-derive by querying
// GET /api/rules?category=Arch and grouping by (target_ifc_class,
// property_name) if the catalog changes meaningfully. IfcRampFlight has no
// rules yet, so its two entries remain a best-guess placeholder.
//
// `unit: "mm"` marks a property as dimensional (length-valued). The
// compliance engine (module2_ifc_read._resolve_element_property, Pass 8)
// always scales the value it reads off the real IFC element to millimetres
// before comparing — regardless of whether the source model itself is
// authored in metres, millimetres, or feet — so a rule's stored check_value
// must already be in millimetres to compare correctly. RuleForm uses this
// flag to offer a unit picker (mm/cm/m/in/ft) and converts whatever the
// author types into millimetres before saving, so the threshold always
// matches what the engine actually compares against.
export interface IfcPropertySuggestion {
  /** property_name to store on the rule */
  name: string;
  /** property_set to store on the rule ("" = direct IFC attribute, not inside a Pset) */
  propertySet: string;
  /** short human label shown in the picker, e.g. "Overall Height" */
  label: string;
  /** "mm" if this is a dimensional property — see file header for why */
  unit?: "mm";
}

export interface ArchDomainTarget {
  ifcClass: string;
  label: string;
  properties: IfcPropertySuggestion[];
}

export interface ArchDomain {
  key: string;
  label: string;
  /** IFC classes a rule can target within this domain; empty when the domain is engine-computed, not rule-driven */
  targets: ArchDomainTarget[];
  /** true when this domain's checks come from dedicated engine logic (egress/plumbing/garage), not editable property_check rules */
  computed?: boolean;
}

const WINDOW_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "OverallHeight", propertySet: "", label: "Overall Height", unit: "mm" },
  { name: "OverallWidth", propertySet: "", label: "Overall Width", unit: "mm" },
  { name: "Area", propertySet: "", label: "Area" },
  { name: "ClearOpeningArea", propertySet: "", label: "Clear Opening Area" },
  { name: "FireRating", propertySet: "", label: "Fire Rating" },
  { name: "FireExit", propertySet: "", label: "Fire Exit" },
  { name: "SmokeStop", propertySet: "", label: "Smoke Stop" },
  { name: "SelfClosing", propertySet: "", label: "Self Closing" },
  { name: "SecurityRating", propertySet: "", label: "Security Rating" },
  { name: "HandicapAccessible", propertySet: "", label: "Handicap Accessible" },
  { name: "IsExternal", propertySet: "", label: "Is External" },
  { name: "Infiltration", propertySet: "", label: "Infiltration" },
  { name: "AcousticRating", propertySet: "", label: "Acoustic Rating" },
  { name: "ThermalTransmittance", propertySet: "", label: "Thermal Transmittance (U-value)" },
];

const DOOR_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "OverallWidth", propertySet: "", label: "Overall Width", unit: "mm" },
  { name: "Width", propertySet: "", label: "Width", unit: "mm" },
  { name: "Height", propertySet: "Pset_DoorCommon", label: "Height", unit: "mm" },
  { name: "ClearWidth", propertySet: "", label: "Clear Width", unit: "mm" },
  {
    name: "ThresholdHeight",
    propertySet: "Pset_DoorCommon",
    label: "Threshold Height",
    unit: "mm",
  },
  { name: "Clearance", propertySet: "Pset_DoorCommon", label: "Clearance", unit: "mm" },
  { name: "ConnectedSpaceCount", propertySet: "", label: "Connected Space Count" },
  { name: "SpaceConnection", propertySet: "Pset_DoorCommon", label: "Space Connection" },
  { name: "Storey", propertySet: "Pset_DoorCommon", label: "Storey" },
  { name: "FireRating", propertySet: "Pset_DoorCommon", label: "Fire Rating" },
  {
    name: "FireRatedGlazingArea",
    propertySet: "Pset_DoorCommon",
    label: "Fire-Rated Glazing Area",
  },
  { name: "SmokeStop", propertySet: "Pset_DoorCommon", label: "Smoke Stop" },
  { name: "SelfClosing", propertySet: "Pset_DoorCommon", label: "Self Closing" },
  { name: "SecurityRating", propertySet: "Pset_DoorCommon", label: "Security Rating" },
  { name: "AcousticRating", propertySet: "Pset_DoorCommon", label: "Acoustic Rating" },
  {
    name: "ThermalTransmittance",
    propertySet: "Pset_DoorCommon",
    label: "Thermal Transmittance (U-value)",
  },
  { name: "HandicapAccessible", propertySet: "Pset_DoorCommon", label: "Handicap Accessible" },
  { name: "IsExternal", propertySet: "Pset_DoorCommon", label: "Is External" },
  { name: "OpeningDirection", propertySet: "Pset_DoorCommon", label: "Opening Direction" },
  { name: "OperationType", propertySet: "Pset_DoorCommon", label: "Operation Type" },
  { name: "OpeningForce", propertySet: "Pset_DoorCommon", label: "Opening Force" },
  { name: "HardwareType", propertySet: "Pset_DoorCommon", label: "Hardware Type" },
  { name: "Material", propertySet: "Pset_DoorCommon", label: "Material" },
  { name: "Manufacturer", propertySet: "Pset_DoorCommon", label: "Manufacturer" },
  { name: "ModelNumber", propertySet: "Pset_DoorCommon", label: "Model Number" },
];

const STAIR_FLIGHT_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "Width", propertySet: "Pset_StairFlightCommon", label: "Width", unit: "mm" },
  { name: "Height", propertySet: "Pset_StairFlightCommon", label: "Height", unit: "mm" },
  { name: "FlightHeight", propertySet: "", label: "Flight Height", unit: "mm" },
  { name: "NumberOfRiser", propertySet: "Pset_StairFlightCommon", label: "Number of Risers" },
  { name: "RiserHeight", propertySet: "", label: "Riser Height", unit: "mm" },
  { name: "NumberOfTreads", propertySet: "Pset_StairFlightCommon", label: "Number of Treads" },
  { name: "TreadDepth", propertySet: "Pset_StairFlightCommon", label: "Tread Depth", unit: "mm" },
  { name: "TreadLength", propertySet: "", label: "Tread Length (run)", unit: "mm" },
  { name: "HeadroomClearance", propertySet: "", label: "Headroom Clearance", unit: "mm" },
  { name: "RequiredHeadroom", propertySet: "", label: "Required Headroom", unit: "mm" },
  { name: "IndividualWinderAngle", propertySet: "", label: "Individual Winder Angle" },
  { name: "WinderSetSeparation", propertySet: "", label: "Winder Set Separation", unit: "mm" },
  { name: "WinderTurnAngle", propertySet: "", label: "Winder Turn Angle" },
  { name: "Name", propertySet: "", label: "Name" },
];

const RAILING_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "Height", propertySet: "", label: "Height (guard / handrail)", unit: "mm" },
  { name: "HandrailHeight", propertySet: "", label: "Handrail Height", unit: "mm" },
];

const RAMP_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "Width", propertySet: "", label: "Width", unit: "mm" },
  { name: "RequiredSlope", propertySet: "", label: "Required Slope" },
  { name: "HasNonSkidSurface", propertySet: "Pset_RampCommon", label: "Has Non-Skid Surface" },
];

// No rules target IfcRampFlight yet in the live catalog — these two remain
// a best-guess placeholder rather than data-derived like the rest above.
const RAMP_FLIGHT_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "Width", propertySet: "", label: "Width (direct attribute, where present)", unit: "mm" },
  { name: "Slope", propertySet: "Pset_RampFlightCommon", label: "Slope" },
];

const SANITARY_TERMINAL_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "PredefinedType", propertySet: "", label: "Predefined Type (fixture kind)" },
];

const ALARM_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "PredefinedType", propertySet: "", label: "Predefined Type (alarm kind)" },
];

export const ARCH_DOMAINS: ArchDomain[] = [
  {
    key: "windows",
    label: "Windows & Glazing",
    targets: [{ ifcClass: "IfcWindow", label: "Windows", properties: WINDOW_PROPERTIES }],
  },
  {
    key: "doors",
    label: "Doors",
    targets: [{ ifcClass: "IfcDoor", label: "Doors", properties: DOOR_PROPERTIES }],
  },
  {
    key: "stairs",
    label: "Stairs, Guards & Handrails",
    targets: [
      { ifcClass: "IfcStairFlight", label: "Stair Flights", properties: STAIR_FLIGHT_PROPERTIES },
      { ifcClass: "IfcRailing", label: "Guards / Handrails", properties: RAILING_PROPERTIES },
    ],
  },
  {
    key: "ramps",
    label: "Ramps",
    targets: [
      { ifcClass: "IfcRamp", label: "Ramps", properties: RAMP_PROPERTIES },
      { ifcClass: "IfcRampFlight", label: "Ramp Flights", properties: RAMP_FLIGHT_PROPERTIES },
    ],
  },
  {
    key: "egress",
    label: "Means of Egress",
    targets: [],
    computed: true,
  },
  {
    key: "washrooms",
    label: "Washrooms & Accessibility",
    targets: [
      {
        ifcClass: "IfcSanitaryTerminal",
        label: "Sanitary Terminals",
        properties: SANITARY_TERMINAL_PROPERTIES,
      },
    ],
  },
  {
    key: "plumbing",
    label: "Plumbing Fixture Counts",
    targets: [],
    computed: true,
  },
  {
    key: "fire",
    label: "Fire Protection (House-Level)",
    targets: [{ ifcClass: "IfcAlarm", label: "Alarms", properties: ALARM_PROPERTIES }],
  },
  {
    key: "garage",
    label: "Garage / Carport",
    targets: [],
    computed: true,
  },
];
