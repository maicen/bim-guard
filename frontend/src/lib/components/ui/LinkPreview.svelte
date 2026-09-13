<script lang="ts" module>
  import { LinkPreview as LinkPreviewPrimitive } from "bits-ui";

  export const LinkPreviewRoot = LinkPreviewPrimitive.Root;
  export const LinkPreviewTrigger = LinkPreviewPrimitive.Trigger;
  export const LinkPreviewPortal = LinkPreviewPrimitive.Portal;
  export const LinkPreviewContent = LinkPreviewPrimitive.Content;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { ExternalLink } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    href: string;
    label?: string;
    previewTitle?: string;
    previewDescription?: string;
    previewImage?: string;
    class?: string;
    children?: Snippet;
  }

  let {
    href,
    label = "",
    previewTitle = "",
    previewDescription = "",
    previewImage = "",
    class: className,
    children,
  }: Props = $props();
</script>

<LinkPreviewPrimitive.Root>
  <LinkPreviewPrimitive.Trigger
    {href}
    target="_blank"
    rel="noopener noreferrer"
    class={cn(
      "inline-flex items-center gap-1 font-medium text-accent underline underline-offset-2 transition-colors hover:text-accent-hover",
      className,
    )}
  >
    {#if children}
      {@render children()}
    {:else}
      <span>{label || href}</span>
      <ExternalLink class="h-3 w-3 shrink-0 opacity-70" />
    {/if}
  </LinkPreviewPrimitive.Trigger>

  <LinkPreviewPrimitive.Portal>
    <LinkPreviewPrimitive.Content
      class="z-50 w-72 overflow-hidden rounded-2xl border border-border-default bg-surface-card p-3 shadow-2xl duration-150 animate-in fade-in zoom-in-95"
      sideOffset={8}
    >
      {#if previewImage}
        <img
          src={previewImage}
          alt=""
          class="mb-2 h-32 w-full rounded-xl object-cover border border-border-subtle"
        />
      {/if}
      {#if previewTitle}
        <h5 class="text-xs font-bold text-fg-primary line-clamp-1">{previewTitle}</h5>
      {/if}
      {#if previewDescription}
        <p class="mt-1 text-nano text-fg-muted line-clamp-2 leading-relaxed">
          {previewDescription}
        </p>
      {/if}
      <span class="mt-2 block truncate text-[10px] text-accent/80">{href}</span>
    </LinkPreviewPrimitive.Content>
  </LinkPreviewPrimitive.Portal>
</LinkPreviewPrimitive.Root>
