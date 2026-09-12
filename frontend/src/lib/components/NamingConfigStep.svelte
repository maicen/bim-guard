<script lang="ts">
  import { run } from "svelte/legacy";

  import { onMount } from "svelte";
  import { Plus, X, Info } from "lucide-svelte";
  import { namingConfigApi } from "../api";
  import type { NamingCatalog, NamingCode, NamingConfigPayload } from "../types";

  interface Props {
    /**
     * The wizard creates the project on the final step, so this component has
     * no project to save against while it is on screen. It edits a plain object
     * the wizard holds and the wizard persists once the project row exists;
     * that is why there is no projectId prop and no save button here.
     */
    config: NamingConfigPayload;
  }

  let { config = $bindable() }: Props = $props();

  type TabId = "metadata" | "levels" | "types" | "disciplines" | "status" | "convention";

  const TABS: { id: TabId; label: string }[] = [
    { id: "metadata", label: "Metadata" },
    { id: "levels", label: "Levels" },
    { id: "types", label: "Types" },
    { id: "disciplines", label: "Disciplines" },
    { id: "status", label: "CDE Status" },
    { id: "convention", label: "Convention" },
  ];

  // Which library each code tab narrows, and which config field holds the
  // project's selection from it. Kept as one table so a tab is a lookup rather
  // than a fourth copy of the same add/remove markup.
  const CODE_TABS: Record<
    string,
    { libraryKey: string; field: keyof NamingConfigPayload; noun: string }
  > = {
    levels: { libraryKey: "levels", field: "level_codes", noun: "level" },
    types: { libraryKey: "types", field: "type_codes", noun: "information type" },
    disciplines: { libraryKey: "disciplines", field: "discipline_codes", noun: "discipline" },
  };

  let activeTab: TabId = $state("metadata");
  let catalog: NamingCatalog | null = $state(null);
  let catalogError = $state("");
  let preview = $state("");
  let appliedFormat = $state("");
  let unresolved: string[] = $state([]);
  let customCode = $state("");
  let customLabel = $state("");

  onMount(async () => {
    try {
      catalog = await namingConfigApi.catalog();
    } catch (err: any) {
      // The step stays usable without the catalog: the metadata fields are free
      // text and the code tabs simply have nothing to offer from the library.
      catalogError = err?.message || "The naming catalog could not be loaded.";
    }
  });

  // Re-render the sample name whenever anything it depends on changes. The
  // round trip is what keeps the preview and the eventual export in agreement,
  // and the guard stops a stale response overwriting a newer one.
  let previewToken = 0;

  async function refreshPreview(_signature: string) {
    const token = ++previewToken;
    try {
      const result = await namingConfigApi.preview(config);
      if (token !== previewToken) return;
      preview = result.name;
      appliedFormat = result.applied_format;
      unresolved = result.unresolved_tokens;
    } catch {
      if (token !== previewToken) return;
      preview = "";
      appliedFormat = "";
      unresolved = [];
    }
  }

  function addCode(code: NamingCode) {
    if (!codeTab) return;
    config = { ...config, [codeTab.field]: [...selected, code] };
  }

  function removeCode(code: string) {
    if (!codeTab) return;
    config = { ...config, [codeTab.field]: selected.filter((c) => c.code !== code) };
  }

  /** Add a code the master library does not carry, scoped to this project. */
  function addCustomCode() {
    const code = customCode.trim().toUpperCase();
    if (!codeTab || !code || selected.some((c) => c.code === code)) return;
    config = {
      ...config,
      [codeTab.field]: [...selected, { code, label: customLabel.trim() || code }],
    };
    customCode = "";
    customLabel = "";
  }
  let selectableStatuses = $derived((catalog?.cde_statuses ?? []).filter((s) => s.selectable));
  let conventions = $derived([
    ...(catalog?.conventions ?? []),
    ...(config.custom_conventions ?? []),
  ]);
  let activeConvention = $derived(
    conventions.find((c) => c.id === config.active_convention) ?? null,
  );
  let codeTab = $derived(CODE_TABS[activeTab]);
  let library = $derived((catalog?.codes?.[codeTab?.libraryKey ?? ""] ?? []) as NamingCode[]);
  let selected = $derived(
    ((config[codeTab?.field ?? "level_codes"] as NamingCode[]) ?? []) as NamingCode[],
  );
  let available = $derived(library.filter((c) => !selected.some((s) => s.code === c.code)));
  run(() => {
    refreshPreview(JSON.stringify(config));
  });
