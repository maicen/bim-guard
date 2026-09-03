<script lang="ts">
  import type { Attachment } from "svelte/attachments";

  let {
    checked = $bindable(false),
    indeterminate = false,
    disabled = false,
    title = "",
    ariaLabel = "Select row",
    onchange,
  }: {
    checked?: boolean;
    indeterminate?: boolean;
    disabled?: boolean;
    title?: string;
    ariaLabel?: string;
    /** Fires after the box is toggled. */
    onchange?: (event: Event) => void;
  } = $props();

  // `indeterminate` has no HTML attribute, so it has to be set on the element.
  const trackIndeterminate: Attachment<HTMLInputElement> = (node) => {
    node.indeterminate = indeterminate;
  };
</script>

<input
  type="checkbox"
  bind:checked
  {disabled}
  {title}
  aria-label={ariaLabel}
  onchange={(event) => onchange?.(event)}
  {@attach trackIndeterminate}
  class="h-4 w-4 cursor-pointer rounded border-slate-700 bg-slate-950 text-accent transition-all focus:ring-accent disabled:cursor-not-allowed disabled:opacity-40"
/>
