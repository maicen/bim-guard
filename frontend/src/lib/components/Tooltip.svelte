<!--
  Tooltip — small hover/focus label for a control whose purpose isn't fully
  conveyed by its own text or icon. Built on bits-ui's `Tooltip` primitive
  (Floating UI positioning, Escape/outside dismissal, keyboard-focus support),
  styled to match the BIM-Guard slate token palette — the same wrapper
  convention `HoverCard.svelte` uses for `Popover`.

  Usage:

      <Tooltip text="Toggle grid visibility">
        {#snippet trigger()}
          <button type="button" class="rbn-btn">...</button>
        {/snippet}
      </Tooltip>

  The `trigger` snippet is the real control (already interactive on its own —
  this just adds a `span` around it to host bits-ui's hover/focus handlers).
  Pass `disabled` to skip rendering the tooltip machinery entirely for a
  control with nothing worth adding.
-->
<script lang="ts">
  import type { Snippet } from "svelte";
  import { Tooltip as TooltipPrimitive } from "bits-ui";

  type Side = "top" | "bottom" | "left" | "right";
  type Align = "start" | "center" | "end";

  interface Props {
    /** Tooltip text. Omit (or pass empty) when nothing's worth showing. */
    text?: string;
    /** Preferred side of the trigger to render on. Flips when space is tight. */
    side?: Side;
    /** Alignment along the trigger's cross axis. */
    align?: Align;
    /** Gap in px between trigger and tooltip. */
    sideOffset?: number;
    /** Suppress the tooltip entirely, rendering just the trigger. */
    disabled?: boolean;
    /** Extra classes on the inline trigger wrapper. */
    triggerClass?: string;
    trigger?: Snippet;
  }

  let {
    text = "",
    side = "top",
    align = "center",
    sideOffset = 6,
    disabled = false,
    triggerClass = "",
    trigger,
  }: Props = $props();
</script>

{#if disabled || !text}
  {@render trigger?.()}
{:else}
  <TooltipPrimitive.Root>
    <TooltipPrimitive.Trigger>
      {#snippet child({ props })}
        <span {...props} class="inline-flex {triggerClass}">
          {@render trigger?.()}
        </span>
      {/snippet}
    </TooltipPrimitive.Trigger>

    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        {side}
        {align}
        {sideOffset}
        class="z-70 max-w-[240px] rounded-lg border border-border-default bg-surface-card/95 px-2.5 py-1.5 text-micro font-medium leading-snug text-fg-secondary shadow-xl shadow-black/40 backdrop-blur-md outline-hidden origin-(--bits-tooltip-content-transform-origin) duration-150 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0"
      >
        <TooltipPrimitive.Arrow
          width={7}
          height={7}
          class="rotate-45 border-border-default bg-surface-card data-[side=top]:border-b data-[side=top]:border-r data-[side=bottom]:border-l data-[side=bottom]:border-t data-[side=left]:border-r data-[side=left]:border-t data-[side=right]:border-b data-[side=right]:border-l"
        />
        {text}
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  </TooltipPrimitive.Root>
{/if}