</script>

<div class="space-y-4">
  <p class="text-xs text-fg-muted">
    How this project names its information containers, per BS EN ISO 19650-1:2018. Optional — a
    project without a naming setup uses the defaults shown here.
  </p>

  {#if catalogError}
    <div
      class="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-caption text-amber-300"
    >
      {catalogError} The metadata fields below still work; the code libraries are unavailable.
    </div>
  {/if}

  <!-- Tabs -->
  <div class="flex flex-wrap gap-1 border-b border-border-default pb-2">
    {#each TABS as tab (tab.id)}
      <button
        type="button"
        onclick={() => (activeTab = tab.id)}
        class="rounded-lg px-3 py-1.5 text-caption font-semibold transition-colors {activeTab ===
        tab.id
          ? 'bg-accent text-white'
          : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
      >
        {tab.label}
      </button>
    {/each}
  </div>

  {#if activeTab === "metadata"}
    <div class="grid grid-cols-2 gap-3">
      <div>
        <label
          for="naming-project-code"
          class="mb-1.5 block text-caption font-medium text-fg-muted"
        >
          Project Code
        </label>
        <input
          id="naming-project-code"
          bind:value={config.project_code}
          placeholder="A1234"
          class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-sm text-fg-primary focus:border-accent focus:outline-hidden"
        />
      </div>
      <div>
        <label for="naming-originator" class="mb-1.5 block text-caption font-medium text-fg-muted">
          Originator Code
        </label>
        <input
          id="naming-originator"
          bind:value={config.originator_code}
          placeholder="BIM01"
          class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-sm text-fg-primary focus:border-accent focus:outline-hidden"
        />
      </div>
      <div>
        <label for="naming-type" class="mb-1.5 block text-caption font-medium text-fg-muted">
          Information Type
        </label>
        <select
          id="naming-type"
          bind:value={config.type_code}
          class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 text-sm text-fg-primary focus:border-accent focus:outline-hidden"
        >
          {#each [...(catalog?.codes?.types ?? []), ...(config.type_codes ?? [])] as t (t)}
            <option value={t.code}>{t.code} — {t.label}</option>
          {/each}
        </select>
      </div>
      <div>
        <label
          for="naming-suitability"
          class="mb-1.5 block text-caption font-medium text-fg-muted"
        >
          Suitability (CDE Status)
        </label>
        <select
          id="naming-suitability"
          bind:value={config.suitability}
          class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 text-sm text-fg-primary focus:border-accent focus:outline-hidden"
        >
          {#each selectableStatuses as s (s)}
            <option value={s.code}>{s.code} — {s.label}</option>
          {/each}
        </select>
      </div>
      <div>
        <label for="naming-revision" class="mb-1.5 block text-caption font-medium text-fg-muted">
          Revision
        </label>
        <input
          id="naming-revision"
          bind:value={config.revision}
          placeholder="01"
          class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-sm text-fg-primary focus:border-accent focus:outline-hidden"
        />
        <p class="mt-1 text-micro text-fg-muted">P01 preliminary · C01 contract</p>
      </div>
      <div>
        <label
          for="naming-date-format"
          class="mb-1.5 block text-caption font-medium text-fg-muted"
        >
          Date Format
        </label>
        <select
          id="naming-date-format"
          bind:value={config.date_format}
          class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 text-sm text-fg-primary focus:border-accent focus:outline-hidden"
        >
          {#each catalog?.date_formats ?? ["YYMMDD"] as f (f)}
            <option value={f}>{f}</option>
          {/each}
        </select>
      </div>
      <div>
        <label for="naming-separator" class="mb-1.5 block text-caption font-medium text-fg-muted">
          Separator
        </label>
        <select
          id="naming-separator"
          bind:value={config.separator}
          class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-sm text-fg-primary focus:border-accent focus:outline-hidden"
        >
          {#each catalog?.separators ?? ["_"] as sep (sep)}
            <option value={sep}>{sep}</option>
          {/each}
        </select>
      </div>
    </div>

    {#if config.active_convention === "uniclass"}
      <!-- Only asked for when the active convention consumes them; the other
           four formats carry no classification tokens. -->
      <div class="grid grid-cols-2 gap-3 border-t border-border-default pt-3">
        <div>
          <label for="naming-class-a" class="mb-1.5 block text-caption font-medium text-fg-muted">
            Uniclass Primary
          </label>
          <input
            id="naming-class-a"
            bind:value={config.class_a}
            placeholder="Ss_25"
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-sm text-fg-primary focus:border-accent focus:outline-hidden"
          />
        </div>
        <div>
          <label for="naming-class-b" class="mb-1.5 block text-caption font-medium text-fg-muted">
            Uniclass Secondary
          </label>
          <input
            id="naming-class-b"
            bind:value={config.class_b}
            placeholder="Pr_20"
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-sm text-fg-primary focus:border-accent focus:outline-hidden"
          />
        </div>
      </div>
    {/if}
  {:else if codeTab}
    <div class="space-y-3">
      <div>
        <span class="mb-1.5 block text-caption font-medium text-fg-muted">
          Active {codeTab.noun} codes
        </span>
        {#if selected.length === 0}
          <p class="rounded-xl border border-border-default p-3 text-caption text-fg-muted">
            None selected — the whole library is available to this project.
          </p>
        {:else}
          <div class="flex flex-wrap gap-1.5">
            {#each selected as code (code)}
              <span
                class="inline-flex items-center gap-1.5 rounded-lg bg-surface-overlay py-1 pl-2.5 pr-1.5 text-caption text-fg-primary"
              >
                <span class="font-mono font-semibold">{code.code}</span>
                <span class="text-fg-muted">{code.label}</span>
                <button
                  type="button"
                  onclick={() => removeCode(code.code)}
                  aria-label="Remove {code.code}"
                  class="rounded p-0.5 text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
                >
                  <X class="h-3 w-3" />
                </button>
              </span>
            {/each}
          </div>
        {/if}
      </div>

      <div class="border-t border-border-default pt-3">
        <span class="mb-1.5 block text-caption font-medium text-fg-muted">
          Master library — ISO 19650-1 §12, Annex A
        </span>
        {#if available.length === 0}
          <p class="text-caption text-fg-muted">Every code in the library is already active.</p>
        {:else}
          <div class="flex flex-wrap gap-1.5">
            {#each available as code (code)}
              <button
                type="button"
                onclick={() => addCode(code)}
                class="inline-flex items-center gap-1.5 rounded-lg border border-border-default px-2.5 py-1 text-caption text-fg-secondary transition-colors hover:border-accent hover:text-fg-primary"
              >
                <Plus class="h-3 w-3" />
                <span class="font-mono font-semibold">{code.code}</span>
                <span class="text-fg-muted">{code.label}</span>
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <div class="flex items-end gap-2 border-t border-border-default pt-3">
        <div class="w-24">
          <label
            for="naming-custom-code"
            class="mb-1.5 block text-caption font-medium text-fg-muted"
          >
            Custom code
          </label>
          <input
            id="naming-custom-code"
            bind:value={customCode}
            placeholder="DR"
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-sm text-fg-primary focus:border-accent focus:outline-hidden"
          />
        </div>
        <div class="flex-1">
          <label
            for="naming-custom-label"
            class="mb-1.5 block text-caption font-medium text-fg-muted"
          >
            Meaning
          </label>
          <input
            id="naming-custom-label"
            bind:value={customLabel}
            placeholder="Drawing"
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 text-sm text-fg-primary focus:border-accent focus:outline-hidden"
          />
        </div>
        <button
          type="button"
          onclick={addCustomCode}
          disabled={!customCode.trim()}
          class="rounded-xl bg-surface-overlay px-4 py-2 text-caption font-semibold text-fg-primary transition-colors hover:bg-surface-hover disabled:opacity-40"
        >
          Add
        </button>
      </div>
      <p class="text-micro text-fg-muted">
        Custom codes belong to this project. The master library is never modified.
      </p>
    </div>
  {:else if activeTab === "status"}
    <div class="space-y-2">
      <p class="text-caption text-fg-muted">
        ISO 19650-2 Table 1. Reference only — a project sets its own suitability on the Metadata
        tab.
      </p>
      <div class="divide-y divide-border-subtle rounded-xl border border-border-default">
        {#each catalog?.cde_statuses ?? [] as s (s)}
          <div class="flex items-center gap-3 px-3 py-2">
            <span class="h-2.5 w-2.5 shrink-0 rounded-full" style="background-color: {s.colour}"
            ></span>
            <span class="w-8 font-mono text-xs font-semibold text-fg-primary">{s.code}</span>
            <span class="flex-1 text-caption text-fg-secondary">{s.label}</span>
            {#if !s.selectable}
              <span class="text-micro uppercase tracking-wider text-fg-muted">Reference</span>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {:else if activeTab === "convention"}
    <div class="space-y-2">
      {#each conventions as convention (convention.id)}
        <button
          type="button"
          onclick={() => (config = { ...config, active_convention: convention.id })}
          class="w-full rounded-xl border p-3 text-left transition-colors {config.active_convention ===
          convention.id
            ? 'border-accent bg-accent/5'
            : 'border-border-default hover:border-border-interactive'}"
        >
          <div class="flex items-center gap-2">
            <span class="text-xs font-semibold text-fg-primary">{convention.name}</span>
            {#if !convention.iso_compliant}
              <span class="rounded bg-amber-500/15 px-1.5 py-0.5 text-micro text-amber-400">
                Not ISO compliant
              </span>
            {/if}
            {#if !convention.preset}
              <span class="rounded bg-surface-overlay px-1.5 py-0.5 text-micro text-fg-muted"
                >Custom</span
              >
            {/if}
          </div>
          <p class="mt-1 text-micro text-fg-muted">{convention.description}</p>
          <p class="mt-1.5 break-all font-mono text-micro text-fg-muted">{convention.format}</p>
        </button>
      {/each}
    </div>
  {/if}

  <!-- Live preview. Always on screen, whichever tab is open, because every tab
       changes the name and the name is the thing being configured. -->
  <div class="rounded-xl border border-border-default bg-surface-canvas/60 p-3">
    <div class="mb-1.5 flex items-center gap-1.5">
      <Info class="h-3 w-3 text-fg-muted" />
      <span class="text-micro font-semibold uppercase tracking-wider text-fg-muted">
        Example container name
      </span>
    </div>
    {#if preview}
      <p class="break-all font-mono text-xs text-emerald-400">{preview}</p>
      {#if appliedFormat}
        <p class="mt-1 break-all font-mono text-micro text-fg-muted">{appliedFormat}</p>
      {/if}
      {#if unresolved.length}
        <p class="mt-1 text-micro text-amber-400/80">
          Unset: {unresolved.join(", ")} — these appear literally until a value is supplied.
        </p>
      {/if}
      {#if activeConvention && !activeConvention.iso_compliant}
        <p class="mt-1 text-micro text-amber-400/80">
          {activeConvention.name} is not an ISO 19650 container name.
        </p>
      {/if}
    {:else}
      <p class="text-caption text-fg-muted">Preview unavailable.</p>
    {/if}
  </div>
</div>
