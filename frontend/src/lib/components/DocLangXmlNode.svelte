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

  let { element, depth, collapsed, selectedElementId, onSelect, autoCollapseDepth = 1 }: Props = $props();

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

  // Deep subtrees default closed so a large document's initial tree isn't
  // fully expanded -- the user opens what they care about. This has to be a
  // pure, synchronous derivation (not an $effect that mutates `collapsed` on
  // mount): an $effect only runs *after* the initial render commits, so
  // every descendant -- however deep, however many thousands of OTSL table
  // cells included -- would still get mounted once on first paint before
  // being torn down again. For a large document that one-frame over-mount
  // was enough to freeze the tab. `collapsed` here instead tracks only
  // explicit user toggles, applied as a flip against the depth-based default.
  let defaultCollapsed = $derived(foldable && depth >= autoCollapseDepth);
  let isCollapsed = $derived(defaultCollapsed !== collapsed.has(element));
  let isSelected = $derived(elementId !== null && elementId === selectedElementId);

  function toggleFold(e: MouseEvent) {
    e.stopPropagation();
    if (collapsed.has(element)) collapsed.delete(element);
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
    <span class="text-fg-muted"> {attr.name}=</span><span class="text-cyan-300/90">"{attr.value}"</span>
  {/each}
{/snippet}

<div
  bind:this={lineEl}
  class="markup-line flex cursor-pointer items-baseline rounded px-1 leading-relaxed hover:bg-surface-hover {isSelected
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
      class="mr-1 inline-flex h-4 w-3 shrink-0 items-center justify-center text-fg-muted hover:text-fg-primary"
    >
      <span class="inline-block text-[9px] transition-transform {isCollapsed ? '' : 'rotate-90'}">▶</span>
    </button>
  {:else}
    <span class="mr-1 inline-block w-3 shrink-0"></span>
  {/if}

  <span class="font-mono text-xs">
    {#if isLeaf}
      {#if leafText}
        <span class="text-fg-muted">&lt;</span><span class="text-violet-300">{tag}</span
        >{@render attrSpans()}<span class="text-fg-muted">&gt;</span><span class="text-fg-secondary"
          >{leafText}</span
        ><span class="text-fg-muted">&lt;/</span><span class="text-violet-300">{tag}</span
        ><span class="text-fg-muted">&gt;</span>
      {:else}
        <span class="text-fg-muted">&lt;</span><span class="text-violet-300">{tag}</span
        >{@render attrSpans()}<span class="text-fg-muted">/&gt;</span>
      {/if}
    {:else}
      <span class="text-fg-muted">&lt;</span><span class="text-violet-300">{tag}</span
      >{@render attrSpans()}<span class="text-fg-muted">&gt;</span>
      {#if isCollapsed}
        <span class="text-fg-muted italic">…&lt;/{tag}&gt;</span>
      {/if}
    {/if}
  </span>
</div>

{#if foldable && !isCollapsed}
  {#each children as child, idx (idx)}
    <Self element={child} depth={depth + 1} {collapsed} {selectedElementId} {onSelect} {autoCollapseDepth} />
  {/each}
  <div class="markup-line flex items-baseline rounded px-1 text-xs text-fg-muted" style="padding-left: {depth * 1.1}rem">
    <span class="mr-1 inline-block w-3 shrink-0"></span>
    <span class="font-mono">&lt;/{tag}&gt;</span>
  </div>
{/if}
