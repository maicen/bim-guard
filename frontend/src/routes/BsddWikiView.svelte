<script lang="ts">
  import { BookText, Box, ExternalLink, Search, Tag } from "lucide-svelte";
  import { bsddApi } from "../lib/api";
  import type { BSDDClassItem, BSDDOntologyClassSummary, BSDDOntologyPropertyDetail } from "../lib/types";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";

  let classes = $state<BSDDOntologyClassSummary[]>([]);
  let isLoadingList = $state(true);
  let listError = $state("");
  let search = $state("");

  // Two things can be open in the main panel: a class or a property. Only
  // one is ever "selected" -- viewing a property remembers which class it
  // was reached from so "Back" has somewhere to go, the way a wiki article
  // remembers the page you clicked in from.
  let selectedClassUri = $state<string | null>(null);
  let selectedPropertyUri = $state<string | null>(null);
  let cameFromClassUri = $state<string | null>(null);

  let classDetail = $state<BSDDClassItem | null>(null);
  let propertyDetail = $state<BSDDOntologyPropertyDetail | null>(null);
  let isLoadingDetail = $state(false);
  let detailError = $state("");
  let propertyFilter = $state("");

  async function loadList() {
    isLoadingList = true;
    listError = "";
    try {
      classes = (await bsddApi.listOntologyClasses()).sort((a, b) => a.name.localeCompare(b.name));
    } catch (err: any) {
      listError = err.message || "Failed to load the local bSDD ontology.";
    } finally {
      isLoadingList = false;
    }
  }
  loadList();

  let classByUri = $derived(new Map(classes.map((c) => [c.uri, c])));
  let filteredClasses = $derived(
    (() => {
      const needle = search.trim().toLowerCase();
      if (!needle) return classes;
      return classes.filter(
        (c) => c.name.toLowerCase().includes(needle) || c.code.toLowerCase().includes(needle),
      );
    })(),
  );

  async function selectClass(uri: string) {
    selectedClassUri = uri;
    selectedPropertyUri = null;
    propertyFilter = "";
    isLoadingDetail = true;
    detailError = "";
    classDetail = null;
    try {
      classDetail = await bsddApi.getOntologyClass(uri);
    } catch (err: any) {
      detailError = err.message || "Failed to load this class.";
    } finally {
      isLoadingDetail = false;
    }
  }

  async function selectProperty(uri: string, fromClassUri: string | null) {
    selectedPropertyUri = uri;
    cameFromClassUri = fromClassUri;
    isLoadingDetail = true;
    detailError = "";
    propertyDetail = null;
    try {
      propertyDetail = await bsddApi.getOntologyProperty(uri);
    } catch (err: any) {
      detailError = err.message || "Failed to load this property.";
    } finally {
      isLoadingDetail = false;
    }
  }

  function backToClass() {
    selectedPropertyUri = null;
    propertyDetail = null;
    if (cameFromClassUri) selectClass(cameFromClassUri);
  }

  function parentUri(item: BSDDClassItem): string | null {
    if (!item.parent_class_code) return null;
    // Every crawled class lives in the same dictionary as its ancestors.
    const base = item.dictionary_uri.replace(/\/$/, "");
    return `${base}/class/${item.parent_class_code}`;
  }

  let filteredProperties = $derived(
    (() => {
      if (!classDetail) return [];
      const needle = propertyFilter.trim().toLowerCase();
      if (!needle) return classDetail.properties;
      return classDetail.properties.filter(
        (p) =>
          p.name.toLowerCase().includes(needle) ||
          (p.property_set || "").toLowerCase().includes(needle),
      );
    })(),
  );
</script>

