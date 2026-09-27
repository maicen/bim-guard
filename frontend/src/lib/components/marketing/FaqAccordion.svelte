<script lang="ts">
  import { ChevronDown } from "lucide-svelte";
  import {
    AccordionRoot,
    AccordionItem,
    AccordionHeader,
    AccordionTrigger,
    AccordionContent,
  } from "../ui/Accordion.svelte";
  import { cn } from "../../utils/cn";

  export interface FaqItem {
    id: string;
    question: string;
    answer: string;
  }

  interface Props {
    items: FaqItem[];
    type?: "single" | "multiple";
    class?: string;
  }

  let { items = [], type = "single", class: className }: Props = $props();
</script>

<div class={cn("w-full", className)}>
  <AccordionRoot {type} class="rounded-2xl border border-border-default bg-surface-card p-2 divide-y divide-border-subtle">
    {#each items as item}
      <AccordionItem value={item.id} class="border-none py-1">
        <AccordionHeader>
          <AccordionTrigger class="flex w-full items-center justify-between px-4 py-3.5 text-left text-sm font-bold text-fg-primary hover:text-accent transition-colors group">
            <span>{item.question}</span>
            <ChevronDown class="h-4 w-4 shrink-0 text-fg-muted transition-transform duration-200 group-data-[state=open]:rotate-180" />
          </AccordionTrigger>
        </AccordionHeader>
        <AccordionContent class="px-4 pb-4 pt-1 text-xs leading-relaxed text-fg-secondary">
          {item.answer}
        </AccordionContent>
      </AccordionItem>
    {/each}
  </AccordionRoot>
</div>
