<script lang="ts">
  import { onMount } from 'svelte';
  import { Plus, X, Info } from 'lucide-svelte';
  import { namingConfigApi } from '../api';
  import type { NamingCatalog, NamingCode, NamingConfigPayload } from '../types';

  // The wizard creates the project on the final step, so this component has no
  // project to save against while it is on screen. It edits a plain object the
  // wizard holds and the wizard persists once the project row exists; that is
  // why there is no projectId prop and no save button here.
  export let config: NamingConfigPayload;

  type TabId = 'metadata' | 'levels' | 'types' | 'disciplines' | 'status' | 'convention';

  const TABS: { id: TabId; label: string }[] = [
    { id: 'metadata', label: 'Metadata' },
    { id: 'levels', label: 'Levels' },
    { id: 'types', label: 'Types' },
    { id: 'disciplines', label: 'Disciplines' },
    { id: 'status', label: 'CDE Status' },
    { id: 'convention', label: 'Convention' },
  ];

  // Which library each code tab narrows, and which config field holds the
  // project's selection from it. Kept as one table so a tab is a lookup rather
  // than a fourth copy of the same add/remove markup.
  const CODE_TABS: Record<string, { libraryKey: string; field: keyof NamingConfigPayload; noun: string }> = {
    levels: { libraryKey: 'levels', field: 'level_codes', noun: 'level' },
    types: { libraryKey: 'types', field: 'type_codes', noun: 'information type' },
    disciplines: { libraryKey: 'disciplines', field: 'discipline_codes', noun: 'discipline' },
  };

  let activeTab: TabId = 'metadata';
  let catalog: NamingCatalog | null = null;
  let catalogError = '';
  let preview = '';
  let appliedFormat = '';
  let unresolved: string[] = [];
  let customCode = '';
  let customLabel = '';

  onMount(async () => {
    try {
      catalog = await namingConfigApi.catalog();
    } catch (err: any) {
      // The step stays usable without the catalog: the metadata fields are free
      // text and the code tabs simply have nothing to offer from the library.
      catalogError = err?.message || 'The naming catalog could not be loaded.';
    }
  });

  $: selectableStatuses = (catalog?.cde_statuses ?? []).filter((s) => s.selectable);
  $: conventions = [...(catalog?.conventions ?? []), ...(config.custom_conventions ?? [])];
  $: activeConvention = conventions.find((c) => c.id === config.active_convention) ?? null;
  $: codeTab = CODE_TABS[activeTab];
  $: library = (catalog?.codes?.[codeTab?.libraryKey ?? ''] ?? []) as NamingCode[];
  $: selected = ((config[codeTab?.field ?? 'level_codes'] as NamingCode[]) ?? []) as NamingCode[];
  $: available = library.filter((c) => !selected.some((s) => s.code === c.code));

  // Re-render the sample name whenever anything it depends on changes. The
  // round trip is what keeps the preview and the eventual export in agreement,
  // and the guard stops a stale response overwriting a newer one.
  let previewToken = 0;
  $: refreshPreview(JSON.stringify(config));

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
      preview = '';
      appliedFormat = '';
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
    customCode = '';
    customLabel = '';
  }
</script>

