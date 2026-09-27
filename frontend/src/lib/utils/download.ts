/**
 * Reusable file download utilities for browser and API downloads.
 */

import { apiFetch } from "../api";
import { withAuthToken } from "../authToken";

/**
 * Triggers a browser download from an existing in-memory Blob.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Triggers a browser download from raw text content (JSON, XML, CSV, etc.).
 */
export function downloadText(
  content: string,
  filename: string,
  mimeType: string = "text/plain;charset=utf-8"
): void {
  const blob = new Blob([content], { type: mimeType });
  downloadBlob(blob, filename);
}

/**
 * Parses the suggested filename from a Response's Content-Disposition header.
 */
function parseFilenameFromHeaders(res: Response, fallback: string): string {
  const disposition = res.headers.get("Content-Disposition");
  if (!disposition) return fallback;

  // Check RFC 5987 filename* first: filename*=UTF-8''encoded_name.ext
  const matchRfc = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (matchRfc && matchRfc[1]) {
    try {
      return decodeURIComponent(matchRfc[1]);
    } catch {
      return matchRfc[1];
    }
  }

  // Check standard filename="name.ext" or filename=name.ext
  const matchStandard = disposition.match(/filename="?([^";]+)"?/i);
  if (matchStandard && matchStandard[1]) {
    return matchStandard[1].trim();
  }

  return fallback;
}

/**
 * Downloads a file from an authenticated API endpoint.
 *
 * Performs an authenticated `apiFetch` (which carries the bearer token in
 * Authorization headers), parses any filename emitted in Content-Disposition,
 * and converts the stream to a Blob download. This avoids opening unauthenticated
 * blank browser tabs or failing with 401 "Missing bearer token".
 */
export async function downloadAuthenticated(
  endpointUrl: string,
  fallbackFilename: string = "download"
): Promise<void> {
  const res = await apiFetch(endpointUrl);
  if (!res.ok) {
    let errorDetail = `Download failed with HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson && errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      const errText = await res.text().catch(() => "");
      if (errText) errorDetail = errText;
    }
    throw new Error(errorDetail);
  }

  const filename = parseFilenameFromHeaders(res, fallbackFilename);
  const blob = await res.blob();
  downloadBlob(blob, filename);
}

/**
 * Downloads a file via direct browser navigation with ?token= query parameter.
 * Useful when streaming massive gigabyte files that shouldn't be buffered in browser memory.
 */
export function downloadDirectWithToken(url: string, filename?: string): void {
  const authenticatedUrl = withAuthToken(url);
  const link = document.createElement("a");
  link.href = authenticatedUrl;
  if (filename) link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
