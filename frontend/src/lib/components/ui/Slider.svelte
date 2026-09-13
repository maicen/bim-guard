<script lang="ts" module>
  import { Slider as SliderPrimitive } from "bits-ui";

  export const SliderRoot = SliderPrimitive.Root;
  export const SliderRange = SliderPrimitive.Range;
  export const SliderThumb = SliderPrimitive.Thumb;
  export const SliderTick = SliderPrimitive.Tick;
</script>

<script lang="ts">
  import { cn } from "../../utils/cn";

  interface Props {
    value?: number | number[];
    min?: number;
    max?: number;
    step?: number;
    disabled?: boolean;
    orientation?: "horizontal" | "vertical";
    class?: string;
    onValueChange?: (val: any) => void;
  }

  let {
    value = $bindable(0),
    min = 0,
    max = 100,
    step = 1,
    disabled = false,
    orientation = "horizontal",
    class: className,
    onValueChange,
  }: Props = $props();

  let isSingle = $derived(typeof value === "number");
  let arrayValue = $derived(typeof value === "number" ? [value] : (value ?? [0]));

  function handleValueChange(arr: number[]) {
    if (isSingle) {
      value = arr[0] ?? min;
      onValueChange?.(arr[0] ?? min);
    } else {
      value = arr;
      onValueChange?.(arr);
    }
  }
</script>

<SliderPrimitive.Root
  type="multiple"
  value={arrayValue}
  onValueChange={handleValueChange}
  {min}
  {max}
  {step}
  {disabled}
  {orientation}
  class={cn(
    "relative flex touch-none select-none items-center",
    orientation === "horizontal" ? "h-5 w-full" : "h-full w-5 flex-col",
    disabled && "opacity-40 cursor-not-allowed",
    className,
  )}
>
  <span
    class={cn(
      "relative grow overflow-hidden rounded-full bg-surface-overlay",
      orientation === "horizontal" ? "h-1.5 w-full" : "h-full w-1.5",
    )}
  >
    <SliderPrimitive.Range
      class={cn(
        "absolute bg-accent transition-all",
        orientation === "horizontal" ? "h-full" : "w-full",
      )}
    />
  </span>

  {#each arrayValue as _, i (i)}
    <SliderPrimitive.Thumb
      index={i}
      class="block h-4 w-4 rounded-full border-2 border-accent bg-surface-canvas shadow-md transition-colors hover:scale-110 focus-visible:outline-2 focus-visible:outline-accent disabled:pointer-events-none"
    />
  {/each}
</SliderPrimitive.Root>