<div class="space-y-4">
  <p class="text-xs text-slate-400">
    How this project names its information containers, per BS EN ISO 19650-1:2018. Optional — a
    project without a naming setup uses the defaults shown here.
  </p>

  {#if catalogError}
    <div class="p-3 rounded-xl border border-amber-500/30 bg-amber-500/5 text-[11px] text-amber-300">
      {catalogError} The metadata fields below still work; the code libraries are unavailable.
    </div>
  {/if}

  <!-- Tabs -->
  <div class="flex flex-wrap gap-1 border-b border-slate-800 pb-2">
    {#each TABS as tab}
      <button
        type="button"
        on:click={() => (activeTab = tab.id)}
        class="px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-colors {activeTab === tab.id
          ? 'bg-[#0071e3] text-white'
          : 'text-slate-400 hover:text-white hover:bg-slate-800'}"
      >
        {tab.label}
      </button>
    {/each}
  </div>

  {#if activeTab === 'metadata'}
    <div class="grid grid-cols-2 gap-3">
      <div>
        <label for="naming-project-code" class="block text-[11px] font-medium text-slate-400 mb-1.5">
          Project Code
        </label>
        <input
          id="naming-project-code"
          bind:value={config.project_code}
          placeholder="A1234"
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#0071e3]"
        />
      </div>
      <div>
        <label for="naming-originator" class="block text-[11px] font-medium text-slate-400 mb-1.5">
          Originator Code
        </label>
        <input
          id="naming-originator"
          bind:value={config.originator_code}
          placeholder="BIM01"
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#0071e3]"
        />
      </div>
      <div>
        <label for="naming-type" class="block text-[11px] font-medium text-slate-400 mb-1.5">
          Information Type
        </label>
        <select
          id="naming-type"
          bind:value={config.type_code}
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-[#0071e3]"
        >
          {#each [...(catalog?.codes?.types ?? []), ...(config.type_codes ?? [])] as t}
            <option value={t.code}>{t.code} — {t.label}</option>
          {/each}
        </select>
      </div>
      <div>
        <label for="naming-suitability" class="block text-[11px] font-medium text-slate-400 mb-1.5">
          Suitability (CDE Status)
        </label>
        <select
          id="naming-suitability"
          bind:value={config.suitability}
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-[#0071e3]"
        >
          {#each selectableStatuses as s}
            <option value={s.code}>{s.code} — {s.label}</option>
          {/each}
        </select>
      </div>
      <div>
        <label for="naming-revision" class="block text-[11px] font-medium text-slate-400 mb-1.5">
          Revision
        </label>
        <input
          id="naming-revision"
          bind:value={config.revision}
          placeholder="01"
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#0071e3]"
        />
        <p class="text-[10px] text-slate-500 mt-1">P01 preliminary · C01 contract</p>
      </div>
      <div>
        <label for="naming-date-format" class="block text-[11px] font-medium text-slate-400 mb-1.5">
          Date Format
        </label>
        <select
          id="naming-date-format"
          bind:value={config.date_format}
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-[#0071e3]"
        >
          {#each catalog?.date_formats ?? ['YYMMDD'] as f}
            <option value={f}>{f}</option>
          {/each}
        </select>
      </div>
      <div>
        <label for="naming-separator" class="block text-[11px] font-medium text-slate-400 mb-1.5">
          Separator
        </label>
        <select
          id="naming-separator"
          bind:value={config.separator}
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#0071e3]"
        >
          {#each catalog?.separators ?? ['_'] as sep}
            <option value={sep}>{sep}</option>
          {/each}
        </select>
      </div>
    </div>

    {#if config.active_convention === 'uniclass'}
      <!-- Only asked for when the active convention consumes them; the other
           four formats carry no classification tokens. -->
      <div class="grid grid-cols-2 gap-3 pt-3 border-t border-slate-800">
        <div>
          <label for="naming-class-a" class="block text-[11px] font-medium text-slate-400 mb-1.5">
            Uniclass Primary
          </label>
          <input
            id="naming-class-a"
            bind:value={config.class_a}
            placeholder="Ss_25"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#0071e3]"
          />
        </div>
        <div>
          <label for="naming-class-b" class="block text-[11px] font-medium text-slate-400 mb-1.5">
            Uniclass Secondary
          </label>
          <input
            id="naming-class-b"
            bind:value={config.class_b}
            placeholder="Pr_20"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#0071e3]"
          />
        </div>
      </div>
    {/if}

  {:else if codeTab}
    <div class="space-y-3">
      <div>
        <span class="block text-[11px] font-medium text-slate-400 mb-1.5">
          Active {codeTab.noun} codes
        </span>
        {#if selected.length === 0}
          <p class="text-[11px] text-slate-500 p-3 rounded-xl border border-slate-800">
            None selected — the whole library is available to this project.
          </p>
        {:else}
          <div class="flex flex-wrap gap-1.5">
            {#each selected as code}
              <span class="inline-flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-lg bg-slate-800 text-[11px] text-white">
                <span class="font-mono font-semibold">{code.code}</span>
                <span class="text-slate-400">{code.label}</span>
                <button
                  type="button"
                  on:click={() => removeCode(code.code)}
                  aria-label="Remove {code.code}"
                  class="p-0.5 rounded hover:bg-slate-700 text-slate-400 hover:text-white"
                >
                  <X class="w-3 h-3" />
                </button>
              </span>
            {/each}
          </div>
        {/if}
      </div>

      <div class="pt-3 border-t border-slate-800">
        <span class="block text-[11px] font-medium text-slate-400 mb-1.5">
          Master library — ISO 19650-1 §12, Annex A
        </span>
        {#if available.length === 0}
          <p class="text-[11px] text-slate-500">Every code in the library is already active.</p>
        {:else}
          <div class="flex flex-wrap gap-1.5">
            {#each available as code}
              <button
                type="button"
                on:click={() => addCode(code)}
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-800 hover:border-[#0071e3] text-[11px] text-slate-300 hover:text-white transition-colors"
              >
                <Plus class="w-3 h-3" />
                <span class="font-mono font-semibold">{code.code}</span>
                <span class="text-slate-500">{code.label}</span>
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <div class="pt-3 border-t border-slate-800 flex items-end gap-2">
        <div class="w-24">
          <label for="naming-custom-code" class="block text-[11px] font-medium text-slate-400 mb-1.5">
            Custom code
          </label>
          <input
            id="naming-custom-code"
            bind:value={customCode}
            placeholder="DR"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#0071e3]"
          />
        </div>
        <div class="flex-1">
          <label for="naming-custom-label" class="block text-[11px] font-medium text-slate-400 mb-1.5">
            Meaning
          </label>
          <input
            id="naming-custom-label"
            bind:value={customLabel}
            placeholder="Drawing"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-[#0071e3]"
          />
        </div>
        <button
          type="button"
          on:click={addCustomCode}
          disabled={!customCode.trim()}
          class="px-4 py-2 rounded-xl text-[11px] font-semibold bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-white transition-colors"
        >
          Add
        </button>
      </div>
      <p class="text-[10px] text-slate-500">
        Custom codes belong to this project. The master library is never modified.
      </p>
    </div>

  {:else if activeTab === 'status'}
    <div class="space-y-2">
      <p class="text-[11px] text-slate-400">
        ISO 19650-2 Table 1. Reference only — a project sets its own suitability on the Metadata tab.
      </p>
      <div class="rounded-xl border border-slate-800 divide-y divide-slate-800">
        {#each catalog?.cde_statuses ?? [] as s}
          <div class="flex items-center gap-3 px-3 py-2">
            <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background-color: {s.colour}"></span>
            <span class="font-mono text-xs font-semibold text-white w-8">{s.code}</span>
            <span class="text-[11px] text-slate-300 flex-1">{s.label}</span>
            {#if !s.selectable}
              <span class="text-[10px] text-slate-500 uppercase tracking-wider">Reference</span>
            {/if}
          </div>
        {/each}
      </div>
    </div>

  {:else if activeTab === 'convention'}
    <div class="space-y-2">
      {#each conventions as convention}
        <button
          type="button"
          on:click={() => (config = { ...config, active_convention: convention.id })}
          class="w-full text-left p-3 rounded-xl border transition-colors {config.active_convention ===
          convention.id
            ? 'border-[#0071e3] bg-[#0071e3]/5'
            : 'border-slate-800 hover:border-slate-700'}"
        >
          <div class="flex items-center gap-2">
            <span class="text-xs font-semibold text-white">{convention.name}</span>
            {#if !convention.iso_compliant}
              <span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400">
                Not ISO compliant
              </span>
            {/if}
            {#if !convention.preset}
              <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">Custom</span>
            {/if}
          </div>
          <p class="text-[10px] text-slate-500 mt-1">{convention.description}</p>
          <p class="text-[10px] font-mono text-slate-400 mt-1.5 break-all">{convention.format}</p>
        </button>
      {/each}
    </div>
  {/if}

  <!-- Live preview. Always on screen, whichever tab is open, because every tab
       changes the name and the name is the thing being configured. -->
  <div class="p-3 rounded-xl border border-slate-800 bg-slate-950/60">
    <div class="flex items-center gap-1.5 mb-1.5">
      <Info class="w-3 h-3 text-slate-500" />
      <span class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
        Example container name
      </span>
    </div>
    {#if preview}
      <p class="font-mono text-xs text-emerald-400 break-all">{preview}</p>
      {#if appliedFormat}
        <p class="font-mono text-[10px] text-slate-500 mt-1 break-all">{appliedFormat}</p>
      {/if}
      {#if unresolved.length}
        <p class="text-[10px] text-amber-400/80 mt-1">
          Unset: {unresolved.join(', ')} — these appear literally until a value is supplied.
        </p>
      {/if}
      {#if activeConvention && !activeConvention.iso_compliant}
        <p class="text-[10px] text-amber-400/80 mt-1">
          {activeConvention.name} is not an ISO 19650 container name.
        </p>
      {/if}
    {:else}
      <p class="text-[11px] text-slate-500">Preview unavailable.</p>
    {/if}
  </div>
</div>
