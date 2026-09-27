export interface BSDDPropertyItem {
  uri: string;
  name: string;
  property_set?: string | null;
  data_type?: string | null;
  units?: string | null;
  allowed_values: string[];
  /** What the property actually means -- bSDD's `definition`, present on nearly every property. */
  definition?: string | null;
  /** Supplementary note from bSDD, only set when distinct from `definition`. */
  description?: string | null;
}

export interface BSDDClassItem {
  uri: string;
  code: string;
  name: string;
  dictionary_uri: string;
  /** bSDD classType, e.g. "Class" (an IFC entity) or "GroupOfProperties" (a Pset_/Qto_ definition). */
  class_type: string;
  parent_class_code?: string | null;
  child_class_codes?: string[];
  related_ifc_entities: string[];
  properties: BSDDPropertyItem[];
  /** What the class actually means -- bSDD's `definition`; classes essentially never carry `description`. */
  definition?: string | null;
  /** Supplementary note from bSDD, only set when distinct from `definition`. */
  description?: string | null;
}

export interface BSDDDictionaryItem {
  uri: string;
  code: string;
  name: string;
  version: string;
  organization_code_owner: string;
  language_iso_code: string;
  classes_count: number;
  is_curated?: boolean;
  domain?: string | null;
}

/** A non-standard local name to resolve against bSDD via LLM disambiguation. */
export interface SemanticMatchRequest {
  query: string;
  kind: "class" | "property";
  target_ifc_class?: string | null;
  model?: string | null;
  organization_id?: number | null;
}

export interface SemanticMatchResponse {
  matched: boolean;
  matched_uri?: string | null;
  matched_code?: string | null;
  confidence: number;
  reasoning?: string | null;
}

export interface BSDDValidationViolation {
  element_guid: string;
  element_type: string;
  field_checked: string;
  expected_constraint: string;
  actual_value?: any;
  severity: "error" | "warning" | "info" | string;
  message: string;
  dictionary_uri?: string | null;
}

export interface BSDDValidationResult {
  passed: boolean;
  dictionary_uri: string;
  total_elements_checked: number;
  total_properties_checked: number;
  passed_count: number;
  violations_count: number;
  compliance_score_pct: number;
  violations: BSDDValidationViolation[];
}

export interface BSDDClassSearchResponse {
  query: string;
  total: number;
  classes: BSDDClassItem[];
}

export interface BSDDPropertySearchResponse {
  query: string;
  total: number;
  properties: BSDDPropertyItem[];
}

/** Lightweight row for browsing the local bSDD ontology cache (the wiki's class tree). */
export interface BSDDOntologyClassSummary {
  uri: string;
  code: string;
  name: string;
  /** bSDD classType, e.g. "Class" (an IFC entity) or "GroupOfProperties" (a Pset_/Qto_ definition). */
  class_type: string;
  parent_class_uri: string | null;
  dictionary_uri: string | null;
}

/** Full property detail from the local ontology, plus which classes carry it. */
export interface BSDDOntologyPropertyDetail {
  uri: string;
  code: string;
  name: string;
  data_type: string | null;
  units: string[];
  definition: string | null;
  description: string | null;
  used_by_classes: { uri: string; code: string; name: string }[];
}
