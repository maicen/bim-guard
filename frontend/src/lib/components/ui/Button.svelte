<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLButtonAttributes } from "svelte/elements";
  import { cn } from "../../utils/cn";

  export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "destructive";
  export type ButtonSize = "xs" | "sm" | "md" | "lg" | "icon";

  interface Props extends HTMLButtonAttributes {
    variant?: ButtonVariant;
    size?: ButtonSize;
    loading?: boolean;
    disabled?: boolean;
    children?: Snippet;
  }

  let {
    variant = "secondary",
    size = "md",
    loading = false,
    disabled = false,
    type = "button",
    class: className,
    children,
    ...rest
  }: Props = $props();

  const variantStyles: Record<ButtonVariant, string> = {
    primary: "bg-accent text-white hover:bg-accent-hover shadow-xs active:scale-[0.98]",
    secondary:
      "bg-surface-card border border-border-default text-fg-primary hover:bg-surface-hover hover:border-border-interactive active:scale-[0.98]",
    outline:
      "border border-border-default bg-transparent text-fg-secondary hover:bg-surface-hover hover:text-fg-primary active:scale-[0.98]",
    ghost: "bg-transparent text-fg-secondary hover:bg-surface-hover hover:text-fg-primary active:scale-[0.98]",
    destructive: "bg-rose-600 text-white hover:bg-rose-700 shadow-xs active:scale-[0.98]",
  };

  const sizeStyles: Record<ButtonSize, string> = {
    xs: "h-6 px-2 py-0.5 text-nano rounded-md gap-1 font-medium",
    sm: "h-7.5 px-2.5 py-1 text-micro rounded-lg gap-1.5 font-medium",
    md: "h-9 px-3.5 py-2 text-caption rounded-xl gap-2 font-semibold",
    lg: "h-10 px-4 py-2.5 text-xs rounded-xl gap-2 font-semibold",
    icon: "h-8 w-8 p-0 rounded-lg flex items-center justify-center shrink-0",
  };
</script>

<button
  {type}
  disabled={disabled || loading}
  class={cn(
    "inline-flex items-center justify-center transition-all duration-150 select-none cursor-pointer focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:pointer-events-none",
    variantStyles[variant],
    sizeStyles[size],
    className,
  )}
  {...rest}
>
  {#if loading}
    <span
      class="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
      aria-hidden="true"
    ></span>
  {/if}
  {@render children?.()}
</button>
