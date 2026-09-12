<script lang="ts">
  import type { Component, ComponentType, Snippet } from "svelte";
  import { Loader2, PlugZap, Star, Trash2 } from "lucide-svelte";

  interface Props {
    name: string;
    kindLabel: string;
    /** lucide-svelte still ships legacy ComponentType icons, so accept either. */
    icon: Component<any> | ComponentType<any>;
    accentClass?: string;
    isDefault: boolean;
    isEnabled: boolean;
    /** e.g. the configured URL/endpoint, shown in monospace. */
    endpoint: string;
    /** e.g. "strategy: auto · API key set · some notes" — caller composes the line. */
    detail?: string;
    testResult?: { ok: boolean; detail: string } | null;
    testing?: boolean;
    /** Whether the viewer may mutate this instance — hides all action buttons when false
     * (read-only viewing, e.g. a non-superadmin looking at platform-wide parsing engines). */
    canManage?: boolean;
    onTest?: () => void;
    onSetDefault?: () => void;
    onToggleEnabled?: () => void;
    onDelete?: () => void;
    extraBadges?: Snippet;
  }

  let {
    name,
    kindLabel,
    icon: Icon,
    accentClass = "text-blue-400",
    isDefault,
    isEnabled,
    endpoint,
    detail = "",
    testResult = null,
    testing = false,
    canManage = true,
    onTest,
    onSetDefault,
    onToggleEnabled,
    onDelete,
    extraBadges,
  }: Props = $props();
</script>

<!--
  Shared list-row layout for one configured external-provider instance —
  used by both the Document Parsing and LLM Providers panels in
  ExternalProvidersView.svelte so the two look and behave identically.
-->
<div
  class="flex flex-col gap-2 rounded-xl border border-border-default bg-surface-canvas/80 p-3.5 transition-colors hover:border-border-interactive sm:flex-row sm:items-start sm:justify-between"
>
  <div class="space-y-1">
    <div class="flex flex-wrap items-center gap-2">
      <Icon class="h-4 w-4 {accentClass}" />
      <span class="text-sm font-semibold text-fg-primary">{name}</span>
      <span
        class="rounded-md border border-border-default bg-surface-card px-2 py-0.5 text-micro font-semibold uppercase text-fg-muted"
      >
        {kindLabel}
      </span>
      {#if isDefault}
        <span
          class="inline-flex items-center gap-1 rounded-md border border-amber-800/60 bg-amber-950/60 px-2 py-0.5 text-micro font-semibold text-amber-300"
        >
          <Star class="h-3 w-3" /> Default
        </span>
      {/if}
      {#if !isEnabled}
        <span
          class="rounded-md border border-border-interactive bg-surface-overlay px-2 py-0.5 text-micro font-semibold text-fg-muted"
        >
          Disabled
        </span>
      {/if}
      {#if extraBadges}{@render extraBadges()}{/if}
    </div>
    <div class="font-mono text-caption text-fg-muted">{endpoint}</div>
    {#if detail}
      <div class="flex flex-wrap items-center gap-2 text-caption text-fg-muted">{detail}</div>
    {/if}
    {#if testResult}
      <div class="text-caption {testResult.ok ? 'text-emerald-400' : 'text-rose-400'}">
        {testResult.ok ? "Reachable" : "Unreachable"} — {testResult.detail}
      </div>
    {/if}
  </div>

  {#if canManage}
    <div class="flex shrink-0 flex-wrap items-center gap-1.5">
      {#if onTest}
        <button
          type="button"
          onclick={onTest}
          disabled={testing}
          class="flex items-center gap-1 rounded-lg border border-border-default px-2.5 py-1.5 text-caption font-medium text-fg-secondary transition-colors hover:bg-surface-hover disabled:opacity-50"
          title="Test connectivity"
        >
          {#if testing}
            <Loader2 class="h-3.5 w-3.5 animate-spin" />
          {:else}
            <PlugZap class="h-3.5 w-3.5" />
          {/if}
          <span>Test</span>
        </button>
      {/if}
      {#if !isDefault && onSetDefault}
        <button
          type="button"
          onclick={onSetDefault}
          class="rounded-lg border border-border-default px-2.5 py-1.5 text-caption font-medium text-fg-secondary transition-colors hover:bg-surface-hover"
          title="Make default"
        >
          Set Default
        </button>
      {/if}
      {#if onToggleEnabled}
        <button
          type="button"
          onclick={onToggleEnabled}
          class="rounded-lg border border-border-default px-2.5 py-1.5 text-caption font-medium text-fg-secondary transition-colors hover:bg-surface-hover"
          title={isEnabled ? "Disable" : "Enable"}
        >
          {isEnabled ? "Disable" : "Enable"}
        </button>
      {/if}
      {#if onDelete}
        <button
          type="button"
          onclick={onDelete}
          class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-rose-950/30 hover:text-rose-400"
          title="Remove instance"
        >
          <Trash2 class="h-4 w-4" />
        </button>
      {/if}
    </div>
  {/if}
</div>
