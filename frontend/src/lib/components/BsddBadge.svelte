<!--
  BsddBadge — hover-card badge for a bSDD-sourced value (an IFC class code
  or a property name). Renders the compact code inline; hovering (or
  tapping, on touch — HoverCard opens on focus too) lazily fetches the live
  buildingSMART Data Dictionary definition and shows it as a rich preview,
  so a reviewer sees what "IfcDoor" or "FireRating" actually means without
  leaving the page. The footer links out to bSDD's own page for the item —
  identifier.buildingsmart.org URIs are dereferenceable, so no separate
  "view in bSDD" plumbing is needed.

  Usage:

      <BsddBadge kind="class" value={rule.target_ifc_class} />
      <BsddBadge kind="property" value={rule.property_name} propertySet={rule.property_set} />
-->
<script lang="ts">
  import { Box, ExternalLink, Tag } from "lucide-svelte";
  import HoverCard from "./HoverCard.svelte";
  import { bsddApi } from "../api";
  import type { BSDDClassItem, BSDDPropertyItem } from "../types";

  interface Props {
    kind: "class" | "property";
    /** IFC class code (e.g. "IfcDoor") or property name (e.g. "FireRating"). */
    value: string | null | undefined;
    /** Property set the value is scoped to — shown in the subtitle, has no effect on the lookup. */
    propertySet?: string | null;
    dictionaryUri?: string;
    side?: "top" | "bottom" | "left" | "right";
    align?: "start" | "center" | "end";
    /** Extra classes on the inline trigger pill (the caller owns its own styling). */
    class?: string;
    /** Placeholder rendered when there is no value to look up. */
    fallback?: string;
  }

  let {
    kind,
    value,
    propertySet = null,
    dictionaryUri,
    side = "top",
    align = "start",
    class: className = "",
    fallback = "—",
  }: Props = $props();

  type Status = "idle" | "loading" | "loaded" | "empty" | "error";

  let status = $state<Status>("idle");
  let detail = $state<BSDDClassItem | BSDDPropertyItem | null>(null);
  let loadedFor = "";

  async function load() {
    if (!value || loadedFor === value) return;
    loadedFor = value;
    status = "loading";
    detail = null;
    try {
      if (kind === "class") {
        detail = await bsddApi.getClass(value, dictionaryUri);
        status = "loaded";
      } else {
        const { properties } = await bsddApi.searchProperties(value, dictionaryUri);
        const match =
          properties.find((p) => p.name.toLowerCase() === (value ?? "").toLowerCase()) ||
          properties[0] ||
          null;
        detail = match;
        status = match ? "loaded" : "empty";
      }
    } catch (err: any) {
      // getClass 404s with "... not found in dictionary ..." for a legitimate
      // miss (a custom or misspelled class) -- distinct from bSDD itself
      // being unreachable, which deserves a different message.
      status = /not found/i.test(err?.message || "") ? "empty" : "error";
    }
  }

  let isClass = $derived(kind === "class");
  let classDetail = $derived(isClass ? (detail as BSDDClassItem | null) : null);
  let propDetail = $derived(!isClass && detail ? (detail as BSDDPropertyItem) : null);
</script>

{#if value}
  <HoverCard
    {side}
    {align}
    width="w-80"
    icon={isClass ? Box : Tag}
    title={value}
    subtitle={status === "loading"
      ? "Looking up bSDD…"
      : isClass
        ? "bSDD IFC class"
        : propertySet
          ? `Property · ${propertySet}`
          : "bSDD property"}
    triggerClass={className}
    onOpen={load}
    showFooter={status === "loaded" && !!detail?.uri}
  >
    {#snippet trigger()}
      <span class="cursor-help">{value}</span>
    {/snippet}

    {#if status === "loading" || status === "idle"}
      <p class="text-slate-500">Fetching the bSDD definition…</p>
    {:else if status === "error"}
      <p class="text-slate-500">bSDD is unreachable right now.</p>
    {:else if status === "empty"}
      <p class="text-slate-500">
        No bSDD definition found for {isClass ? "this class" : "this property name"}.
      </p>
    {:else if classDetail}
      <div class="space-y-2">
        <p>{classDetail.description || "No description available."}</p>
        {#if classDetail.parent_class_code}
          <p class="text-micro text-slate-500">
            Extends <span class="font-mono text-slate-300">{classDetail.parent_class_code}</span>
          </p>
        {/if}
        {#if classDetail.related_ifc_entities?.length}
          <p class="text-micro text-slate-500">
            Related IFC entities:
            <span class="font-mono text-slate-300">{classDetail.related_ifc_entities.join(", ")}</span>
          </p>
        {/if}
        {#if classDetail.properties?.length}
          <p class="text-micro text-slate-500">
            {classDetail.properties.length} standardized {classDetail.properties.length === 1
              ? "property"
              : "properties"} in bSDD
          </p>
        {/if}
      </div>
    {:else if propDetail}
      <div class="space-y-2">
        <p>{propDetail.description || "No description available."}</p>
        <dl class="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-micro">
          {#if propDetail.data_type}
            <dt class="uppercase tracking-wider text-slate-500">Type</dt>
            <dd class="font-mono text-slate-200">{propDetail.data_type}</dd>
          {/if}
          {#if propDetail.units}
            <dt class="uppercase tracking-wider text-slate-500">Units</dt>
            <dd class="font-mono text-slate-200">{propDetail.units}</dd>
          {/if}
          {#if propDetail.property_set}
            <dt class="uppercase tracking-wider text-slate-500">Pset</dt>
            <dd class="font-mono text-slate-200">{propDetail.property_set}</dd>
          {/if}
        </dl>
        {#if propDetail.allowed_values?.length}
          <div class="flex flex-wrap gap-1 pt-0.5">
            {#each propDetail.allowed_values.slice(0, 8) as val (val)}
              <span
                class="rounded border border-slate-700/60 bg-slate-800 px-1.5 py-0.5 font-mono text-nano text-slate-300"
              >
                {val}
              </span>
            {/each}
            {#if propDetail.allowed_values.length > 8}
              <span class="text-nano text-slate-500"
                >+{propDetail.allowed_values.length - 8} more</span
              >
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    {#snippet footer()}
      {#if detail?.uri}
        <a
          href={detail.uri}
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-1 text-accent hover:underline"
        >
          View in bSDD <ExternalLink class="h-3 w-3" />
        </a>
      {/if}
    {/snippet}
  </HoverCard>
{:else}
  <span class={className}>{fallback}</span>
{/if}
