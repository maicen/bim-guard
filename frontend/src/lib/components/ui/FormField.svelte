<script lang="ts">
  import type { Snippet } from "svelte";
  import { AlertCircle } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    label?: string;
    htmlFor?: string;
    required?: boolean;
    hint?: string;
    error?: string | null;
    class?: string;
    children?: Snippet;
  }

  let {
    label,
    htmlFor,
    required = false,
    hint,
    error,
    class: className,
    children,
  }: Props = $props();
</script>

<div class={cn("flex flex-col gap-1.5", className)}>
  {#if label}
    <div class="flex items-center justify-between">
      <label for={htmlFor} class="text-caption font-semibold text-fg-secondary">
        {label}
        {#if required}
          <span class="text-critical ml-0.5" aria-hidden="true">*</span>
        {/if}
      </label>
      {#if hint}
        <span class="text-nano text-fg-muted">{hint}</span>
      {/if}
    </div>
  {/if}

  {@render children?.()}

  {#if error}
    <p class="flex items-center gap-1 text-nano font-medium text-critical" role="alert">
      <AlertCircle class="h-3 w-3 shrink-0" />
      <span>{error}</span>
    </p>
  {/if}
</div>
