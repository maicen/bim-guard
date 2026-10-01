/**
 * Upload size ceiling for IFC models.
 *
 * Mirrors the Supabase Storage bucket's file_size_limit (see
 * supabase/config.toml and app/modules/pipeline_io/file_upload.py's
 * MAX_UPLOAD_BYTES) — that backend is the real enforcement point. A file
 * larger than this is rejected here so the user gets a clear message
 * instead of a raw connection-drop error surfacing after the upload has
 * already started.
 */
export const MAX_IFC_UPLOAD_BYTES = 50 * 1024 * 1024;

/** Mirrors MAX_DOCUMENT_UPLOAD_BYTES in app/document_upload_validation.py */
export const MAX_DOCUMENT_UPLOAD_BYTES = 100 * 1024 * 1024;

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

/** Split a batch of picked files into ones under the limit and ones over it. */
export function partitionByUploadSize(files: File[], maxBytes: number = MAX_IFC_UPLOAD_BYTES): { accepted: File[]; oversized: File[] } {
  const accepted: File[] = [];
  const oversized: File[] = [];
  for (const file of files) {
    (file.size > maxBytes ? oversized : accepted).push(file);
  }
  return { accepted, oversized };
}

/** Human-readable rejection notice for one or more oversized files. */
export function describeOversizedFiles(oversized: File[], maxBytes: number = MAX_IFC_UPLOAD_BYTES, advice: string = ""): string {
  const limit = formatFileSize(maxBytes);
  const adviceSuffix = advice ? ` ${advice}` : "";
  if (oversized.length === 1) {
    return `${oversized[0].name} is ${formatFileSize(oversized[0].size)}, which is over the ${limit} upload limit.${adviceSuffix}`;
  }
  return `${oversized.length} files are over the ${limit} upload limit: ${oversized.map((f) => f.name).join(", ")}.${adviceSuffix}`;
}
