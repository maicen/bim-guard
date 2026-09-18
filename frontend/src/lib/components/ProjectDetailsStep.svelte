<script lang="ts">
  import { onMount } from "svelte";
  import { Combobox as ComboboxPrimitive } from "bits-ui";
  import { ChevronsUpDown, Lock } from "lucide-svelte";
  import { projectsApi } from "../api";
  import { detailLocks, matchingClientNames } from "../projectDetails";
  import {
    PROJECT_CODE_MAX_LENGTH,
    PROJECT_CODE_MIN_LENGTH,
    PROJECT_TYPES,
    SHORT_NAME_MAX_LENGTH,
    SHORT_NAME_MIN_LENGTH,
  } from "../types";
  import { Select } from "./ui";

  /**
   * Step 1 (Details) of the New Project wizard, shared by NewProjectView and
   * ProjectWizardModal.
   *
   * The required fields unlock in order -- client name, project name, short
   * name, project code, jurisdiction, project type -- each disabled until
   * every one before it is filled (see detailLocks). The optional fields
   * (description, size, buildings, floors) stay editable throughout.
   */
  interface Props {
    clientName: string;
    name: string;
    shortName: string;
    projectCode: string;
    description: string;
    country: string;
    projectType: string;
    projectSizeSqm: string;
    buildingsCount: string;
    floorsCount: string;
    /** Jurisdictions served by /api/projects/options; empty when it is unreachable. */
    countries?: string[];
    /** Building types served by /api/projects/options; falls back to PROJECT_TYPES. */
    projectTypes?: string[];
  }

  let {
    clientName = $bindable(),
    name = $bindable(),
    shortName = $bindable(),
    projectCode = $bindable(),
    description = $bindable(),
    country = $bindable(),
    projectType = $bindable(),
    projectSizeSqm = $bindable(),
    buildingsCount = $bindable(),
    floorsCount = $bindable(),
    countries = [],
    projectTypes = [],
  }: Props = $props();

  // Options endpoint unreachable: the four jurisdictions with a bundled
  // ruleset keep the wizard usable.
  const FALLBACK_COUNTRIES = ["Canada", "United Kingdom", "United States", "International"];

  let countryOptions = $derived(
    (countries.length ? countries : FALLBACK_COUNTRIES).map((c) => ({ value: c, label: c })),
  );
  let typeOptions = $derived(projectTypes.length ? projectTypes : PROJECT_TYPES);

  let locks = $derived(
    detailLocks({ clientName, name, shortName, projectCode, country, projectType }),
  );

  // Client names already used on projects this user can see. A failed fetch
  // only costs the pick-list; the field still takes free text.
  let knownClientNames: string[] = $state([]);
  let clientListOpen = $state(false);
  let clientSuggestions = $derived(matchingClientNames(knownClientNames, clientName));

  onMount(async () => {
    try {
      knownClientNames = (await projectsApi.clientNames()).client_names;
    } catch {
      knownClientNames = [];
    }
  });

  const inputClass =
    "w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2 text-sm text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden disabled:cursor-not-allowed disabled:opacity-40";
  const labelClass = "mb-1.5 block text-xs font-semibold uppercase tracking-wider text-fg-secondary";
</script>

