import type {
  BoundingBox,
  CDEState,
  IsoGovernanceFieldsRequired,
} from "./common";

export const DOCUMENT_TYPES = [
  "Specification",
  "Code",
  "Manual",
  "Standard",
  "Drawing",
  "Schedule",
  "O&M Manual",
  "Warranty",
  "Assessment",
  "Report",
  "RFI Log",
  "Other",
] as const;

export type DocumentType = (typeof DOCUMENT_TYPES)[number];

export interface DocumentItem extends IsoGovernanceFieldsRequired {
  id: number;
  filename: string;
  doc_type?: string | null;
  file_path?: string | null;
  upload_date?: string | null;
  text_preview?: string | null;
  char_count: number;
  has_doclang?: boolean;
  doclang_storage_path?: string | null;
  doclang_archive_path?: string | null;
  doclang_xml?: string | null;
  project_code?: string;
}

export interface DocumentDetail extends IsoGovernanceFieldsRequired {
  id: number;
  filename: string;
  doc_type?: string | null;
  file_path?: string | null;
  upload_date?: string | null;
  text: string;
  char_count: number;
  doclang_storage_path?: string | null;
  doclang_archive_path?: string | null;
  doclang_xml?: string | null;
  project_code?: string;
}

export interface DocumentSection {
  id?: string | null;
  section_number?: string | null;
  section_name?: string | null;
  text: string;
  char_count: number;
  page_number?: number | null;
  printed_page_number?: string | null;
  node_type?: string;
  bbox?: BoundingBox | null;
  summary?: string | null;
  end_page_number?: number | null;
  key_topics?: string[];
  citations?: string[];
  target_ifc_classes?: string[];
}

export interface DocumentSectionsResponse {
  document_id: number;
  sections: DocumentSection[];
}

export interface SectionTreeNode {
  id: string;
  section_number?: string | null;
  section_name?: string | null;
  char_count: number;
  page_number?: number | null;
  printed_page_number?: string | null;
  node_type?: string;
  bbox?: BoundingBox | null;
  summary?: string | null;
  end_page_number?: number | null;
  key_topics?: string[];
  citations?: string[];
  target_ifc_classes?: string[];
  children: SectionTreeNode[];
}

export interface DocumentSectionTreeResponse {
  document_id: number;
  tree: SectionTreeNode[];
  sections: DocumentSection[];
  enhanced: boolean;
}

export interface SectionGraphResponse {
  document_id: number;
  section_id?: string | null;
  records: Record<string, unknown>[];
  available: boolean;
}

export type DocumentElementKind = "heading" | "paragraph" | "list" | "table" | "picture";

/** One rendered block's bbox, keyed by the id injected into the document's DocLang XML at extraction time. */
export interface DocumentElementBbox {
  element_id: string;
  kind: DocumentElementKind;
  page_number?: number | null;
  bbox?: BoundingBox | null;
  order: number;
}

export interface DocumentElementBboxesResponse {
  document_id: number;
  elements: DocumentElementBbox[];
}

export type RuleSourceMatchStatus = "exact" | "unmapped" | "orphaned";

/** Lightweight rule shape for the rule-source map view. */
export interface RuleSourceSummary {
  id: number;
  rule_id?: string | null;
  description?: string | null;
  severity?: string | null;
  category?: string | null;
  source_page_number?: number | null;
  source_bbox?: BoundingBox | null;
  source_element_id?: string | null;
  match_status: RuleSourceMatchStatus;
}

/** One document element annotated with the rule(s) extracted from it. */
export interface DocumentElementWithRules extends DocumentElementBbox {
  rules: RuleSourceSummary[];
}

/**
 * Every rule extracted from a document, mapped against its exact source element.
 * `unmapped_rules` holds rules with no `source_element_id` at all (extracted
 * before that linkage existed) -- only an approximate page/bbox location.
 * `orphaned_rules` holds rules whose `source_element_id` matches no *current*
 * element (the source document was likely re-parsed) -- these need re-linking.
 */
export interface RuleSourceMapResponse {
  document_id: number;
  elements: DocumentElementWithRules[];
  unmapped_rules: RuleSourceSummary[];
  orphaned_rules: RuleSourceSummary[];
}

/** One source document's contribution to a ruleset's source map. */
export interface RulesetDocumentSourceMap {
  document_id: number;
  filename: string;
  elements: DocumentElementWithRules[];
  unmapped_rules: RuleSourceSummary[];
  orphaned_rules: RuleSourceSummary[];
}

/** Every rule in a ruleset, mapped against its exact source element, across every source document. */
export interface RulesetSourceMapResponse {
  ruleset_id: string;
  documents: RulesetDocumentSourceMap[];
}

export interface DocumentUpdatePayload {
  filename?: string;
  doc_type?: string | null;
  project_code?: string;
  originator?: string;
  suitability_code?: string;
  revision_code?: string;
  cde_state?: CDEState;
  /** Lead Appointed Party approver name, required to authorize SHARED -> PUBLISHED. */
  approved_by?: string;
}

export interface GoogleDriveImportPayload {
  urls: string[];
  doc_type?: string;
  project_code?: string;
  originator?: string;
  suitability_code?: string;
  revision_code?: string;
  parser?: "auto";
  engine_instance?: string;
}

export interface GoogleDriveImportResult {
  url: string;
  ok: boolean;
  document?: DocumentDetail | null;
  error?: string | null;
}

export interface GoogleDriveImportResponse {
  results: GoogleDriveImportResult[];
}
