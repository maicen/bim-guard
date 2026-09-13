<script lang="ts" module>
  import { Toggle as TogglePrimitive } from "bits-ui";

  export const ToggleRoot = TogglePrimitive.Root;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    pressed?: boolean;
    onPressedChange?: (pressed: boolean) => void;
    disabled?: boolean;
    size?: "sm" | "md" | "lg";
    variant?: "default" | "outline";
    class?: string;
    children?: Snippet;
  }

  let {
    pressed = $bindable(false),
    onPressedChange,
    disabled = false,
    size = "md",
    variant = "default",
    class: className,
    children,
  }: Props = $props();

  const sizeClasses = {
    sm: "h-7 px-2 text-micro gap-1 rounded-lg",
    md: "h-8.5 px-3 text-caption gap-1.5 rounded-xl",
    lg: "h-10 px-4 text-xs gap-2 rounded-xl",
  };

  const variantClasses = {
    default: "bg-surface-canvas border border-border-default hover:bg-surface-hover data-[state=on]:bg-accent data-[state=on]:text-white data-[state=on]:border-accent",
    outline: "border border-border-default bg-transparent hover:bg-surface-hover data-[state=on]:bg-surface-selected data-[state=on]:border-accent data-[state=on]:text-accent",
  };
</script>

<TogglePrimitive.Root
  bind:pressed
  {onPressedChange}
  {disabled}
  class={cn(
    "inline-flex items-center justify-center font-medium text-fg-secondary transition-colors focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer select-none",
    sizeClasses[size],
    variantClasses[variant],
    className,
  )}
>
  {@render children?.()}
</TogglePrimitive.Root>
