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
    Loader2,
  } from "lucide-svelte";
  import { settingsApi } from "../lib/api";
  import { themeMode, setTheme, type ThemeMode } from "../lib/theme";
  import { authState } from "../lib/auth.svelte";
  import { isAuthConfigured } from "../lib/supabaseClient";
  import type { SettingItem } from "../lib/types";
  import Select from "../lib/components/ui/Select.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import Alert from "../lib/components/Alert.svelte";
  import { toErrorLogEntry, type ErrorLogEntry } from "../lib/utils/errorLog";

  let settings: SettingItem[] = $state([]);
  let activeLogLevel = $state("INFO");
  let dbBackend = $state("SUPABASE");
  let isLoading = $state(true);
  let isSaving = $state(false);
  let error = $state("");
  let errorLog: ErrorLogEntry[] = $state([]);
  let successMessage = $state("");

  // ── Your Profile ──────────────────────────────────────────────────────────
  let profileFullName = $state("");
  let profileTitle = $state("");
  let profileSaving = $state(false);
  let profileError = $state("");
  let profileErrorLog: ErrorLogEntry[] = $state([]);
  let profileSuccess = $state("");

  // authState.profile loads asynchronously after sign-in, independent of this
  // view's own onMount, so the form fields track it reactively rather than
  // being read once.
  $effect(() => {
    profileFullName = authState.profile?.profile.full_name || "";
    profileTitle = authState.profile?.profile.title || "";
  });

  async function handleSaveProfile() {
    profileSaving = true;
    profileError = "";
    profileErrorLog = [];
    profileSuccess = "";
    try {
      await authState.updateProfile({
        full_name: profileFullName.trim(),
        title: profileTitle.trim(),
      });
      profileSuccess = "Profile saved.";
    } catch (err: any) {
      profileError = err.message || "Failed to save profile.";
      profileErrorLog = [toErrorLogEntry(err, "save profile")];
    } finally {
      profileSaving = false;
    }
  }

  onMount(async () => {
    try {
      const data = await settingsApi.get();
      settings = data.settings || [];
      activeLogLevel = data.active_log_level || "INFO";
      dbBackend = data.db_backend || "SUPABASE";
    } catch (err: any) {
      error = err.message || "Failed to load application settings.";
      errorLog = [toErrorLogEntry(err, "load settings")];
    } finally {
      isLoading = false;
    }
  });

  async function handleSave() {
    isSaving = true;
    error = "";
    errorLog = [];
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
      errorLog = [toErrorLogEntry(err, "save settings")];
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
          class="bg-accent hover:bg-accent-hover inline-flex items-center gap-2 rounded-xl px-5 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:scale-[1.02] disabled:opacity-50"
        >
          <Save class="h-3.5 w-3.5" />
          <span>{isSaving ? "Saving..." : "Save Settings"}</span>
        </button>
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <Alert
      type="error"
      message={error}
      errors={errorLog}
      logTitle="Settings Error Log"
      dismissible
      onDismiss={() => {
        error = "";
        errorLog = [];
      }}
    />
  {/if}

  {#if successMessage}
    <div
      class="border-success-border/60 bg-success-bg/40 text-success flex items-center gap-2 rounded-xl border p-4 text-xs"
    >
      <CheckCircle2 class="text-success h-4 w-4 shrink-0" />
      <span>{successMessage}</span>
    </div>
  {/if}

  {#if isAuthConfigured && authState.user}
    <div class="border-border-default bg-surface-card/60 space-y-4 rounded-2xl border p-6">
      <div>
        <h2 class="text-fg-primary text-base font-bold tracking-tight">Your Profile</h2>
        <p class="text-fg-muted text-xs">
          Display name and title shown alongside your account. Your avatar and email come from
          Google and aren't editable here.
        </p>
      </div>

      {#if profileError}
        <Alert
          type="error"
          message={profileError}
          errors={profileErrorLog}
          logTitle="Profile Save Error Log"
        />
      {/if}
      {#if profileSuccess}
        <div
          class="border-success-border/60 bg-success-bg/40 text-success flex items-center gap-2 rounded-xl border p-3.5 text-xs"
        >
          <CheckCircle2 class="text-success h-4 w-4 shrink-0" />
          <span>{profileSuccess}</span>
        </div>
      {/if}

      <div class="flex items-center gap-4">
        {#if authState.profile?.profile.avatar_url}
          <img
            src={authState.profile.profile.avatar_url}
            alt=""
            referrerpolicy="no-referrer"
            class="h-14 w-14 shrink-0 rounded-full object-cover"
          />
        {:else}
          <div
            class="bg-surface-overlay text-fg-secondary flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-lg font-semibold"
          >
            {(profileFullName || authState.user.email || "?")[0]?.toUpperCase()}
          </div>
        {/if}
        <div class="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label
              for="profile-full-name"
              class="text-caption text-fg-muted mb-1 block font-semibold">Display name</label
            >
            <input
              id="profile-full-name"
              type="text"
              bind:value={profileFullName}
              placeholder={authState.user.email}
              class="border-border-default bg-surface-canvas text-fg-primary placeholder:text-fg-muted focus:border-accent w-full rounded-xl border px-3 py-2 text-xs focus:outline-hidden"
            />
          </div>
          <div>
            <label for="profile-title" class="text-caption text-fg-muted mb-1 block font-semibold"
              >Title / discipline</label
            >
            <input
              id="profile-title"
              type="text"
              bind:value={profileTitle}
              placeholder="e.g. BIM Coordinator"
              class="border-border-default bg-surface-canvas text-fg-primary placeholder:text-fg-muted focus:border-accent w-full rounded-xl border px-3 py-2 text-xs focus:outline-hidden"
            />
          </div>
        </div>
      </div>

      <div class="flex justify-end">
        <button
          type="button"
          disabled={profileSaving}
          onclick={handleSaveProfile}
          class="bg-accent hover:bg-accent-hover flex items-center gap-1.5 rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition-all disabled:opacity-50"
        >
          {#if profileSaving}
            <Loader2 class="h-3.5 w-3.5 animate-spin" />
            <span>Saving...</span>
          {:else}
            <Save class="h-3.5 w-3.5" />
            <span>Save Profile</span>
          {/if}
        </button>
      </div>
    </div>
  {/if}

  <!-- Environment & Persistence Info -->
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
    <div class="border-border-default bg-surface-card/40 space-y-1 rounded-2xl border p-5">
      <div class="text-fg-muted text-xs font-semibold uppercase">Persistence Backend</div>
      <div class="text-fg-primary flex items-center gap-2 text-lg font-bold">
        <Database class="h-4 w-4 text-emerald-400" />
        <span>DB {dbBackend}</span>
      </div>
      <div class="text-caption text-fg-muted">Configured via environment variables</div>
    </div>

    <div class="border-border-default bg-surface-card/40 space-y-1 rounded-2xl border p-5">
      <div class="text-fg-muted text-xs font-semibold uppercase">Active Logging Level</div>
      <div class="font-mono text-lg font-bold text-cyan-400">
        {activeLogLevel}
      </div>
      <div class="text-caption text-fg-muted">Dynamic log level filter</div>
    </div>
  </div>

  <!-- Appearance & Theme Selector -->
  <div class="border-border-default bg-surface-card/60 space-y-4 rounded-2xl border p-6">
    <div>
      <h2 class="text-fg-primary text-base font-bold tracking-tight">Interface Appearance</h2>
      <p class="text-fg-muted text-xs">
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
          ? 'border-accent bg-accent/10 ring-accent ring-1'
          : 'border-border-default bg-surface-card/50 hover:bg-surface-hover'}"
      >
        <div class="bg-surface-overlay mb-3 flex h-8 w-8 items-center justify-center rounded-lg">
          <Moon class="h-4 w-4 text-blue-400" />
        </div>
        <span class="text-fg-primary text-sm font-semibold">Dark Theme</span>
        <span class="text-caption text-fg-muted mt-0.5"
          >Deep midnight palette for focused low-light environments</span
        >
      </button>

      <!-- Light Option -->
      <button
        type="button"
        onclick={() => setTheme("light")}
        class="flex flex-col items-start rounded-xl border p-4 text-left transition-all {$themeMode ===
        'light'
          ? 'border-accent bg-accent/10 ring-accent ring-1'
          : 'border-border-default bg-surface-card/50 hover:bg-surface-hover'}"
      >
        <div class="bg-surface-overlay mb-3 flex h-8 w-8 items-center justify-center rounded-lg">
          <Sun class="h-4 w-4 text-amber-400" />
        </div>
        <span class="text-fg-primary text-sm font-semibold">Light Theme</span>
        <span class="text-caption text-fg-muted mt-0.5"
          >High-contrast clean palette for bright environments</span
        >
      </button>

      <!-- System Option -->
      <button
        type="button"
        onclick={() => setTheme("system")}
        class="flex flex-col items-start rounded-xl border p-4 text-left transition-all {$themeMode ===
        'system'
          ? 'border-accent bg-accent/10 ring-accent ring-1'
          : 'border-border-default bg-surface-card/50 hover:bg-surface-hover'}"
      >
        <div class="bg-surface-overlay mb-3 flex h-8 w-8 items-center justify-center rounded-lg">
          <Laptop class="text-fg-secondary h-4 w-4" />
        </div>
        <span class="text-fg-primary text-sm font-semibold">System Auto</span>
        <span class="text-caption text-fg-muted mt-0.5"
          >Synchronize appearance with OS color scheme</span
        >
      </button>
    </div>
  </div>

  <!-- Settings Form Table -->
  <div class="border-border-default bg-surface-card/60 space-y-4 rounded-2xl border p-6">
    <h2 class="text-fg-primary text-base font-bold tracking-tight">Database Persisted Settings</h2>

    {#if isLoading}
      <div class="text-fg-muted p-12 text-center text-xs">Loading settings...</div>
    {:else if settings.length === 0}
      <div
        class="border-border-default text-fg-muted rounded-xl border border-dashed p-8 text-center text-xs"
      >
        No settings records currently found in the database.
      </div>
    {:else}
      <div class="space-y-4">
        {#each settings as item (item.key)}
          <div class="border-border-default space-y-1.5 border-b pb-4 last:border-b-0">
            <div class="flex items-center justify-between">
              <label for={`setting-${item.key}`} class="text-fg-primary font-mono text-xs font-bold"
                >{item.key}</label
              >
              {#if item.description}
                <span class="text-caption text-fg-muted">{item.description}</span>
              {/if}
            </div>
            {#if item.key === "BIM_GUARD_LOG_LEVEL"}
              <Select
                bind:value={item.value}
                ariaLabel={item.description || item.key}
                options={[
                  { value: "DEBUG", label: "DEBUG" },
                  { value: "INFO", label: "INFO" },
                  { value: "WARNING", label: "WARNING" },
                  { value: "ERROR", label: "ERROR" },
                ]}
              />
            {:else}
              <input
                id={`setting-${item.key}`}
                type="text"
                bind:value={item.value}
                placeholder={item.description || item.key}
                class="border-border-default bg-surface-canvas text-fg-primary placeholder:text-fg-muted focus:border-accent w-full rounded-xl border px-3 py-2 text-xs focus:outline-hidden"
              />
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
