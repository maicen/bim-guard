<script lang="ts">
  import { CheckCircle2, XCircle } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  export interface ComparisonRow {
    feature: string;
    note?: string;
    manual: boolean | string;
    desktop: boolean | string;
    bimguard: boolean | string;
  }

  interface Props {
    items: ComparisonRow[];
    class?: string;
  }

  let { items = [], class: className }: Props = $props();
</script>

<div class={cn("overflow-x-auto rounded-3xl border border-border-default bg-surface-card shadow-sm", className)}>
  <table class="w-full text-left text-xs border-collapse">
    <thead>
      <tr class="border-b border-border-default bg-surface-overlay/60">
        <th scope="col" class="p-4 sm:p-5 font-bold text-fg-primary">Feature & Workflow Capability</th>
        <th scope="col" class="p-4 sm:p-5 font-semibold text-fg-muted text-center w-36">Manual PDF Audits</th>
        <th scope="col" class="p-4 sm:p-5 font-semibold text-fg-muted text-center w-48">Desktop Checkers (Solibri/Navisworks)</th>
        <th scope="col" class="p-4 sm:p-5 font-bold text-accent text-center w-44 bg-surface-selected">BIM-Guard Cloud</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-border-subtle">
      {#each items as row}
        <tr class="hover:bg-surface-hover/50 transition-colors">
          <td class="p-4 sm:p-5">
            <span class="font-bold text-fg-primary block">{row.feature}</span>
            {#if row.note}
              <span class="text-micro text-fg-muted mt-0.5 block">{row.note}</span>
            {/if}
          </td>
          <td class="p-4 sm:p-5 text-center">
            {#if row.manual === false}
              <XCircle class="h-4 w-4 text-fg-muted mx-auto opacity-50" />
            {:else if row.manual === true}
              <CheckCircle2 class="h-4 w-4 text-success mx-auto" />
            {:else}
              <span class="text-fg-muted font-medium">{row.manual}</span>
            {/if}
          </td>
          <td class="p-4 sm:p-5 text-center">
            {#if row.desktop === false}
              <XCircle class="h-4 w-4 text-fg-muted mx-auto opacity-50" />
            {:else if row.desktop === true}
              <CheckCircle2 class="h-4 w-4 text-success mx-auto" />
            {:else}
              <span class="text-fg-secondary font-medium">{row.desktop}</span>
            {/if}
          </td>
          <td class="p-4 sm:p-5 text-center bg-surface-selected/40">
            {#if row.bimguard === true}
              <CheckCircle2 class="h-4 w-4 text-accent mx-auto" />
            {:else}
              <span class="text-accent font-bold">{row.bimguard}</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
