<script lang="ts" module>
  import { Command as CommandPrimitive } from "bits-ui";

  export const CommandRoot = CommandPrimitive.Root;
  export const CommandInput = CommandPrimitive.Input;
  export const CommandList = CommandPrimitive.List;
  export const CommandEmpty = CommandPrimitive.Empty;
  export const CommandGroup = CommandPrimitive.Group;
  export const CommandGroupHeading = CommandPrimitive.GroupHeading;
  export const CommandItem = CommandPrimitive.Item;
  export const CommandSeparator = CommandPrimitive.Separator;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { Search } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    placeholder?: string;
    class?: string;
    children?: Snippet;
  }

  let { placeholder = "Type a command or search…", class: className, children }: Props = $props();
</script>

<CommandPrimitive.Root
  class={cn(
    "flex h-full w-full flex-col overflow-hidden rounded-2xl border border-border-default bg-surface-card text-fg-primary shadow-2xl",
    className,
  )}
>
  <div class="flex items-center border-b border-border-default px-3">
    <Search class="mr-2 h-4 w-4 shrink-0 text-fg-muted" />
    <CommandPrimitive.Input
      {placeholder}
      class="flex h-11 w-full rounded-md bg-transparent py-3 text-xs text-fg-primary outline-hidden placeholder:text-fg-muted disabled:cursor-not-allowed disabled:opacity-50"
    />
  </div>
  <CommandPrimitive.List class="max-h-[300px] overflow-y-auto overflow-x-hidden p-1.5">
    {@render children?.()}
  </CommandPrimitive.List>
</CommandPrimitive.Root>
