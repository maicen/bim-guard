<script lang="ts">
  import { PROPERTY_CONFIDENCE_STYLES, UNKNOWN_PROPERTY_CONFIDENCE } from "../propertyConfidence";
  import type { PropertyConfidence } from "../types";
  import { cn } from "../utils/cn";

  interface Props {
    confidence?: PropertyConfidence | null;
  }

  let { confidence = null }: Props = $props();

  let resolved = $derived(confidence ?? UNKNOWN_PROPERTY_CONFIDENCE);
  let style = $derived(PROPERTY_CONFIDENCE_STYLES[resolved.id]);
</script>

<span class="inline-flex items-center gap-1.5" title={resolved.description}>
  <span class="flex items-end gap-0.5" aria-hidden="true">
    {#each [1, 2, 3] as bar (bar)}
      <span
        class={cn(
          "w-1 rounded-sm",
          bar === 1 ? "h-1.5" : bar === 2 ? "h-2.5" : "h-3.5",
          bar <= resolved.meter_level ? style.bar : "bg-surface-overlay",
        )}
      ></span>
    {/each}
  </span>
  <span class={cn("whitespace-nowrap text-micro font-semibold", style.text)}>{resolved.label}</span>
</span>
