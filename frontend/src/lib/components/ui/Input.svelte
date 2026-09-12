<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLInputAttributes } from "svelte/elements";
  import { cn } from "../../utils/cn";

  interface Props extends Omit<HTMLInputAttributes, "prefix"> {
    value?: string | number | null;
    error?: boolean | string;
    prefixIcon?: Snippet;
    suffixIcon?: Snippet;
  }

  let {
    value = $bindable(""),
    error = false,
    type = "text",
    disabled = false,
    readonly = false,
    id,
    placeholder,
    class: className,
    prefixIcon,
    suffixIcon,
    ...rest
  }: Props = $props();

  let hasError = $derived(!!error);
</script>

<div class="relative flex w-full items-center">
  {#if prefixIcon}
    <div
      class="pointer-events-none absolute left-3 flex items-center justify-center text-fg-muted"
    >
      {@render prefixIcon()}
    </div>
  {/if}

  <input
    {id}
    {type}
    {disabled}
    {readonly}
    {placeholder}
    bind:value
    class={cn(
      "w-full rounded-xl border bg-surface-card px-3.5 py-2 text-xs text-fg-primary transition-colors placeholder:text-fg-muted",
      "focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent",
      "disabled:cursor-not-allowed disabled:opacity-40",
      prefixIcon && "pl-9",
      suffixIcon && "pr-9",
      hasError
        ? "border-critical focus:border-critical focus:ring-critical"
        : "border-border-default hover:border-border-interactive",
      className,
    )}
    {...rest}
  />

  {#if suffixIcon}
    <div
      class="pointer-events-none absolute right-3 flex items-center justify-center text-fg-muted"
    >
      {@render suffixIcon()}
    </div>
  {/if}
</div>
