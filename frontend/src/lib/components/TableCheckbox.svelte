<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let checked: boolean = false;
  export let indeterminate: boolean = false;
  export let disabled: boolean = false;
  export let title: string = "";
  export let ariaLabel: string = "Select row";

  const dispatch = createEventDispatcher<{ change: Event }>();

  function handleChange(e: Event) {
    dispatch("change", e);
  }

  function setIndeterminate(node: HTMLInputElement, isIndet: boolean) {
    node.indeterminate = isIndet;
    return {
      update(val: boolean) {
        node.indeterminate = val;
      },
    };
  }
</script>

<input
  type="checkbox"
  bind:checked
  use:setIndeterminate={indeterminate}
  {disabled}
  {title}
  aria-label={ariaLabel}
  on:change={handleChange}
  class="rounded bg-slate-950 border-slate-700 text-[#0071e3] focus:ring-[#0071e3] cursor-pointer w-4 h-4 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
/>
