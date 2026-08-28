<script lang="ts">
  import { onMount } from 'svelte';
  import { Settings, Save, CheckCircle2, AlertCircle, Database } from 'lucide-svelte';
  import { settingsApi } from '../lib/api';
  import type { SettingItem } from '../lib/types';

  let settings: SettingItem[] = [];
  let activeLogLevel = 'INFO';
  let dbBackend = 'SUPABASE';
  let isLoading = true;
  let isSaving = false;
  let error = '';
  let successMessage = '';

  onMount(async () => {
    try {
      const data = await settingsApi.get();
      settings = data.settings || [];
      activeLogLevel = data.active_log_level || 'INFO';
      dbBackend = data.db_backend || 'SUPABASE';
    } catch (err: any) {
      error = err.message || 'Failed to load application settings.';
    } finally {
      isLoading = false;
    }
  });

  async function handleSave() {
    isSaving = true;
    error = '';
    successMessage = '';

    const payload: Record<string, string> = {};
    settings.forEach((s) => {
      payload[s.key] = s.value;
    });

    try {
      const updated = await settingsApi.update(payload);
      settings = updated.settings || [];
      activeLogLevel = updated.active_log_level || activeLogLevel;
      successMessage = 'Runtime settings saved and persisted to database.';
    } catch (err: any) {
      error = err.message || 'Failed to save settings.';
    } finally {
      isSaving = false;
    }
  }
</script>

<div class="space-y-6 max-w-4xl mx-auto">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Configuration</div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">Runtime Settings</h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Manage application runtime parameters and logging levels persisted in database.
      </p>
    </div>

    <button
      type="button"
      disabled={isSaving}
      on:click={handleSave}
      class="inline-flex items-center gap-2 px-5 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] disabled:opacity-50"
    >
      <Save class="w-3.5 h-3.5" />
      <span>{isSaving ? 'Saving...' : 'Save Settings'}</span>
    </button>
  </div>

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
      <AlertCircle class="w-4 h-4 text-rose-400 shrink-0" />
      <span>{error}</span>
    </div>
  {/if}

  {#if successMessage}
    <div class="p-4 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2">
      <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Environment & Persistence Info -->
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <div class="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-1">
      <div class="text-xs text-slate-400 font-semibold uppercase">Persistence Backend</div>
      <div class="text-lg font-bold text-white flex items-center gap-2">
        <Database class="w-4 h-4 text-emerald-400" />
        <span>DB {dbBackend}</span>
      </div>
      <div class="text-[11px] text-slate-500">Configured via environment variables</div>
    </div>

    <div class="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-1">
      <div class="text-xs text-slate-400 font-semibold uppercase">Active Logging Level</div>
      <div class="text-lg font-bold text-cyan-400 font-mono">{activeLogLevel}</div>
      <div class="text-[11px] text-slate-500">Dynamic log level filter</div>
    </div>
  </div>

  <!-- Settings Form Table -->
  <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
    <h2 class="text-base font-bold text-white tracking-tight">Database Persisted Settings</h2>

    {#if isLoading}
      <div class="p-12 text-center text-xs text-slate-400">Loading settings...</div>
    {:else if settings.length === 0}
      <div class="p-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
        No settings records currently found in the database.
      </div>
    {:else}
      <div class="space-y-4">
        {#each settings as item}
          <div class="space-y-1.5 border-b border-slate-800/80 pb-4 last:border-b-0">
            <div class="flex items-center justify-between">
              <label for={`setting-${item.key}`} class="text-xs font-mono font-bold text-white">{item.key}</label>
              {#if item.description}
                <span class="text-[11px] text-slate-400">{item.description}</span>
              {/if}
            </div>
            {#if item.key === 'BIM_GUARD_LOG_LEVEL'}
              <select
                id={`setting-${item.key}`}
                bind:value={item.value}
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-[#0071e3]"
              />
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

