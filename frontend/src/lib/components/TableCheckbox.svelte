<script lang="ts">
  import Checkbox from "./ui/Checkbox.svelte";

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

  function handleCheckedChange(val: boolean | "indeterminate") {
    if (val === "indeterminate") {
      checked = false;
    } else {
      checked = val;
    }
    onchange?.(new Event("change"));
  }
</script>

<span {title} class="inline-flex items-center">
  <Checkbox
    bind:checked
    bind:indeterminate
    {disabled}
    {ariaLabel}
    onCheckedChange={() => onchange?.(new Event("change"))}
  />
</span>
