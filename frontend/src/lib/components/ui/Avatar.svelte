<script lang="ts" module>
  import { Avatar as AvatarPrimitive } from "bits-ui";

  export const AvatarRoot = AvatarPrimitive.Root;
  export const AvatarImage = AvatarPrimitive.Image;
  export const AvatarFallback = AvatarPrimitive.Fallback;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    src?: string | null;
    alt?: string;
    fallback?: string;
    size?: "xs" | "sm" | "md" | "lg" | "xl";
    class?: string;
    fallbackSnippet?: Snippet;
  }

  let {
    src = null,
    alt = "",
    fallback = "",
    size = "md",
    class: className,
    fallbackSnippet,
  }: Props = $props();

  const sizeClasses = {
    xs: "h-6 w-6 text-nano",
    sm: "h-7 w-7 text-micro",
    md: "h-8 w-8 text-caption",
    lg: "h-10 w-10 text-xs",
    xl: "h-14 w-14 text-sm",
  };
</script>

<AvatarPrimitive.Root
  class={cn(
    "relative flex shrink-0 overflow-hidden rounded-full border border-border-default bg-surface-overlay font-semibold text-fg-secondary select-none",
    sizeClasses[size],
    className,
  )}
>
  {#if src}
    <AvatarPrimitive.Image
      {src}
      {alt}
      class="aspect-square h-full w-full object-cover"
      referrerpolicy="no-referrer"
    />
  {/if}

  <AvatarPrimitive.Fallback
    class="flex h-full w-full items-center justify-center bg-surface-overlay text-fg-secondary"
  >
    {#if fallbackSnippet}
      {@render fallbackSnippet()}
    {:else}
      {fallback}
    {/if}
  </AvatarPrimitive.Fallback>
</AvatarPrimitive.Root>
