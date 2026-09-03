/**
 * Standardized Client-Side Caching Architecture for BIM-Guard
 * Follows SOLID Principles:
 * - Single Responsibility: Clear separation between storage, SWR policy, and entity state.
 * - Open/Closed: Extensible storage backends and customizable entity stores.
 * - Liskov Substitution: All cache storage providers implement ICacheStorage.
 * - Interface Segregation: Discrete interfaces for read, write, SWR, and reactive subscriptions.
 * - Dependency Inversion: High-level API modules depend on abstract cache stores.
 */

export interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

export type Listener<T> = (data: T) => void;
export type Unsubscribe = () => void;

/**
 * Interface Segregation: Read-only access contract
 */
export interface IReadOnlyCache<K, V> {
  get(key: K): V | undefined;
  has(key: K): boolean;
  isFresh(key: K, ttlMs: number): boolean;
  getEntry(key: K): CacheEntry<V> | undefined;
}

/**
 * Interface Segregation: Mutable cache storage contract
 */
export interface ICacheStorage<K, V> extends IReadOnlyCache<K, V> {
  set(key: K, value: V): void;
  delete(key: K): boolean;
  clear(): void;
}

/**
 * Interface Segregation: Reactive subscription contract
 */
export interface ISubscribable<T> {
  subscribe(listener: Listener<T>): Unsubscribe;
}

/**
 * Concrete generic in-memory cache storage implementing ICacheStorage (SRP)
 */
export class InMemoryCache<K, V> implements ICacheStorage<K, V> {
  private readonly store = new Map<K, CacheEntry<V>>();

  get(key: K): V | undefined {
    const entry = this.store.get(key);
    return entry ? entry.data : undefined;
  }

  getEntry(key: K): CacheEntry<V> | undefined {
    return this.store.get(key);
  }

  has(key: K): boolean {
    return this.store.has(key);
  }

  isFresh(key: K, ttlMs: number): boolean {
    const entry = this.store.get(key);
    if (!entry) return false;
    return Date.now() - entry.timestamp < ttlMs;
  }

  set(key: K, value: V): void {
    this.store.set(key, { data: value, timestamp: Date.now() });
  }

  delete(key: K): boolean {
    return this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }

  entries(): IterableIterator<[K, CacheEntry<V>]> {
    return this.store.entries();
  }

  forEach(callback: (entry: CacheEntry<V>, key: K) => void): void {
    this.store.forEach(callback);
  }
}

export interface SWROptions {
  forceRefresh?: boolean;
}

/**
 * Stale-While-Revalidate (SWR) Coordinator with Promise Deduplication (SRP & DIP)
 */
export class SWRStore<K, V> implements ISubscribable<V> {
  protected readonly storage: ICacheStorage<K, V>;
  protected readonly inFlight = new Map<K, Promise<V>>();
  protected readonly listeners = new Set<Listener<V>>();
  public readonly ttlMs: number;

  constructor(storage: ICacheStorage<K, V> = new InMemoryCache<K, V>(), ttlMs: number = 60_000) {
    this.storage = storage;
    this.ttlMs = ttlMs;
  }

  getCached(key: K): V | undefined {
    return this.storage.get(key);
  }

