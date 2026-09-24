import type { ApiError } from "../api";

/** One failure captured for a copiable technical-details/issue log. */
export interface ErrorLogEntry {
  /** Which item this failure belongs to, e.g. a draft/project/document id or label. */
  subject?: string;
  status?: number;
  message: string;
  url?: string;
  timestamp?: string;
}

/** Normalize a caught `ApiError` (or anything error-shaped) into a log entry. */
export function toErrorLogEntry(err: unknown, subject?: string): ErrorLogEntry {
  const apiErr = err as ApiError | undefined;
  return {
    subject,
    status: apiErr?.status,
    message: apiErr?.message || String(err),
    url: apiErr?.url,
    timestamp: apiErr?.timestamp || new Date().toISOString(),
  };
}

/** Render a plain-text, copy-paste-friendly issue log for one or more failures. */
export function buildIssueLog(
  title: string,
  context: Record<string, string | number | undefined>,
  entries: ErrorLogEntry[],
): string {
  const lines = [`BIM Guard — ${title}`, `Generated: ${new Date().toISOString()}`];
  for (const [key, value] of Object.entries(context)) {
    if (value !== undefined && value !== "") lines.push(`${key}: ${value}`);
  }
  lines.push(`Failures: ${entries.length}`, "");
  entries.forEach((e, i) => {
    lines.push(`[${i + 1}]${e.subject ? ` ${e.subject}` : ""} — HTTP ${e.status ?? "?"}`);
    if (e.url) lines.push(`    url: ${e.url}`);
    if (e.timestamp) lines.push(`    at: ${e.timestamp}`);
    lines.push(`    ${e.message}`);
  });
  return lines.join("\n");
}

/** Copy `text` to the clipboard, swallowing denial -- the caller shows its own fallback UI. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
