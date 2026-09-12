<script lang="ts">
  import { Checkbox as CheckboxPrimitive } from "bits-ui";
  import { Check, Minus } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    checked?: boolean;
    indeterminate?: boolean;
    disabled?: boolean;
    id?: string;
    name?: string;
    value?: string;
    class?: string;
    ariaLabel?: string;
    onCheckedChange?: (checked: boolean) => void;
    onIndeterminateChange?: (indeterminate: boolean) => void;
  }

  let {
    checked = $bindable(false),
    indeterminate = $bindable(false),
    disabled = false,
    id,
    name,
    value,
    class: className,
    ariaLabel,
    onCheckedChange,
    onIndeterminateChange,
  }: Props = $props();
</script>

<CheckboxPrimitive.Root
  {id}
  {name}
  {value}
  bind:checked
  bind:indeterminate
  {onCheckedChange}
  {onIndeterminateChange}
  {disabled}
  aria-label={ariaLabel}
  class={cn(
    "peer inline-flex h-4 w-4 shrink-0 cursor-pointer items-center justify-center rounded border border-border-interactive bg-surface-canvas text-white transition-all duration-150 focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-40 active:scale-[0.96] data-[state=checked]:bg-accent data-[state=checked]:border-accent data-[state=indeterminate]:bg-accent data-[state=indeterminate]:border-accent",
    className,
  )}
>
  {#snippet children({ checked: isChecked, indeterminate: isIndeterminate })}
    {#if isIndeterminate}
      <Minus class="h-3 w-3 stroke-[3]" />
    {:else if isChecked}
      <Check class="h-3 w-3 stroke-[3]" />
    {/if}
  {/snippet}
</CheckboxPrimitive.Root>
