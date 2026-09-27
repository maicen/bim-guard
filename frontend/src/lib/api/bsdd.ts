import type {
  BSDDClassItem,
  BSDDClassSearchResponse,
  BSDDDictionaryItem,
  BSDDOntologyClassSummary,
  BSDDOntologyPropertyDetail,
  BSDDPropertySearchResponse,
  SemanticMatchRequest,
  SemanticMatchResponse,
} from "../types";
import { getPersistentCache, setPersistentCache } from "../localCache";
import { API_BASE, apiFetch, handleResponse } from "./client";

/**
 * buildingSMART Data Dictionary (bSDD) client.
 *
 * Backs project-settings classification-standard selection and the rule
 * builder's element/property autocomplete. Search results are inherently
 * transient (typed by the user, one query at a time), so unlike the other
 * clients in this file this one does no caching -- each call is a plain
 * round trip.
 */
// bSDD class/property definitions are reference data that barely ever
// changes -- worth caching on the user's own machine (not just the backend's
// local ontology) so a repeat hover or search never re-hits the network at
// all. 30 days: long enough that a normal session never expires it, short
// enough that a bSDD revision eventually reaches the client anyway.
const BSDD_CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000;

// In-memory only (see listOntologyClasses) -- cleared on reload, never in localStorage.
let ontologyClassesMemoryCache: BSDDOntologyClassSummary[] | null = null;

export const bsddApi = {
  /** Classification standards a project can be coded against (Uniclass, OmniClass, IFC, ...). */
  async listDictionaries(curatedOnly: boolean = false): Promise<BSDDDictionaryItem[]> {
    const query = curatedOnly ? "?curated_only=true" : "";
    const res = await apiFetch(`${API_BASE}/bsdd/dictionaries${query}`);
    return handleResponse<BSDDDictionaryItem[]>(res);
  },

  /** Search bSDD classes (element/classification codes) matching free text. */
  async searchClasses(query: string, dictionaryUri?: string): Promise<BSDDClassSearchResponse> {
    const cacheKey = `bsdd:classes:search:${query}:${dictionaryUri || ""}`;
    const cached = getPersistentCache<BSDDClassSearchResponse>(cacheKey, BSDD_CACHE_TTL_MS);
    if (cached) return cached;
    const params = new URLSearchParams({ q: query });
    if (dictionaryUri) params.set('dictionary_uri', dictionaryUri);
    const res = await apiFetch(`${API_BASE}/bsdd/classes/search?${params.toString()}`);
    const result = await handleResponse<BSDDClassSearchResponse>(res);
    setPersistentCache(cacheKey, result);
    return result;
  },

  /** Search bSDD properties (property set + name pairs) matching free text. */
  async searchProperties(query: string, dictionaryUri?: string): Promise<BSDDPropertySearchResponse> {
    const cacheKey = `bsdd:properties:search:${query}:${dictionaryUri || ""}`;
    const cached = getPersistentCache<BSDDPropertySearchResponse>(cacheKey, BSDD_CACHE_TTL_MS);
    if (cached) return cached;
    const params = new URLSearchParams({ q: query });
    if (dictionaryUri) params.set('dictionary_uri', dictionaryUri);
    const res = await apiFetch(`${API_BASE}/bsdd/properties/search?${params.toString()}`);
    const result = await handleResponse<BSDDPropertySearchResponse>(res);
    setPersistentCache(cacheKey, result);
    return result;
  },

  /**
   * LLM-disambiguate a non-standard local class/property name against bSDD.
   *
   * Unlike searchClasses/searchProperties (instant substring match), this
   * calls an LLM and costs real latency -- use it as an on-demand "suggest
   * via AI" action, not on every keystroke, and never cache the result
   * (the same query can get a different pick from a different model).
   */
  async semanticMatch(payload: SemanticMatchRequest): Promise<SemanticMatchResponse> {
    const res = await apiFetch(`${API_BASE}/bsdd/semantic-match`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<SemanticMatchResponse>(res);
  },

  /** Fetch one bSDD class definition with its standardized properties. */
  async getClass(classCode: string, dictionaryUri?: string): Promise<BSDDClassItem> {
    const cacheKey = `bsdd:class:${classCode}:${dictionaryUri || ""}`;
    const cached = getPersistentCache<BSDDClassItem>(cacheKey, BSDD_CACHE_TTL_MS);
    if (cached) return cached;
    const params = dictionaryUri ? `?dictionary_uri=${encodeURIComponent(dictionaryUri)}` : '';
    const res = await apiFetch(`${API_BASE}/bsdd/classes/${encodeURIComponent(classCode)}${params}`);
    const result = await handleResponse<BSDDClassItem>(res);
    setPersistentCache(cacheKey, result);
    return result;
  },

  /**
   * Every class in the local ontology cache -- backs the bSDD Wiki's browsable tree.
   *
   * Not persisted to localStorage: the response is the full ~16k-row ontology
   * (a multi-MB payload), and the backend already serves it from an in-memory,
   * file-backed cache in well under 50ms (see BSDDOntologyRepository), so a
   * 30-day localStorage copy just burns quota for no real latency win. Kept
   * in-memory for the tab's lifetime instead, so navigating away from and
   * back to the bSDD Wiki within one session doesn't re-fetch it.
   */
  async listOntologyClasses(): Promise<BSDDOntologyClassSummary[]> {
    if (ontologyClassesMemoryCache) return ontologyClassesMemoryCache;
    const res = await apiFetch(`${API_BASE}/bsdd/ontology/classes`);
    const result = await handleResponse<BSDDOntologyClassSummary[]>(res);
    ontologyClassesMemoryCache = result;
    return result;
  },

  /** Full class detail from the local ontology, by its full bSDD URI. */
  async getOntologyClass(uri: string): Promise<BSDDClassItem> {
    const cacheKey = `bsdd:ontology:class:${uri}`;
    const cached = getPersistentCache<BSDDClassItem>(cacheKey, BSDD_CACHE_TTL_MS);
    if (cached) return cached;
    const res = await apiFetch(`${API_BASE}/bsdd/ontology/class?uri=${encodeURIComponent(uri)}`);
    const result = await handleResponse<BSDDClassItem>(res);
    setPersistentCache(cacheKey, result);
    return result;
  },

  /** Full property detail from the local ontology, by its full bSDD URI, plus classes using it. */
  async getOntologyProperty(uri: string): Promise<BSDDOntologyPropertyDetail> {
    const cacheKey = `bsdd:ontology:property:${uri}`;
    const cached = getPersistentCache<BSDDOntologyPropertyDetail>(cacheKey, BSDD_CACHE_TTL_MS);
    if (cached) return cached;
    const res = await apiFetch(`${API_BASE}/bsdd/ontology/property?uri=${encodeURIComponent(uri)}`);
    const result = await handleResponse<BSDDOntologyPropertyDetail>(res);
    setPersistentCache(cacheKey, result);
    return result;
  },
};
