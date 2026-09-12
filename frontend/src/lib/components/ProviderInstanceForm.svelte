<script lang="ts">
  import type { Snippet } from "svelte";
  import { Loader2, PlugZap, CheckCircle2, AlertCircle, Info } from "lucide-svelte";
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
    /** Optional connectivity test callback before saving */
    onTest?: () => void;
    testing?: boolean;
    testResult?: { ok: boolean; detail: string } | null;
    /** If true, the submit button is disabled until testResult is ok */
    requireSuccessfulTest?: boolean;
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
    onTest,
    testing = false,
    testResult = null,
    requireSuccessfulTest = false,
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
  class="space-y-3 rounded-xl border border-border-default bg-surface-canvas p-4"
>
  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <div>
      <label for="provider-instance-name" class="mb-1 block text-caption font-semibold text-fg-muted">
        Name <span class="text-rose-400">*</span>
      </label>
      <input
        id="provider-instance-name"
        type="text"
        required
        bind:value={name}
        placeholder="local, hosted-1, hosted-2..."
        class="w-full rounded-xl border border-border-default bg-surface-card px-3 py-2 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
      />
    </div>
    <div>
      <label for="provider-instance-kind" class="mb-1 block text-caption font-semibold text-fg-muted">
        Kind
      </label>
      <select
        id="provider-instance-kind"
        bind:value={kind}
        class="w-full rounded-xl border border-border-default bg-surface-card px-3 py-2 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
      >
        {#each kinds as kindOption (kindOption.kind)}
          <option value={kindOption.kind}>{kindOption.display_name}</option>
        {/each}
      </select>
      {#if selectedKindInfo?.description}
        <p class="mt-1 text-caption text-fg-muted">{selectedKindInfo.description}</p>
      {/if}
    </div>
  </div>

  <div>
    <label for="provider-instance-url" class="mb-1 block text-caption font-semibold text-fg-muted">
      {urlLabel} {#if urlRequired}<span class="text-rose-400">*</span>{/if}
    </label>
    <input
      id="provider-instance-url"
      type="text"
      required={urlRequired}
      bind:value={url}
      placeholder={selectedKindInfo?.url_placeholder || "https://..."}
      class="w-full rounded-xl border border-border-default bg-surface-card px-3 py-2 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
    />
  </div>

  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <div>
      <label for="provider-instance-key" class="mb-1 block text-caption font-semibold text-fg-muted">
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
    <label for="provider-instance-notes" class="mb-1 block text-caption font-semibold text-fg-muted"
      >Notes (Optional)</label
    >
    <input
      id="provider-instance-notes"
      type="text"
      bind:value={notes}
      placeholder="e.g. EU region hosted account"
      class="w-full rounded-xl border border-border-default bg-surface-card px-3 py-2 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
    />
  </div>

  {#if testResult}
    <div
      class="flex items-start gap-2.5 rounded-xl border p-3 text-xs {testResult.ok
        ? 'border-emerald-800/80 bg-emerald-950/40 text-emerald-300'
        : 'border-rose-800/80 bg-rose-950/40 text-rose-300'}"
    >
      {#if testResult.ok}
        <CheckCircle2 class="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
      {:else}
        <AlertCircle class="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
      {/if}
      <div class="space-y-0.5">
        <p class="font-semibold">{testResult.ok ? "Connection Successful" : "Connection Failed"}</p>
        <p class="text-caption opacity-90">{testResult.detail}</p>
      </div>
    </div>
  {:else if requireSuccessfulTest}
    <div class="flex items-center gap-2 rounded-xl border border-border-default bg-surface-card/40 px-3 py-2 text-caption text-fg-muted">
      <Info class="h-3.5 w-3.5 shrink-0 text-fg-muted" />
      <span>Test the connection to enable adding this provider.</span>
    </div>
  {/if}

  <div class="flex items-center justify-between gap-2 pt-2">
    <div>
      {#if onTest}
        <button
          type="button"
          onclick={onTest}
          disabled={testing || submitting}
          class="flex items-center gap-1.5 rounded-xl border border-border-interactive bg-surface-overlay px-3 py-1.5 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-white disabled:opacity-50"
        >
          {#if testing}
            <Loader2 class="h-3.5 w-3.5 animate-spin text-accent" />
            <span>Testing connection...</span>
          {:else}
            <PlugZap class="h-3.5 w-3.5 text-accent" />
            <span>Test Connection</span>
          {/if}
        </button>
      {/if}
    </div>

    <div class="flex items-center gap-2">
      <button
        type="button"
        onclick={onCancel}
        class="rounded-xl border border-border-default px-3 py-1.5 text-xs text-fg-muted transition-colors hover:text-fg-primary"
      >
        Cancel
      </button>
      <button
        type="submit"
        disabled={submitting || (requireSuccessfulTest && !testResult?.ok)}
        title={requireSuccessfulTest && !testResult?.ok ? "A successful connection test is required before adding" : undefined}
        class="flex items-center gap-1.5 rounded-xl bg-accent px-4 py-1.5 text-xs font-semibold text-white transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        {#if submitting}
          <Loader2 class="h-3.5 w-3.5 animate-spin" />
          <span>Saving...</span>
        {:else}
          <span>{submitLabel}</span>
        {/if}
      </button>
    </div>
  </div>
</form>
