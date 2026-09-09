<script lang="ts">
  import { Loader2, Star } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { llmProvidersApi } from "../api";
  import { formatModelMeta } from "../utils/formatModelMeta";
  import type { LLMProviderInstance, LLMTask, LLMTaskModelAssignment, LLMProviderModel } from "../types";

  interface Props {
    task: LLMTask;
    organizationId: number;
    /** Enabled LLM provider instances for this org — models are merged across all of them. */
    instances: LLMProviderInstance[];
    /** This task's current shortlist, used to pre-select checkboxes/default. */
    currentAssignments: LLMTaskModelAssignment[];
    onClose: () => void;
    onSaved: (assignments: LLMTaskModelAssignment[]) => void;
  }

  let { task, organizationId, instances, currentAssignments, onClose, onSaved }: Props = $props();

  interface MergedModel extends LLMProviderModel {
    instanceId: number;
    instanceName: string;
  }

  function rowKey(instanceId: number, modelId: string): string {
    return `${instanceId}:${modelId}`;
  }

  let loading = $state(true);
  let loadError = $state("");
  let modelsByInstance = $state<Record<number, LLMProviderModel[]>>({});
  let selected = $state<Set<string>>(new Set());
  let defaultKey = $state<string | null>(null);
  let saving = $state(false);
  let saveError = $state("");
  let filter = $state("");

  $effect(() => {
    // Seed selection/default from the task's current shortlist once, on open.
    const initialSelected = new Set<string>();
    let initialDefault: string | null = null;
    for (const a of currentAssignments) {
      const key = rowKey(a.provider_instance_id, a.model_id);
      initialSelected.add(key);
      if (a.is_default) initialDefault = key;
    }
    selected = initialSelected;
    defaultKey = initialDefault;
  });

  $effect(() => {
    loading = true;
    loadError = "";
    Promise.all(
      instances.map(async (instance) => {
        try {
          const models = await llmProvidersApi.models(organizationId, instance.id);
          return [instance.id, models] as const;
        } catch {
          return [instance.id, []] as const;
        }
      }),
    )
      .then((entries) => {
        modelsByInstance = Object.fromEntries(entries);
        if (entries.every(([, models]) => models.length === 0) && instances.length > 0) {
          loadError = "Could not load models from any enabled provider instance.";
        }
      })
      .finally(() => {
        loading = false;
      });
  });

  let merged: MergedModel[] = $derived(
    instances.flatMap((instance) =>
      (modelsByInstance[instance.id] ?? []).map((model) => ({
        ...model,
        instanceId: instance.id,
        instanceName: instance.name,
      })),
    ),
  );

  let filtered: MergedModel[] = $derived(
    (() => {
      const q = filter.trim().toLowerCase();
      if (!q) return merged;
      return merged.filter(
        (m) => m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q),
      );
    })(),
  );

  function toggle(model: MergedModel) {
    const key = rowKey(model.instanceId, model.id);
    const next = new Set(selected);
    if (next.has(key)) {
      next.delete(key);
      if (defaultKey === key) defaultKey = null;
    } else {
      next.add(key);
      if (!defaultKey) defaultKey = key;
    }
    selected = next;
  }

  function setDefault(model: MergedModel) {
    const key = rowKey(model.instanceId, model.id);
    if (!selected.has(key)) return;
    defaultKey = key;
  }

  async function handleSave() {
    saving = true;
    saveError = "";
    const chosen = merged.filter((m) => selected.has(rowKey(m.instanceId, m.id)));
    const defaultModel = chosen.find((m) => rowKey(m.instanceId, m.id) === defaultKey) ?? null;
    try {
      const result = await llmProvidersApi.setTaskAssignments(organizationId, task.key, {
        models: chosen.map((m) => ({
          provider_instance_id: m.instanceId,
          model_id: m.id,
          model_name: m.name,
          context_length: m.context_length,
          input_price_per_million: m.input_price_per_million,
          output_price_per_million: m.output_price_per_million,
        })),
        default_provider_instance_id: defaultModel?.instanceId ?? null,
        default_model_id: defaultModel?.id ?? null,
      });
      onSaved(result);
    } catch (err: any) {
      saveError = err.message || "Could not save this shortlist.";
    } finally {
      saving = false;
    }
  }