<div class="mx-auto space-y-6">
  <PageHeader
    category="Manuals"
    title="bSDD Wiki"
    icon={BookText}
    subtitle="Browse this app's local buildingSMART Data Dictionary cache -- the same classes and properties the rule builder's hover cards and autocomplete draw from, without a live bSDD lookup. Seeded by scripts/crawl_bsdd_ontology.py; grows automatically as the app looks up anything not yet cached."
  />

  <div class="grid grid-cols-1 gap-4 lg:grid-cols-[280px,1fr]">
    <!-- Class list -->
    <div class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
      <div class="relative">
        <Search class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          bind:value={search}
          placeholder="Filter classes..."
          class="w-full rounded-lg border border-slate-800 bg-slate-950 py-1.5 pl-8 pr-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        />
      </div>

      {#if isLoadingList}
        <LoadingState message="Loading ontology..." />
      {:else if listError}
        <p class="text-xs text-rose-400">{listError}</p>
      {:else if filteredClasses.length === 0}
        <p class="text-xs text-slate-500">No classes match "{search}".</p>
      {:else}
        <div class="max-h-[60vh] space-y-0.5 overflow-y-auto">
          {#each filteredClasses as cls (cls.uri)}
            <button
              type="button"
              onclick={() => selectClass(cls.uri)}
              class="block w-full rounded-lg px-2.5 py-1.5 text-left transition-colors {selectedClassUri ===
              cls.uri
                ? 'bg-accent/15 text-accent'
                : 'text-slate-300 hover:bg-slate-800/60'}"
            >
              <span class="block truncate text-xs font-semibold">{cls.name}</span>
              <span class="block truncate font-mono text-nano text-slate-500">{cls.code}</span>
            </button>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Detail panel -->
    <div class="min-h-[60vh] rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
      {#if isLoadingDetail}
        <LoadingState message="Loading..." />
      {:else if detailError}
        <p class="text-xs text-rose-400">{detailError}</p>
      {:else if selectedPropertyUri && propertyDetail}
        <div class="space-y-4">
          {#if cameFromClassUri}
            <button
              type="button"
              onclick={backToClass}
              class="text-xs text-accent hover:underline"
            >
              &larr; Back to {classByUri.get(cameFromClassUri)?.name || "class"}
            </button>
          {/if}

          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-blue-800/50 bg-blue-950/50 text-accent">
              <Tag class="h-4 w-4" />
            </div>
            <div class="min-w-0">
              <h2 class="text-lg font-bold text-slate-50">{propertyDetail.name}</h2>
              <p class="font-mono text-micro text-slate-500">{propertyDetail.code}</p>
            </div>
          </div>

          <p class="text-sm leading-relaxed text-slate-300">
            {propertyDetail.definition || propertyDetail.description || "No definition available."}
          </p>
          {#if propertyDetail.definition && propertyDetail.description}
            <p class="text-xs italic text-slate-500">Note: {propertyDetail.description}</p>
          {/if}

          <dl class="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
            {#if propertyDetail.data_type}
              <div>
                <dt class="uppercase tracking-wider text-slate-500">Type</dt>
                <dd class="font-mono text-slate-200">{propertyDetail.data_type}</dd>
              </div>
            {/if}
            {#if propertyDetail.units.length}
              <div>
                <dt class="uppercase tracking-wider text-slate-500">Units</dt>
                <dd class="font-mono text-slate-200">{propertyDetail.units.join(", ")}</dd>
              </div>
            {/if}
          </dl>

          {#if propertyDetail.used_by_classes.length}
            <div>
              <h3 class="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Used by {propertyDetail.used_by_classes.length}
                {propertyDetail.used_by_classes.length === 1 ? "class" : "classes"}
              </h3>
              <div class="flex flex-wrap gap-1.5">
                {#each propertyDetail.used_by_classes as cls (cls.uri)}
                  <button
                    type="button"
                    onclick={() => selectClass(cls.uri)}
                    class="rounded-lg border border-slate-700/60 bg-slate-800 px-2 py-1 font-mono text-nano text-slate-300 transition-colors hover:border-accent/50 hover:text-accent"
                  >
                    {cls.code}
                  </button>
                {/each}
              </div>
            </div>
          {/if}

          <a
            href={propertyDetail.uri}
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1 text-xs text-accent hover:underline"
          >
            View in bSDD <ExternalLink class="h-3 w-3" />
          </a>
        </div>
      {:else if selectedClassUri && classDetail}
        <div class="space-y-4">
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-blue-800/50 bg-blue-950/50 text-accent">
              <Box class="h-4 w-4" />
            </div>
            <div class="min-w-0">
              <h2 class="text-lg font-bold text-slate-50">{classDetail.name}</h2>
              <p class="font-mono text-micro text-slate-500">{classDetail.code}</p>
            </div>
          </div>

          <p class="text-sm leading-relaxed text-slate-300">
            {classDetail.definition || classDetail.description || "No definition available."}
          </p>
          {#if classDetail.definition && classDetail.description}
            <p class="text-xs italic text-slate-500">Note: {classDetail.description}</p>
          {/if}

          {#if classDetail.parent_class_code}
            {@const pUri = parentUri(classDetail)}
            <div class="flex items-center gap-2 text-xs">
              <span class="uppercase tracking-wider text-slate-500">Extends</span>
              {#if pUri && classByUri.has(pUri)}
                <button
                  type="button"
                  onclick={() => selectClass(pUri)}
                  class="rounded-lg border border-slate-700/60 bg-slate-800 px-2 py-1 font-mono text-nano text-slate-300 transition-colors hover:border-accent/50 hover:text-accent"
                >
                  {classDetail.parent_class_code}
                </button>
              {:else}
                <span class="font-mono text-nano text-slate-400">{classDetail.parent_class_code}</span>
              {/if}
            </div>
          {/if}

          {#if classDetail.child_class_codes.length}
            <div>
              <h3 class="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Subtypes
              </h3>
              <div class="flex flex-wrap gap-1.5">
                {#each classDetail.child_class_codes as code (code)}
                  {@const childUri = `${classDetail.dictionary_uri.replace(/\/$/, "")}/class/${code}`}
                  <button
                    type="button"
                    onclick={() => classByUri.has(childUri) && selectClass(childUri)}
                    disabled={!classByUri.has(childUri)}
                    class="rounded-lg border border-slate-700/60 bg-slate-800 px-2 py-1 font-mono text-nano text-slate-300 transition-colors enabled:hover:border-accent/50 enabled:hover:text-accent disabled:opacity-50"
                  >
                    {code}
                  </button>
                {/each}
              </div>
            </div>
          {/if}

          <a
            href={classDetail.uri}
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1 text-xs text-accent hover:underline"
          >
            View in bSDD <ExternalLink class="h-3 w-3" />
          </a>

          <div class="border-t border-slate-800 pt-4">
            <div class="mb-2 flex items-center justify-between gap-3">
              <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">
                {classDetail.properties.length} standardized properties
              </h3>
              <input
                type="text"
                bind:value={propertyFilter}
                placeholder="Filter properties..."
                class="w-48 rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1 text-nano text-slate-50 focus:border-accent focus:outline-none"
              />
            </div>
            <div class="max-h-96 overflow-y-auto rounded-xl border border-slate-800">
              <table class="w-full text-xs">
                <thead class="sticky top-0 bg-slate-900">
                  <tr class="border-b border-slate-800 text-micro uppercase tracking-wider text-slate-500">
                    <th class="px-3 py-2 text-left">Property</th>
                    <th class="px-3 py-2 text-left">Pset</th>
                    <th class="px-3 py-2 text-left">Type</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/60">
                  {#each filteredProperties as prop (prop.uri + ":" + (prop.property_set || ""))}
                    <tr class="hover:bg-slate-800/30">
                      <td class="px-3 py-1.5">
                        <button
                          type="button"
                          onclick={() => selectProperty(prop.uri, selectedClassUri)}
                          class="font-medium text-slate-200 hover:text-accent hover:underline"
                        >
                          {prop.name}
                        </button>
                      </td>
                      <td class="px-3 py-1.5 font-mono text-nano text-slate-500">{prop.property_set || "-"}</td>
                      <td class="px-3 py-1.5 font-mono text-nano text-slate-500">{prop.data_type || "-"}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      {:else}
        <EmptyState
          icon={BookText}
          title="Pick a class"
          description="Choose a class from the list to see its definition, hierarchy, and standardized properties."
        />
      {/if}
    </div>
  </div>
</div>
