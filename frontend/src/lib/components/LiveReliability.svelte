<!--
  LiveReliability — a ReliabilityBadge that re-grades as the rule's properties are edited.

  For places where the property set / property name are editable (the manual
  rule form, the paste-text extraction table): a grade fetched once would go
  stale on the first edit. Edits are debounced, and a reply for an outdated
  edit is ignored. `initial` is a grade the server already computed for the
  starting values, so an unedited row costs no request.

  Usage:

      <LiveReliability propertySet={formPropertySet} propertyName={formPropertyName} showReason />
      <LiveReliability propertySet={rule.property_set} propertyName={rule.property_name}
        initial={rule.reliability} />
-->
<script lang="ts">
  import { onDestroy, untrack } from "svelte";
  import ReliabilityBadge from "./ReliabilityBadge.svelte";
  import { rulesApi } from "../api";
  import type { RuleReliability } from "../types";

  interface Props {
    propertySet?: string | null;
    propertyName?: string | null;
    compareProperty?: string | null;
    valueMinProperty?: string | null;
    valueMaxProperty?: string | null;
    /** The grade the server already computed for the starting values, if any. */
    initial?: RuleReliability | null;
    showReason?: boolean;
    fallback?: string;
  }

  let {
    propertySet = "",
    propertyName = "",
    compareProperty = "",
    valueMinProperty = "",
    valueMaxProperty = "",
    initial = null,
    showReason = false,
    fallback = "—",
  }: Props = $props();

  const DEBOUNCE_MS = 350;

  let inputsKey = $derived(
    JSON.stringify([
      propertySet ?? "",
      propertyName ?? "",
      compareProperty ?? "",
      valueMinProperty ?? "",
      valueMaxProperty ?? "",
    ]),
  );

  let current: RuleReliability | null = $state(untrack(() => initial));
  let loading = $state(false);
  // The inputs `initial` was graded for; while they are unchanged there is nothing to fetch.
  let seededFor: string | null = untrack(() => (initial ? inputsKey : null));
  let timer: ReturnType<typeof setTimeout> | undefined;
  let latestRequest = 0;

  $effect(() => {
    const key = inputsKey;
    if (key === seededFor) return;
    seededFor = null;

    clearTimeout(timer);
    const request = ++latestRequest;
    if (!propertyName?.trim()) {
      current = null;
      loading = false;
      return;
    }

    loading = true;
    timer = setTimeout(async () => {
      try {
        const graded = await rulesApi.assessReliability({
          property_set: propertySet || null,
          property_name: propertyName || null,
          compare_property: compareProperty || null,
          value_min_property: valueMinProperty || null,
          value_max_property: valueMaxProperty || null,
        });
        if (request === latestRequest) current = graded;
      } catch {
        // Advisory only: a failed grading call must never block editing the rule.
        if (request === latestRequest) current = null;
      } finally {
        if (request === latestRequest) loading = false;
      }
    }, DEBOUNCE_MS);
  });

  onDestroy(() => clearTimeout(timer));
</script>

<ReliabilityBadge reliability={current} {showReason} {fallback} {loading} />
