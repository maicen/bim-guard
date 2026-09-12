import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

const customTwMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["nano", "micro", "caption"] }],
    },
  },
});

/**
 * Compose Tailwind class names, resolving conflicts left-to-right.
 *
 * `clsx` flattens conditionals (arrays, objects, falsy values) and `twMerge`
 * then drops earlier utilities that a later one overrides, so a caller-supplied
 * `class` prop can always win over a component's defaults:
 *
 *     cn("px-3 py-2 bg-surface-card", isActive && "bg-accent", className)
 */
export function cn(...inputs: ClassValue[]): string {
  return customTwMerge(clsx(inputs));
}

