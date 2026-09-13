<script lang="ts" module>
  import { RatingGroup as RatingGroupPrimitive } from "bits-ui";

  export const RatingGroupRoot = RatingGroupPrimitive.Root;
  export const RatingGroupItem = RatingGroupPrimitive.Item;
</script>

<script lang="ts">
  import { Star } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    value?: number;
    max?: number;
    disabled?: boolean;
    class?: string;
    onValueChange?: (val: number) => void;
  }

  let {
    value = $bindable(0),
    max = 5,
    disabled = false,
    class: className,
    onValueChange,
  }: Props = $props();

  const items = $derived(Array.from({ length: max }, (_, i) => i + 1));
</script>

<RatingGroupPrimitive.Root
  bind:value
  {max}
  {disabled}
  {onValueChange}
  class={cn("inline-flex items-center gap-1", className)}
>
  {#each items as item (item)}
    <RatingGroupPrimitive.Item
      index={item}
      class="group rounded p-0.5 text-border-interactive transition-colors hover:text-amber-400 focus-visible:outline-2 focus-visible:outline-accent data-[state=checked]:text-amber-400 disabled:cursor-not-allowed disabled:opacity-40"
    >
      <Star class="h-4 w-4 fill-current transition-transform group-hover:scale-110" />
    </RatingGroupPrimitive.Item>
  {/each}
</RatingGroupPrimitive.Root>