{#snippet lockHint(id: string, hint: string)}
  <p {id} class="mt-1 flex items-center gap-1 text-caption text-fg-muted">
    <Lock class="h-3 w-3 shrink-0" />
    {hint}
  </p>
{/snippet}

<div class="space-y-4">
  <div>
    <label for="wizard-client-name" class={labelClass}>Client Name *</label>
    <ComboboxPrimitive.Root
      type="single"
      bind:open={clientListOpen}
      inputValue={clientName}
      onValueChange={(picked) => {
        // Picking a prior client fills the field; an empty value is bits-ui
        // deselecting, which must not wipe what is typed.
        if (picked) clientName = picked;
      }}
    >
      <div class="relative w-full">
        <ComboboxPrimitive.Input
          id="wizard-client-name"
          oninput={(e) => {
            clientName = e.currentTarget.value;
            clientListOpen = clientSuggestions.length > 0;
          }}
          placeholder="e.g. Northwind Health Trust"
          autocomplete="off"
          class="{inputClass} {knownClientNames.length ? 'pr-9' : ''}"
        />
        {#if knownClientNames.length}
          <ComboboxPrimitive.Trigger
            aria-label="Show existing clients"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-fg-muted hover:text-fg-primary"
          >
            <ChevronsUpDown class="h-3.5 w-3.5" />
          </ComboboxPrimitive.Trigger>
        {/if}
      </div>

      {#if clientSuggestions.length}
        <ComboboxPrimitive.Portal>
          <ComboboxPrimitive.Content
            class="z-70 max-h-60 w-(--bits-combobox-anchor-width) min-w-[200px] overflow-hidden rounded-xl border border-border-default bg-surface-card p-1 shadow-xl duration-150 animate-in fade-in zoom-in-95"
            sideOffset={4}
          >
            <ComboboxPrimitive.Viewport class="p-1">
              {#each clientSuggestions as client (client)}
                <ComboboxPrimitive.Item
                  value={client}
                  label={client}
                  class="flex cursor-pointer select-none items-center rounded-lg px-2.5 py-1.5 text-xs text-fg-secondary outline-hidden transition-colors data-[highlighted]:bg-surface-hover data-[highlighted]:text-fg-primary"
                >
                  {client}
                </ComboboxPrimitive.Item>
              {/each}
            </ComboboxPrimitive.Viewport>
          </ComboboxPrimitive.Content>
        </ComboboxPrimitive.Portal>
      {/if}
    </ComboboxPrimitive.Root>
    <p class="mt-1 text-caption text-fg-muted">
      The party the project is delivered for. Type a new client, or pick one used on an earlier
      project.
    </p>
  </div>

  <div>
    <label for="wizard-name" class={labelClass}>Project Name *</label>
    <input
      id="wizard-name"
      type="text"
      bind:value={name}
      disabled={!!locks.name}
      aria-describedby={locks.name ? "wizard-name-lock" : undefined}
      placeholder="e.g. BIM Headquarters Phase 1"
      class={inputClass}
    />
    {#if locks.name}{@render lockHint("wizard-name-lock", locks.name)}{/if}
  </div>

  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
    <div>
      <label for="wizard-short-name" class={labelClass}>Short Name *</label>
      <input
        id="wizard-short-name"
        type="text"
        bind:value={shortName}
        disabled={!!locks.shortName}
        aria-describedby={locks.shortName ? "wizard-short-name-lock" : undefined}
        maxlength={SHORT_NAME_MAX_LENGTH}
        placeholder="e.g. BG HQ Phase 1"
        class={inputClass}
      />
      {#if locks.shortName}
        {@render lockHint("wizard-short-name-lock", locks.shortName)}
      {:else}
        <p class="mt-1 text-caption text-fg-muted">
          Shown in the header and breadcrumbs instead of the full name ({SHORT_NAME_MIN_LENGTH}-{SHORT_NAME_MAX_LENGTH}
          characters).
        </p>
      {/if}
    </div>
    <div>
      <label for="wizard-project-code" class={labelClass}>Project Code *</label>
      <input
        id="wizard-project-code"
        type="text"
        bind:value={projectCode}
        disabled={!!locks.projectCode}
        aria-describedby={locks.projectCode ? "wizard-project-code-lock" : undefined}
        maxlength={PROJECT_CODE_MAX_LENGTH}
        placeholder="e.g. BGHQ1"
        class="{inputClass} uppercase"
      />
      {#if locks.projectCode}
        {@render lockHint("wizard-project-code-lock", locks.projectCode)}
      {:else}
        <p class="mt-1 text-caption text-fg-muted">
          ISO 19650 container naming code: {PROJECT_CODE_MIN_LENGTH}-{PROJECT_CODE_MAX_LENGTH}
          alphanumeric characters, no spaces or separators.
        </p>
      {/if}
    </div>
  </div>

  <div>
    <label for="wizard-desc" class={labelClass}>Project Description</label>
    <textarea
      id="wizard-desc"
      bind:value={description}
      rows="4"
      placeholder="Scope, regulatory framework, and notes..."
      class={inputClass}
    ></textarea>
  </div>

  <div>
    <span class={labelClass}>Jurisdiction *</span>
    <Select
      options={countryOptions}
      bind:value={country}
      disabled={!!locks.country}
      ariaLabel="Jurisdiction"
      placeholder="Select a jurisdiction…"
    />
    {#if locks.country}
      {@render lockHint("wizard-jurisdiction-lock", locks.country)}
    {:else}
      <p class="mt-1 text-caption text-fg-muted">
        Required for Architectural compliance checks; optional for Piping corrosion analysis. The
        building code is chosen on step 4, from the codes this jurisdiction publishes.
      </p>
    {/if}
  </div>

  <div>
    <div class="mb-1.5 flex items-center justify-between">
      <span class="block text-xs font-semibold uppercase tracking-wider text-fg-secondary">
        Project Type <span class="text-rose-400">*</span>
      </span>
      {#if projectType}
        <span class="rounded bg-accent/20 px-2 py-0.5 font-mono text-micro font-bold text-blue-400">
          {projectType}
        </span>
      {/if}
    </div>
    <div
      role="group"
      aria-label="Project type"
      aria-describedby={locks.projectType ? "wizard-project-type-lock" : undefined}
      class="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5"
    >
      {#each typeOptions as type (type)}
        <button
          type="button"
          disabled={!!locks.projectType}
          onclick={() => (projectType = type)}
          class="flex items-center justify-center rounded-xl border px-2.5 py-2.5 text-center text-caption font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-40 {projectType ===
          type
            ? 'border-accent bg-accent/15 text-fg-primary ring-1 ring-accent'
            : 'border-border-default bg-surface-canvas text-fg-muted enabled:hover:border-border-interactive enabled:hover:text-fg-primary'}"
        >
          {type}
        </button>
      {/each}
    </div>
    {#if locks.projectType}
      {@render lockHint("wizard-project-type-lock", locks.projectType)}
    {/if}
  </div>

  <div class="grid grid-cols-3 gap-3">
    <div>
      <label for="wizard-size" class={labelClass}>Size (m²)</label>
      <input
        id="wizard-size"
        type="number"
        min="0"
        step="any"
        bind:value={projectSizeSqm}
        placeholder="5000"
        class={inputClass}
      />
    </div>
    <div>
      <label for="wizard-buildings" class={labelClass}>Buildings</label>
      <input
        id="wizard-buildings"
        type="number"
        min="0"
        step="1"
        bind:value={buildingsCount}
        placeholder="1"
        class={inputClass}
      />
    </div>
    <div>
      <label for="wizard-floors" class={labelClass}>Floors</label>
      <input
        id="wizard-floors"
        type="number"
        min="0"
        step="1"
        bind:value={floorsCount}
        placeholder="2"
        class={inputClass}
      />
    </div>
  </div>
</div>