</script>

<Modal isOpen={true} title={`Shortlist models — ${task.label}`} subtitle={task.description} maxWidth="max-w-2xl" {onClose}>
  {#snippet children()}
    <div class="space-y-3">
      <input
        type="search"
        bind:value={filter}
        placeholder="Filter models…"
        class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
      />

      {#if saveError}
        <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300">
          {saveError}
        </div>
      {/if}

      {#if instances.length === 0}
        <p class="text-xs text-slate-500">
          No enabled LLM provider instances for this organization — add one first.
        </p>
      {:else if loading}
        <div class="flex items-center gap-2 p-6 text-xs text-slate-400">
          <Loader2 class="h-4 w-4 animate-spin" />
          <span>Loading models from {instances.length} provider instance{instances.length === 1 ? "" : "s"}…</span>
        </div>
      {:else if loadError}
        <p class="text-xs text-rose-400">{loadError}</p>
      {:else}
        <div class="max-h-96 space-y-1 overflow-y-auto pr-1">
          {#each filtered as model (rowKey(model.instanceId, model.id))}
            {@const key = rowKey(model.instanceId, model.id)}
            {@const isSelected = selected.has(key)}
            <div
              class="flex items-start gap-2.5 rounded-lg px-2.5 py-2 text-xs transition-colors {isSelected
                ? 'bg-accent/10'
                : 'hover:bg-slate-800'}"
            >
              <input
                type="checkbox"
                checked={isSelected}
                onchange={() => toggle(model)}
                class="mt-0.5 h-3.5 w-3.5 shrink-0 rounded border-slate-600 bg-slate-950 text-accent focus:ring-1 focus:ring-blue-500"
              />
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-1.5">
                  <span class="truncate font-semibold text-slate-100">{model.name}</span>
                  <span class="rounded-md border border-slate-800 bg-slate-900 px-1.5 py-0.5 text-micro text-slate-500"
                    >{model.instanceName}</span
                  >
                </div>
                <div class="text-caption text-slate-500">{formatModelMeta(model)}</div>
              </div>
              <button
                type="button"
                onclick={() => setDefault(model)}
                disabled={!isSelected}
                title={isSelected ? "Make default for this task" : "Select this model first"}
                class="shrink-0 rounded-md p-1 transition-colors disabled:opacity-30 {defaultKey === key
                  ? 'text-amber-400'
                  : 'text-slate-600 hover:text-slate-300'}"
              >
                <Star class="h-3.5 w-3.5" fill={defaultKey === key ? "currentColor" : "none"} />
              </button>
            </div>
          {:else}
            <p class="p-4 text-center text-xs text-slate-500">No models match "{filter}".</p>
          {/each}
        </div>
      {/if}
    </div>
  {/snippet}
  {#snippet footer()}
    <div class="flex w-full items-center justify-between gap-2">
      <span class="text-caption text-slate-500">{selected.size} model{selected.size === 1 ? "" : "s"} shortlisted</span>
      <div class="flex gap-2">
        <button
          type="button"
          onclick={onClose}
          class="rounded-xl border border-slate-800 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:text-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onclick={handleSave}
          disabled={saving}
          class="flex items-center gap-1.5 rounded-xl bg-accent px-4 py-1.5 text-xs font-semibold text-white transition-all hover:bg-accent-hover disabled:opacity-50"
        >
          {#if saving}
            <Loader2 class="h-3.5 w-3.5 animate-spin" />
          {/if}
          <span>{saving ? "Saving…" : "Save Shortlist"}</span>
        </button>
      </div>
    </div>
  {/snippet}
</Modal>
