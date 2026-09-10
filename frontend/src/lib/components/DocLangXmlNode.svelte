<!--
  DocLangXmlNode — one element's line(s) in the syntax-highlighted DocLang XML
  tree, recursing into its own children. A recursive component (not a flat
  windowed list, unlike the "rendered" blocks tab) — simpler to get correct,
  and folding deep/uninteresting subtrees by default keeps the actually-
  mounted DOM small for large documents without a separate virtualization pass.

  `<custom>` elements (BIM-Guard's injected element-id carrier, see
  doclang_element_ids.py) are never rendered -- they're internal plumbing,
  not something a user reviewing the document markup needs to see.
-->
<script lang="ts">
  import type { SvelteSet } from "svelte/reactivity";
  import { cursorTooltip } from "../actions/cursorTooltip";
  import Self from "./DocLangXmlNode.svelte";

  interface Props {
    element: Element;
    depth: number;
    collapsed: SvelteSet<Element>;
    selectedElementId: string | null;
    onSelect: (elementId: string) => void;
    /** Depth at/beyond which a foldable node starts collapsed by default. */
    autoCollapseDepth?: number;
  }

  let { element, depth, collapsed, selectedElementId, onSelect, autoCollapseDepth = 2 }: Props = $props();

  function localName(el: Element): string {
    return el.tagName.toLowerCase().split(":").pop() || el.tagName.toLowerCase();
  }

  function attrs(el: Element): { name: string; value: string }[] {
    return Array.from(el.attributes)
      .filter((a) => a.name !== "xmlns")
      .map((a) => ({ name: a.name, value: a.value }));
  }

  function childElements(el: Element): Element[] {
    return Array.from(el.children).filter((c) => localName(c) !== "custom");
  }

  function getInjectedElementId(el: Element): string | null {
    for (const child of Array.from(el.children)) {
      if (localName(child) !== "custom") continue;
      for (const grandchild of Array.from(child.children)) {
        if (localName(grandchild) === "bg_element_id") return grandchild.getAttribute("value");
      }
    }
    return null;
  }

  /** Direct text content only (not descendants') -- distinguishes a leaf text
   * element like <text>Foo</text> from a container whose text lives in children. */
  function directText(el: Element): string {
    let text = "";
    for (const node of Array.from(el.childNodes)) {
      if (node.nodeType === Node.TEXT_NODE || node.nodeType === Node.CDATA_SECTION_NODE) {
        text += node.textContent ?? "";
      }
    }
    return text.trim();
  }

  let tag = $derived(localName(element));
  let elementAttrs = $derived(attrs(element));
  let elementId = $derived(getInjectedElementId(element));
  let children = $derived(childElements(element));
  let leafText = $derived(children.length === 0 ? directText(element) : "");
  let isLeaf = $derived(children.length === 0);
  let foldable = $derived(!isLeaf);

  // Initialize (once per element) whether a foldable node starts collapsed --
  // deep subtrees default closed so a large document's initial tree isn't
  // fully expanded; the user opens what they care about.
  $effect(() => {
    if (foldable && depth >= autoCollapseDepth && !collapsed.has(element)) {
      collapsed.add(element);
    }
  });

  let isCollapsed = $derived(collapsed.has(element));
  let isSelected = $derived(elementId !== null && elementId === selectedElementId);

  function toggleFold(e: MouseEvent) {
    e.stopPropagation();
    if (isCollapsed) collapsed.delete(element);
    else collapsed.add(element);
  }

  function handleSelect() {
    if (elementId) onSelect(elementId);
  }

  let lineEl: HTMLDivElement | undefined = $state();

  // Cross-pane sync: when this node becomes the selected one (from the
  // rendered-blocks view or the bbox overlay, not a click on this line
  // itself), scroll it into view within the XML tree pane.
  $effect(() => {
    if (isSelected) lineEl?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
</script>

{#snippet attrSpans()}
  {#each elementAttrs as attr (attr.name)}
    <span class="text-slate-500"> {attr.name}=</span><span class="text-cyan-300/90">"{attr.value}"</span>
  {/each}
{/snippet}

<div
  bind:this={lineEl}
  class="markup-line flex cursor-pointer items-baseline rounded px-1 leading-relaxed hover:bg-slate-800/50 {isSelected
    ? 'bg-accent/15 ring-1 ring-accent/50'
    : ''}"
  style="padding-left: {depth * 1.1}rem"
  onclick={handleSelect}
  role="presentation"
>
  {#if foldable}
    <button
      type="button"
      onclick={toggleFold}
      use:cursorTooltip={{ text: isCollapsed ? "Expand" : "Collapse" }}
      aria-expanded={!isCollapsed}
      aria-label={isCollapsed ? "Expand element" : "Collapse element"}
      class="mr-1 inline-flex h-4 w-3 shrink-0 items-center justify-center text-slate-500 hover:text-slate-200"
    >
      <span class="inline-block text-[9px] transition-transform {isCollapsed ? '' : 'rotate-90'}">▶</span>
    </button>
  {:else}
    <span class="mr-1 inline-block w-3 shrink-0"></span>
  {/if}

  <span class="font-mono text-xs">
    {#if isLeaf}
      {#if leafText}
        <span class="text-slate-600">&lt;</span><span class="text-violet-300">{tag}</span
        >{@render attrSpans()}<span class="text-slate-600">&gt;</span><span class="text-slate-200"
          >{leafText}</span
        ><span class="text-slate-600">&lt;/</span><span class="text-violet-300">{tag}</span
        ><span class="text-slate-600">&gt;</span>
      {:else}
        <span class="text-slate-600">&lt;</span><span class="text-violet-300">{tag}</span
        >{@render attrSpans()}<span class="text-slate-600">/&gt;</span>
      {/if}
    {:else}
      <span class="text-slate-600">&lt;</span><span class="text-violet-300">{tag}</span
      >{@render attrSpans()}<span class="text-slate-600">&gt;</span>
      {#if isCollapsed}
        <span class="text-slate-600 italic">…&lt;/{tag}&gt;</span>
      {/if}
    {/if}
  </span>
</div>

{#if foldable && !isCollapsed}
  {#each children as child, idx (idx)}
    <Self element={child} depth={depth + 1} {collapsed} {selectedElementId} {onSelect} {autoCollapseDepth} />
  {/each}
  <div class="markup-line flex items-baseline rounded px-1 text-xs text-slate-600" style="padding-left: {depth * 1.1}rem">
    <span class="mr-1 inline-block w-3 shrink-0"></span>
    <span class="font-mono">&lt;/{tag}&gt;</span>
  </div>
{/if}
