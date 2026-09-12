<script lang="ts">
  import { Switch as SwitchPrimitive } from "bits-ui";
  import { cn } from "../../utils/cn";

  interface Props {
    checked?: boolean;
    disabled?: boolean;
    id?: string;
    name?: string;
    value?: string;
    class?: string;
    ariaLabel?: string;
    onCheckedChange?: (checked: boolean) => void;
  }

  let {
    checked = $bindable(false),
    disabled = false,
    id,
    name,
    value,
    class: className,
    ariaLabel,
    onCheckedChange,
  }: Props = $props();
</script>

<SwitchPrimitive.Root
  {id}
  {name}
  {value}
  bind:checked
  {onCheckedChange}
  {disabled}
  aria-label={ariaLabel}
  class={cn(
    "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border border-border-interactive bg-surface-overlay p-0.5 transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-40 data-[state=checked]:bg-accent data-[state=checked]:border-accent",
    className,
  )}
>
  <SwitchPrimitive.Thumb
    class="pointer-events-none block h-3.5 w-3.5 rounded-full bg-white shadow-xs transition-transform duration-200 data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0"
  />
</SwitchPrimitive.Root>
