/**
 * Persistent, per-browser cache backed by localStorage -- survives page
 * reloads and new sessions, unlike the in-memory SWR stores in cache.ts.
 * For data that barely changes (bSDD class/property definitions) so a
 * reviewer's own machine never re-fetches the same lookup twice within the
 * TTL, even across visits.
 *
 * Wrapped in try/catch throughout: a private window, disabled storage, or a
 * full quota must degrade to "no cache" rather than break the caller.
 */

const CACHE_VERSION = "v1";
const PREFIX = `bimguard:cache:${CACHE_VERSION}:`;

interface CacheEnvelope<T> {
  value: T;
  storedAt: number;
}

export function getPersistentCache<T>(key: string, ttlMs: number): T | null {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CacheEnvelope<T>;
    if (Date.now() - parsed.storedAt > ttlMs) {
      localStorage.removeItem(PREFIX + key);
      return null;
    }
    return parsed.value;
  } catch {
    return null;
  }
}

export function setPersistentCache<T>(key: string, value: T): void {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify({ value, storedAt: Date.now() } satisfies CacheEnvelope<T>));
  } catch {
    // Storage full, disabled, or unavailable (private mode) -- caching is
    // an optimization, not a requirement, so just skip it.
  }
}
