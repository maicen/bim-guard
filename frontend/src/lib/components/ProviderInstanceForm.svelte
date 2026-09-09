<script lang="ts">
  import type { Snippet } from "svelte";
  import { Loader2 } from "lucide-svelte";
  import SecretInput from "./SecretInput.svelte";

  interface KindOption {
    kind: string;
    display_name: string;
    description: string;
    requires_api_key: boolean;
    url_placeholder: string;
  }

  interface Props {
    kinds: KindOption[];
    name: string;
    kind: string;
    url: string;
    apiKey: string;
    notes: string;
    urlLabel?: string;
    urlRequired?: boolean;
    submitting: boolean;
    submitLabel?: string;
    onSubmit: () => void;
    onCancel: () => void;
    /** Kind-specific extra fields (e.g. parsing engines' Strategy select),
     * rendered between the URL and API key rows. Receives the selected
     * kind's metadata so it can decide whether to render anything. */
    extraFields?: Snippet<[KindOption | null]>;
  }

  let {
    kinds,
    name = $bindable(),
    kind = $bindable(),
    url = $bindable(),
    apiKey = $bindable(),
    notes = $bindable(),
    urlLabel = "API URL",
    urlRequired = true,
    submitting,
    submitLabel = "Save Instance",
    onSubmit,
    onCancel,
    extraFields,
  }: Props = $props();

  let selectedKindInfo = $derived(kinds.find((k) => k.kind === kind) ?? null);
</script>

<!--
  Shared add/edit form shell for one provider instance — used by both the
  Document Parsing and LLM Providers panels so registering a new instance of
  either kind looks and behaves the same.
-->
<form
  onsubmit={(e) => {
    e.preventDefault();
    onSubmit();
  }}
  class="space-y-3 rounded-xl border border-slate-800 bg-slate-950 p-4"
>
  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <div>
      <label for="provider-instance-name" class="mb-1 block text-caption font-semibold text-slate-400">
        Name <span class="text-rose-400">*</span>
      </label>
      <input
        id="provider-instance-name"
        type="text"
        required
        bind:value={name}
        placeholder="local, hosted-1, hosted-2..."
        class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
      />
    </div>
    <div>
      <label for="provider-instance-kind" class="mb-1 block text-caption font-semibold text-slate-400">
        Kind
      </label>
      <select
        id="provider-instance-kind"
        bind:value={kind}
        class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
      >
        {#each kinds as kindOption (kindOption.kind)}
          <option value={kindOption.kind}>{kindOption.display_name}</option>
        {/each}
      </select>
      {#if selectedKindInfo?.description}
        <p class="mt-1 text-caption text-slate-500">{selectedKindInfo.description}</p>
      {/if}
    </div>
  </div>

  <div>
    <label for="provider-instance-url" class="mb-1 block text-caption font-semibold text-slate-400">
      {urlLabel} {#if urlRequired}<span class="text-rose-400">*</span>{/if}
    </label>
    <input
      id="provider-instance-url"
      type="text"
      required={urlRequired}
      bind:value={url}
      placeholder={selectedKindInfo?.url_placeholder || "https://..."}
      class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
    />
  </div>

  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <div>
      <label for="provider-instance-key" class="mb-1 block text-caption font-semibold text-slate-400">
        API Key{selectedKindInfo?.requires_api_key ? "" : " (not required)"}
      </label>
      <SecretInput
        id="provider-instance-key"
        bind:value={apiKey}
        placeholder={selectedKindInfo?.requires_api_key ? "sk-..." : "(optional)"}
      />
    </div>
    {#if extraFields}{@render extraFields(selectedKindInfo)}{/if}
  </div>

  <div>
    <label for="provider-instance-notes" class="mb-1 block text-caption font-semibold text-slate-400"
      >Notes (Optional)</label
    >
    <input
      id="provider-instance-notes"
      type="text"
      bind:value={notes}
      placeholder="e.g. EU region hosted account"
      class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
    />
  </div>

  <div class="flex items-center justify-end gap-2 pt-2">
    <button
      type="button"
      onclick={onCancel}
      class="rounded-xl border border-slate-800 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:text-slate-50"
    >
      Cancel
    </button>
    <button
      type="submit"
      disabled={submitting}
      class="flex items-center gap-1.5 rounded-xl bg-accent px-4 py-1.5 text-xs font-semibold text-white transition-all hover:bg-accent-hover disabled:opacity-50"
    >
      {#if submitting}
        <Loader2 class="h-3.5 w-3.5 animate-spin" />
        <span>Saving...</span>
      {:else}
        <span>{submitLabel}</span>
      {/if}
    </button>
  </div>
</form>
