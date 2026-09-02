// Building-element categories for Ontario Building Code Part 9 architectural
// compliance, mirroring the domain breakdown shown on the ARCH Analysis
// results page (ArchAnalyzeView.svelte's DOMAIN_CARDS). Kept as a separate,
// small reference here rather than imported from that view, so this page
// never risks destabilizing the (already complex) results view.

export interface IfcPropertySuggestion {
  /** property_name to store on the rule */
  name: string;
  /** property_set to store on the rule ("" = direct IFC attribute, not inside a Pset) */
  propertySet: string;
  /** short human label shown in the picker, e.g. "Overall Height (m)" */
  label: string;
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

const DOOR_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "OverallHeight", propertySet: "", label: "Overall Height (direct attribute)" },
  { name: "OverallWidth", propertySet: "", label: "Overall Width (direct attribute)" },
  { name: "FireRating", propertySet: "Pset_DoorCommon", label: "Fire Rating" },
  { name: "IsExternal", propertySet: "Pset_DoorCommon", label: "Is External" },
  { name: "HandicapAccessible", propertySet: "Pset_DoorCommon", label: "Handicap Accessible" },
  { name: "ThermalTransmittance", propertySet: "Pset_DoorCommon", label: "Thermal Transmittance (U-value)" },
  { name: "AcousticRating", propertySet: "Pset_DoorCommon", label: "Acoustic Rating" },
];

const WINDOW_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "OverallHeight", propertySet: "", label: "Overall Height (direct attribute)" },
  { name: "OverallWidth", propertySet: "", label: "Overall Width (direct attribute)" },
  { name: "FireRating", propertySet: "Pset_WindowCommon", label: "Fire Rating" },
  { name: "IsExternal", propertySet: "Pset_WindowCommon", label: "Is External" },
  { name: "ThermalTransmittance", propertySet: "Pset_WindowCommon", label: "Thermal Transmittance (U-value)" },
  { name: "GlazingAreaFraction", propertySet: "Pset_WindowCommon", label: "Glazing Area Fraction" },
];

const STAIR_FLIGHT_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "NumberOfRisers", propertySet: "Pset_StairFlightCommon", label: "Number of Risers" },
  { name: "NumberOfTreads", propertySet: "Pset_StairFlightCommon", label: "Number of Treads" },
  { name: "RiserHeight", propertySet: "Pset_StairFlightCommon", label: "Riser Height" },
  { name: "TreadLength", propertySet: "Pset_StairFlightCommon", label: "Tread Length (run)" },
  { name: "NosingLength", propertySet: "Pset_StairFlightCommon", label: "Nosing Length" },
  { name: "WalkingLineOffset", propertySet: "Pset_StairFlightCommon", label: "Walking Line Offset" },
];

const RAILING_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "Height", propertySet: "Pset_RailingCommon", label: "Height (guard / handrail)" },
  { name: "IsExternal", propertySet: "Pset_RailingCommon", label: "Is External" },
];

const RAMP_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "HandicapAccessible", propertySet: "Pset_RampCommon", label: "Handicap Accessible" },
  { name: "RequiredSlope", propertySet: "Pset_RampCommon", label: "Required Slope" },
  { name: "RequiredHeadroom", propertySet: "Pset_RampCommon", label: "Required Headroom" },
  { name: "HasNonSkidSurface", propertySet: "Pset_RampCommon", label: "Has Non-Skid Surface" },
];

const RAMP_FLIGHT_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "Width", propertySet: "", label: "Width (direct attribute, where present)" },
  { name: "Slope", propertySet: "Pset_RampFlightCommon", label: "Slope" },
];

const SANITARY_TERMINAL_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "IsExternal", propertySet: "Pset_SanitaryTerminalTypeCommon", label: "Is External" },
  { name: "PredefinedType", propertySet: "", label: "Predefined Type (fixture kind)" },
];

const ALARM_PROPERTIES: IfcPropertySuggestion[] = [
  { name: "PredefinedType", propertySet: "", label: "Predefined Type (alarm kind)" },
  { name: "Reference", propertySet: "", label: "Reference" },
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
    targets: [{ ifcClass: "IfcSanitaryTerminal", label: "Sanitary Terminals", properties: SANITARY_TERMINAL_PROPERTIES }],
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
