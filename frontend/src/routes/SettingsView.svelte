<script lang="ts">
  import { onMount } from "svelte";
  import {
    Settings,
    Save,
    CheckCircle2,
    AlertCircle,
    Database,
    Sun,
    Moon,
    Laptop,
  } from "lucide-svelte";
  import { settingsApi } from "../lib/api";
  import { themeMode, setTheme, type ThemeMode } from "../lib/theme";
  import type { SettingItem } from "../lib/types";
  import PageHeader from "../lib/components/PageHeader.svelte";

  let settings: SettingItem[] = $state([]);
  let activeLogLevel = $state("INFO");
  let dbBackend = $state("SUPABASE");
  let isLoading = $state(true);
  let isSaving = $state(false);
  let error = $state("");
  let successMessage = $state("");

  onMount(async () => {
    try {
      const data = await settingsApi.get();
      settings = data.settings || [];
      activeLogLevel = data.active_log_level || "INFO";
      dbBackend = data.db_backend || "SUPABASE";
    } catch (err: any) {
      error = err.message || "Failed to load application settings.";
    } finally {
      isLoading = false;
    }
  });

  async function handleSave() {
    isSaving = true;
    error = "";
    successMessage = "";

    const payload: Record<string, string> = {};
    settings.forEach((s) => {
      payload[s.key] = s.value;
    });

    try {
      const updated = await settingsApi.update(payload);
      settings = updated.settings || [];
      activeLogLevel = updated.active_log_level || activeLogLevel;
      successMessage = "Runtime settings saved and persisted to database.";
    } catch (err: any) {
      error = err.message || "Failed to save settings.";
    } finally {
      isSaving = false;
    }
  }
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <PageHeader
    category="Configuration"
    title="Runtime Settings"
    subtitle="Manage application runtime parameters and logging levels persisted in database."
    icon={Settings}
  >
    {#snippet actions()}
      <div>
        <button
          type="button"
          disabled={isSaving}
          onclick={handleSave}
          class="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:opacity-50"
        >
          <Save class="h-3.5 w-3.5" />
          <span>{isSaving ? "Saving..." : "Save Settings"}</span>
        </button>
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div
      class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300"
    >
      <AlertCircle class="h-4 w-4 shrink-0 text-rose-400" />
      <span>{error}</span>
    </div>
  {/if}

  {#if successMessage}
    <div
      class="flex items-center gap-2 rounded-xl border border-emerald-800 bg-emerald-950/50 p-4 text-xs text-emerald-300"
    >
      <CheckCircle2 class="h-4 w-4 shrink-0 text-emerald-400" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Environment & Persistence Info -->
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
    <div class="space-y-1 rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
      <div class="text-xs font-semibold uppercase text-slate-400">Persistence Backend</div>
      <div class="flex items-center gap-2 text-lg font-bold text-slate-50">
        <Database class="h-4 w-4 text-emerald-400" />
        <span>DB {dbBackend}</span>
      </div>
      <div class="text-caption text-slate-500">Configured via environment variables</div>
    </div>

    <div class="space-y-1 rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
      <div class="text-xs font-semibold uppercase text-slate-400">Active Logging Level</div>
      <div class="font-mono text-lg font-bold text-cyan-400">
        {activeLogLevel}
      </div>
      <div class="text-caption text-slate-500">Dynamic log level filter</div>
    </div>
  </div>

  <!-- Appearance & Theme Selector -->
  <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
    <div>
      <h2 class="text-base font-bold tracking-tight text-slate-50">Interface Appearance</h2>
      <p class="text-xs text-slate-400">
        Select your preferred color theme or synchronize automatically with your operating system.
      </p>
    </div>

    <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <!-- Dark Option -->
      <button
        type="button"
        onclick={() => setTheme("dark")}
        class="flex flex-col items-start rounded-xl border p-4 text-left transition-all {$themeMode ===
        'dark'
          ? 'border-accent bg-accent/10 ring-1 ring-accent'
          : 'border-slate-800 bg-slate-900/50 hover:bg-slate-800/60'}"
      >
        <div class="mb-3 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800">
          <Moon class="h-4 w-4 text-blue-400" />
        </div>
        <span class="text-sm font-semibold text-slate-50">Dark Theme</span>
        <span class="mt-0.5 text-caption text-slate-400"
          >Deep midnight palette for focused low-light environments</span
        >
      </button>

      <!-- Light Option -->
      <button
        type="button"
        onclick={() => setTheme("light")}
        class="flex flex-col items-start rounded-xl border p-4 text-left transition-all {$themeMode ===
        'light'
          ? 'border-accent bg-accent/10 ring-1 ring-accent'
          : 'border-slate-800 bg-slate-900/50 hover:bg-slate-800/60'}"
      >
        <div class="mb-3 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800">
          <Sun class="h-4 w-4 text-amber-400" />
        </div>
        <span class="text-sm font-semibold text-slate-50">Light Theme</span>
        <span class="mt-0.5 text-caption text-slate-400"
          >High-contrast clean palette for bright environments</span
        >
      </button>

      <!-- System Option -->
      <button
        type="button"
        onclick={() => setTheme("system")}
        class="flex flex-col items-start rounded-xl border p-4 text-left transition-all {$themeMode ===
        'system'
          ? 'border-accent bg-accent/10 ring-1 ring-accent'
          : 'border-slate-800 bg-slate-900/50 hover:bg-slate-800/60'}"
      >
        <div class="mb-3 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800">
          <Laptop class="h-4 w-4 text-slate-300" />
        </div>
        <span class="text-sm font-semibold text-slate-50">System Auto</span>
        <span class="mt-0.5 text-caption text-slate-400"
          >Synchronize appearance with OS color scheme</span
        >
      </button>
    </div>
  </div>

  <!-- Settings Form Table -->
  <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
    <h2 class="text-base font-bold tracking-tight text-slate-50">Database Persisted Settings</h2>

    {#if isLoading}
      <div class="p-12 text-center text-xs text-slate-400">Loading settings...</div>
    {:else if settings.length === 0}
      <div
        class="rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500"
      >
        No settings records currently found in the database.
      </div>
    {:else}
      <div class="space-y-4">
        {#each settings as item (item.key)}
          <div class="space-y-1.5 border-b border-slate-800/80 pb-4 last:border-b-0">
            <div class="flex items-center justify-between">
              <label for={`setting-${item.key}`} class="font-mono text-xs font-bold text-slate-50"
                >{item.key}</label
              >
              {#if item.description}
                <span class="text-caption text-slate-400">{item.description}</span>
              {/if}
            </div>
            {#if item.key === "BIM_GUARD_LOG_LEVEL"}
              <select
                id={`setting-${item.key}`}
                bind:value={item.value}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
              >
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
              </select>
            {:else}
              <input
                id={`setting-${item.key}`}
                type="text"
                bind:value={item.value}
                placeholder={item.description || item.key}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 placeholder-slate-600 focus:border-accent focus:outline-none"
              />
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