  subscribe(listener: Listener<V>): Unsubscribe {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  protected notify(data: V): void {
    this.listeners.forEach((listener) => {
      try {
        listener(data);
      } catch (err) {
        console.error("Error in cache listener:", err);
      }
    });
  }

  async execute(key: K, fetcher: () => Promise<V>, options: SWROptions = {}): Promise<V> {
    const cached = this.storage.get(key);
    const isFresh = this.storage.isFresh(key, this.ttlMs);

    // 1. Return fresh cached data immediately
    if (!options.forceRefresh && isFresh && cached !== undefined) {
      return cached;
    }

    // 2. Reuse active in-flight request for identical key
    if (this.inFlight.has(key)) {
      if (!options.forceRefresh && cached !== undefined) {
        return cached;
      }
      return this.inFlight.get(key)!;
    }

    // 3. Stale-While-Revalidate: return stale data immediately and revalidate in background
    if (!options.forceRefresh && cached !== undefined) {
      const backgroundPromise = (async () => {
        try {
          const freshData = await fetcher();
          this.storage.set(key, freshData);
          this.notify(freshData);
          return freshData;
        } finally {
          this.inFlight.delete(key);
        }
      })();
      this.inFlight.set(key, backgroundPromise);
      return cached;
    }

    // 4. Direct fetch when no cached data exists or when forcing refresh
    const fetchPromise = (async () => {
      try {
        const freshData = await fetcher();
        this.storage.set(key, freshData);
        this.notify(freshData);
        return freshData;
      } finally {
        this.inFlight.delete(key);
      }
    })();

    this.inFlight.set(key, fetchPromise);
    return fetchPromise;
  }

  set(key: K, value: V): void {
    this.storage.set(key, value);
    this.notify(value);
  }

  delete(key: K): boolean {
    return this.storage.delete(key);
  }

  clear(): void {
    this.storage.clear();
    this.inFlight.clear();
  }
}

/**
 * Standardized Entity Cache Store for REST collections (SRP, OCP, DIP)
 * Encapsulates list caching, item caching by ID, mutation updates, and cross-view sync.
 */
export class EntityCacheStore<TItem, TId extends string | number = number> implements ISubscribable<
  TItem[]
> {
  private readonly listStore: SWRStore<string, TItem[]>;
  private readonly itemStore: SWRStore<TId, TItem>;
  private readonly idExtractor: (item: TItem) => TId;

  constructor(
    idExtractor: (item: TItem) => TId,
    listTtlMs: number = 60_000,
    itemTtlMs: number = 60_000,
  ) {
    this.idExtractor = idExtractor;
    this.listStore = new SWRStore<string, TItem[]>(new InMemoryCache<string, TItem[]>(), listTtlMs);
    this.itemStore = new SWRStore<TId, TItem>(new InMemoryCache<TId, TItem>(), itemTtlMs);
  }

  getCachedList(queryKey: string = "__default__"): TItem[] | undefined {
    return this.listStore.getCached(queryKey);
  }

  getCachedItem(id: TId): TItem | undefined {
    return this.itemStore.getCached(id);
  }

  subscribe(listener: Listener<TItem[]>): Unsubscribe {
    const unsub = this.listStore.subscribe(listener);
    const current = this.listStore.getCached("__default__");
    if (current) {
      listener(current);
    }
    return unsub;
  }

  async fetchList(
    queryKey: string = "__default__",
    fetcher: () => Promise<TItem[]>,
    options: SWROptions = {},
  ): Promise<TItem[]> {
    const list = await this.listStore.execute(queryKey, fetcher, options);
    // Automatically seed/refresh individual item stores
    list.forEach((item) => {
      this.itemStore.set(this.idExtractor(item), item);
    });
    return list;
  }

  async fetchItem(
    id: TId,
    fetcher: () => Promise<TItem>,
    options: SWROptions = {},
  ): Promise<TItem> {
    const item = await this.itemStore.execute(id, fetcher, options);
    this.updateInList(item);
    return item;
  }

  addOrUpdate(item: TItem): void {
    const id = this.idExtractor(item);
    this.itemStore.set(id, item);
    this.updateInList(item);
  }

  remove(id: TId): void {
    this.itemStore.delete(id);
    const current = this.listStore.getCached("__default__");
    if (current) {
      const updated = current.filter((item) => this.idExtractor(item) !== id);
      this.listStore.set("__default__", updated);
    }
  }

  private updateInList(item: TItem): void {
    const id = this.idExtractor(item);
    const current = this.listStore.getCached("__default__");
    if (current) {
      const idx = current.findIndex((i) => this.idExtractor(i) === id);
      let nextList: TItem[];
      if (idx >= 0) {
        nextList = [...current];
        nextList[idx] = item;
      } else {
        nextList = [item, ...current];
      }
      this.listStore.set("__default__", nextList);
    }
  }

  clear(): void {
    this.listStore.clear();
    this.itemStore.clear();
  }
}
