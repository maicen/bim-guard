<!--
  DocLangXmlTree — syntax-highlighted, foldable view of a document's raw
  DocLang XML, replacing the previous plain-text dump. Parses once per `xml`
  change and renders recursively via DocLangXmlNode.
-->
<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";
  import DocLangXmlNode from "./DocLangXmlNode.svelte";

  interface Props {
    xml: string;
    selectedElementId?: string | null;
    onSelect?: (elementId: string) => void;
  }

  let { xml, selectedElementId = null, onSelect = () => {} }: Props = $props();

  function parseRoot(source: string): Element | null {
    if (!source) return null;
    try {
      const doc = new DOMParser().parseFromString(source, "application/xml");
      if (doc.querySelector("parsererror")) return null;
      return doc.documentElement;
    } catch {
      return null;
    }
  }

  let root = $derived(parseRoot(xml));
  // Keyed by element, so it resets naturally whenever `root` (and therefore
  // every Element in it) is recreated by a fresh parse of a new `xml` string.
  let collapsed = $derived(new SvelteSet<Element>());
</script>

{#if root}
  {#key root}
    <div class="select-text">
      <DocLangXmlNode element={root} depth={0} {collapsed} {selectedElementId} onSelect={onSelect} />
    </div>
  {/key}
{:else}
  <div class="flex flex-col items-center justify-center py-16 text-center text-slate-400">
    <p class="text-sm font-semibold text-slate-300">No DocLang XML to display</p>
  </div>
{/if}
