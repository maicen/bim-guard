/** One entry of the code library. Mirrors NamingCodeContract. */
export interface NamingCode {
  code: string;
  label: string;
}

/** One naming convention: a format string over the token vocabulary. */
export interface NamingConvention {
  id: string;
  name: string;
  format: string;
  separator: string;
  description: string;
  /** True for the five built-ins, which cannot be edited or deleted. */
  preset: boolean;
  /** False for conventions meant for clash-test names rather than for a CDE. */
  iso_compliant: boolean;
}

/** One token a convention format may contain. */
export interface NamingToken {
  token: string;
  label: string;
  /** Where the value comes from: 'config', 'library' or 'runtime'. */
  source: string;
}

/** One row of the CDE status table (ISO 19650-2 Table 1). */
export interface CdeStatus {
  code: string;
  label: string;
  colour: string;
  /** False for rows shown for reference but not offered as a suitability. */
  selectable: boolean;
}

/** The static half of the naming feature. Mirrors NamingCatalogResponseContract. */
export interface NamingCatalog {
  conventions: NamingConvention[];
  tokens: NamingToken[];
  codes: Record<string, NamingCode[]>;
  cde_statuses: CdeStatus[];
  date_formats: string[];
  separators: string[];
  default_convention: string;
}

/** A project's naming configuration. Mirrors NamingConfigContract. */
export interface NamingConfig {
  project_id: number;
  /** False when nothing has been saved and these are the defaults. */
  is_configured: boolean;
  project_code: string;
  originator_code: string;
  type_code: string;
  suitability: string;
  revision: string;
  separator: string;
  date_format: string;
  class_a: string;
  class_b: string;
  active_convention: string;
  level_codes: NamingCode[];
  type_codes: NamingCode[];
  discipline_codes: NamingCode[];
  volume_codes: NamingCode[];
  custom_conventions: NamingConvention[];
  updated_at?: string | null;
}

/** Fields to write. Mirrors NamingConfigUpdateContract; every field optional. */
export type NamingConfigPayload = Partial<
  Omit<NamingConfig, "project_id" | "is_configured" | "updated_at">
>;

/** A rendered sample name. Mirrors NamingPreviewResponseContract. */
export interface NamingPreview {
  name: string;
  convention_id: string;
  /** The format as rendered, with the project's separator substituted. */
  applied_format: string;
  /** Tokens left literal because nothing supplied a value for them. */
  unresolved_tokens: string[];
}
