<script lang="ts">
  import { ShieldAlert, Lock, RotateCcw } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import { Select } from "../lib/components/ui";
  import { permissionsApi, organizationsApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import type { OrgRole, OrganizationSummary, PermissionActionInfo, RolePermission } from "../lib/types";

  const ROLE_OPTIONS: { value: OrgRole; label: string }[] = [
    { value: "member", label: "Member (and above)" },
    { value: "admin", label: "Admin (and above)" },
    { value: "owner", label: "Owner only" },
  ];

  let isSuperadmin = $derived(authState.isSuperadmin);

  let orgs = $state<OrganizationSummary[]>([]);
  let actions = $state<PermissionActionInfo[]>([]);
  let matrix = $state<RolePermission[]>([]);
  let loading = $state(true);
  let error = $state("");
  let savingAction = $state<string | null>(null);

  // Empty string = platform default scope; otherwise an organization id.
  let scope = $state<string>("");

  async function loadOrgs() {
    try {
      const res = await organizationsApi.listAll();
      orgs = res.organizations;
    } catch (err: any) {
      error = err.message || "Failed to load organizations.";
    }
  }

  async function loadMatrix() {
    loading = true;
    error = "";
    try {
      const [actionList, matrixList] = await Promise.all([
        permissionsApi.actions(),
        permissionsApi.matrix(scope ? Number(scope) : undefined),
      ]);
      actions = actionList;
      matrix = matrixList;
    } catch (err: any) {
      error = err.message || "Failed to load the permission matrix.";
    } finally {
      loading = false;
    }
  }

  function minRoleFor(action: string): OrgRole {
    return matrix.find((r) => r.action === action)?.min_role ?? "admin";
  }

  function isOverrideFor(action: string): boolean {
    return matrix.find((r) => r.action === action)?.is_override ?? false;
  }

  async function handleSetMinRole(action: string, minRole: OrgRole) {
    savingAction = action;
    error = "";
    try {
      await permissionsApi.setMinRole(
        action as any,
        minRole,
        scope ? Number(scope) : null,
      );
      await loadMatrix();
    } catch (err: any) {
      error = err.message || "Failed to update this action's minimum role.";
    } finally {
      savingAction = null;
    }
  }

  async function handleResetOverride(action: string) {
    if (!scope) return;
    savingAction = action;
    error = "";
    try {
      await permissionsApi.resetToDefault(action as any, Number(scope));
      await loadMatrix();
    } catch (err: any) {
      error = err.message || "Failed to reset this action to the platform default.";
    } finally {
      savingAction = null;
    }
  }

  $effect(() => {
    if (isSuperadmin) {
      loadOrgs();
    }
  });

  $effect(() => {
    if (isSuperadmin) {
      // Re-run whenever `scope` changes.
      void scope;
      loadMatrix();
    }
  });

  let scopeOptions = $derived([
    { value: "", label: "Platform default" },
    ...orgs.map((org) => ({ value: String(org.id), label: org.name })),
  ]);
</script>

<div class="space-y-6">
  <PageHeader
    category="Admin"
    title="Role Permissions"
    subtitle="Which organization role each gated action requires — platform default, or a per-organization override."
    icon={Lock}
  />

  {#if !isSuperadmin}
    <EmptyState
      title="Superadmin only"
      description="Only the platform superadmin can view or edit the role-permission matrix."
      icon={ShieldAlert}
    />
  {:else}
    <div class="space-y-4 rounded-2xl border border-border-default bg-surface-card/60 p-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="text-base font-bold tracking-tight text-fg-primary">Scope</h2>
          <p class="text-xs text-fg-muted">
            Edit the platform default, or one organization's override (which wins over the default when
            set).
          </p>
        </div>
        <div class="w-64">
          <Select
            ariaLabel="Scope"
            options={scopeOptions}
            bind:value={scope}
            triggerClass="w-full bg-surface-canvas"
          />
        </div>
      </div>

      {#if error}
        <div class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3.5 text-xs text-rose-300">
          {error}
        </div>
      {/if}

      {#if loading}
        <LoadingState message="Loading permission matrix..." />
      {:else}
        <div class="divide-y divide-border-subtle rounded-xl border border-border-default bg-surface-canvas/60">
          {#each actions as action (action.action)}
            <div class="flex flex-wrap items-center justify-between gap-3 px-3.5 py-3">
              <div class="min-w-0">
                <div class="flex items-center gap-1.5">
                  <span class="font-mono text-xs font-semibold text-fg-secondary">{action.action}</span>
                  {#if scope && isOverrideFor(action.action)}
                    <span
                      class="rounded-full border border-accent/60 bg-accent/10 px-1.5 py-0.5 text-micro font-semibold uppercase tracking-wide text-accent"
                      >Override</span
                    >
                  {/if}
                </div>
                {#if action.description}
                  <p class="mt-0.5 text-caption text-fg-muted">{action.description}</p>
                {/if}
              </div>
              <div class="flex shrink-0 items-center gap-2">
                <div class="w-44">
                  <Select
                    ariaLabel={`Minimum role for ${action.action}`}
                    options={ROLE_OPTIONS}
                    value={minRoleFor(action.action)}
                    onValueChange={(val) => handleSetMinRole(action.action, val as OrgRole)}
                    triggerClass="w-full bg-surface-canvas"
                    disabled={savingAction === action.action}
                  />
                </div>
                {#if scope && isOverrideFor(action.action)}
                  <button
                    type="button"
                    onclick={() => handleResetOverride(action.action)}
                    disabled={savingAction === action.action}
                    title="Reset to platform default"
                    class="rounded-lg border border-border-interactive bg-surface-overlay p-1.5 text-fg-secondary transition-colors hover:bg-surface-hover disabled:opacity-50"
                  >
                    <RotateCcw class="h-3.5 w-3.5" />
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>
