<script lang="ts">
  import type { Component, ComponentType, Snippet } from "svelte";
  import { ChevronDown } from "lucide-svelte";
  import { AccordionItem, AccordionHeader, AccordionTrigger, AccordionContent } from "../ui";

  interface Props {
    value: string;
    title: string;
    icon?: Component<any> | ComponentType<any> | null;
    children?: Snippet;
  }

  let { value, title, icon = null, children }: Props = $props();

  const Icon = $derived(icon);
</script>

<AccordionItem {value}>
  <AccordionHeader>
    <AccordionTrigger
      class="group flex h-8 w-full shrink-0 items-center gap-1.5 border-b border-border-subtle bg-surface-overlay px-2.5 text-left text-xs font-semibold tracking-wide text-fg-primary hover:text-accent"
    >
      <ChevronDown
        class="h-3.5 w-3.5 shrink-0 text-fg-muted transition-transform duration-200 group-data-[state=closed]:-rotate-90"
      />
      {#if Icon}
        <Icon class="h-3.5 w-3.5 shrink-0 text-accent" />
      {/if}
      <span class="truncate">{title}</span>
    </AccordionTrigger>
  </AccordionHeader>
  <AccordionContent forceMount class="min-h-0 data-[state=closed]:hidden">
    {@render children?.()}
  </AccordionContent>
</AccordionItem>
