<script lang="ts">
  import { ListChecks, Edit3 } from "lucide-svelte";
  import Modal from "../Modal.svelte";
  import type { Rule } from "../../types";

  interface Props {
    isOpen: boolean;
    rule: Rule | null;
    onClose: () => void;
    onEdit?: (rule: Rule) => void;
  }

  let { isOpen = false, rule, onClose, onEdit }: Props = $props();
</script>

<Modal
  {isOpen}
  title={rule?.rule_id || (rule ? `Rule #${rule.id}` : "Rule Specification")}
  subtitle="Rule Specification & Conditions"
  icon={ListChecks}
  maxWidth="max-w-xl"
  {onClose}
>
  {#if rule}
    <div class="space-y-4 text-xs">
      <div>
        <span class="mb-1 block font-semibold text-fg-muted">Description</span>
        <div class="rounded-xl border border-border-default bg-surface-canvas/60 p-3 text-fg-secondary">
          {rule.description || "No description provided."}
        </div>
      </div>

      <div class="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <div class="rounded-xl border border-border-default bg-surface-canvas/40 p-2.5">
          <span class="block text-micro font-semibold uppercase tracking-wider text-fg-muted">
            Category
          </span>
          <span class="font-mono font-semibold text-fg-primary">
            {rule.category || "Arch"}
          </span>
        </div>

        <div class="rounded-xl border border-border-default bg-surface-canvas/40 p-2.5">
          <span class="block text-micro font-semibold uppercase tracking-wider text-fg-muted">
            Mechanism
          </span>
          <span class="font-mono font-semibold text-fg-primary">
            {rule.mechanism || "CODE"}
          </span>
        </div>

        <div class="rounded-xl border border-border-default bg-surface-canvas/40 p-2.5">
          <span class="block text-micro font-semibold uppercase tracking-wider text-fg-muted">
            Severity
          </span>
          <span class="font-semibold text-amber-400">{rule.severity}</span>
        </div>

        <div class="rounded-xl border border-border-default bg-surface-canvas/40 p-2.5">
          <span class="block text-micro font-semibold uppercase tracking-wider text-fg-muted">
            Ruleset / Folder
          </span>
          <span class="block truncate font-mono text-fg-secondary">
            {rule.ruleset_id || "Global"}
          </span>
        </div>
      </div>

      <div class="space-y-2 rounded-xl border border-border-default bg-surface-canvas/70 p-3.5">
        <span class="block text-micro font-semibold uppercase tracking-wider text-fg-muted">
          Target &amp; Condition
        </span>
        <div class="grid grid-cols-2 gap-2 font-mono text-caption">
          <div>
            <span class="text-fg-muted">Pset:</span>
            <span class="text-fg-secondary">{rule.property_set || "Pset_Compliance"}</span>
          </div>
          <div>
            <span class="text-fg-muted">Property:</span>
            <span class="text-fg-secondary">{rule.property_name || "—"}</span>
          </div>
          <div>
            <span class="text-fg-muted">Operator:</span>
            <span class="text-cyan-300">{rule.operator || "=="}</span>
          </div>
          <div>
            <span class="text-fg-muted">Target Value:</span>
            <span class="text-emerald-300">
              {rule.check_value ||
                (rule.value_min ? `[${rule.value_min}..${rule.value_max}]` : "—")}
              {rule.unit || ""}
            </span>
          </div>
        </div>
        {#if rule.compare_property}
          <div class="pt-1 font-mono text-caption text-amber-300">
            Compare with: {rule.compare_property}
          </div>
        {/if}
      </div>

      <div>
        <span class="mb-1 block text-micro font-semibold uppercase tracking-wider text-fg-muted">
          Raw JSON Definition
        </span>
        <pre
          class="max-h-40 overflow-auto rounded-xl border border-border-default bg-surface-canvas p-3 font-mono text-caption text-fg-muted">{JSON.stringify(
            rule,
            null,
            2,
          )}</pre>
      </div>
    </div>
  {/if}

  {#snippet footer()}
    <div class="flex w-full items-center justify-between">
      {#if onEdit && rule}
        <button
          type="button"
          onclick={() => {
            onClose();
            onEdit(rule);
          }}
          class="inline-flex items-center gap-1.5 rounded-xl bg-surface-overlay px-3 py-1.5 text-xs text-fg-primary transition-colors hover:bg-surface-hover"
        >
          <Edit3 class="h-3.5 w-3.5" />
          <span>Edit this Rule</span>
        </button>
      {:else}
        <div></div>
      {/if}

      <button
        type="button"
        onclick={onClose}
        class="rounded-xl bg-surface-overlay px-4 py-2 text-xs font-semibold text-fg-primary transition-colors hover:bg-surface-hover"
      >
        Close
      </button>
    </div>
  {/snippet}
</Modal>
