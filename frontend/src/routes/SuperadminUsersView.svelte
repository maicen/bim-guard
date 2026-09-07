<script lang="ts">
  import { Users, Building2, Plus, Trash2, UserPlus, X, ShieldCheck } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import Modal from "../lib/components/Modal.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import { organizationsApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { toasts } from "../lib/toast.svelte";
  import type { OrganizationSummary, UserSummary } from "../lib/types";

  let orgs = $state.raw<OrganizationSummary[]>([]);
  let users = $state.raw<UserSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let memberCounts = $derived.by(() => {
    const counts: Record<number, number> = {};
    for (const user of users) {
      for (const org of user.organizations) {
        counts[org.organization_id] = (counts[org.organization_id] ?? 0) + 1;
      }
    }
    return counts;
  });

  async function load() {
    loading = true;
    error = null;
    try {
      const [orgRes, userRes] = await Promise.all([
        organizationsApi.listAll(),
        organizationsApi.listAllUsers(),
      ]);
      orgs = orgRes.organizations;
      users = userRes.users;
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  load();

  // -- Users: search + pagination -----------------------------------------

  let searchQuery = $state("");
  let userPageIndex = $state(1);
  let userPageSize = $state(10);

  let filteredUsers = $derived(
    users.filter((u) => {
      const q = searchQuery.trim().toLowerCase();
      if (!q) return true;
      return (
        u.email.toLowerCase().includes(q) ||
        u.full_name.toLowerCase().includes(q) ||
        u.organizations.some((o) => o.name.toLowerCase().includes(q))
      );
    }),
  );

  let paginatedUsers = $derived(
    filteredUsers.slice((userPageIndex - 1) * userPageSize, userPageIndex * userPageSize),
  );

  // -- Create organization ---------------------------------------------------

  let isCreateOrgOpen = $state(false);
  let newOrgName = $state("");
  let isCreatingOrg = $state(false);

  async function submitCreateOrg() {
    const name = newOrgName.trim();
    if (!name) return;
    isCreatingOrg = true;
    try {
      await organizationsApi.create({ name });
      toasts.success(`Organization "${name}" created.`);
      isCreateOrgOpen = false;
      newOrgName = "";
      await load();
    } catch (err) {
      toasts.fromError(err, "Could not create organization.");
    } finally {
      isCreatingOrg = false;
    }
  }

  // -- Delete organization -----------------------------------------------

  let orgPendingDelete = $state<OrganizationSummary | null>(null);

  async function confirmDeleteOrg() {
    if (!orgPendingDelete) return;
    try {
      await organizationsApi.deleteOrganization(orgPendingDelete.id);
      toasts.success(`Organization "${orgPendingDelete.name}" deleted.`);
      await load();
    } catch (err) {
      toasts.fromError(err, "Could not delete organization.");
    } finally {
      orgPendingDelete = null;
    }
  }

  // -- Assign user to organization -----------------------------------------

  let assigningUser = $state<UserSummary | null>(null);
  let assignOrgId = $state<number | "">("");
  let assignRole = $state<"owner" | "admin" | "member">("member");
  let isAssigning = $state(false);

  function openAssignModal(user: UserSummary) {
    assigningUser = user;
    assignOrgId = orgs[0]?.id ?? "";
    assignRole = "member";
  }

  async function submitAssign() {
    if (!assigningUser || assignOrgId === "") return;
    isAssigning = true;
    try {
      await organizationsApi.addMember(Number(assignOrgId), {
        user_id: assigningUser.id,
        role: assignRole,
      });
      toasts.success(`${assigningUser.email || "User"} added to organization.`);
      assigningUser = null;
      await load();
    } catch (err) {
      toasts.fromError(err, "Could not assign user to organization.");
    } finally {
      isAssigning = false;
    }
  }

  // -- Remove user from an organization ------------------------------------

  let removalPending = $state<{ user: UserSummary; organizationId: number; orgName: string } | null>(
    null,
  );

  async function confirmRemoveFromOrg() {
    if (!removalPending) return;
    try {
      await organizationsApi.removeMember(removalPending.organizationId, removalPending.user.id);
      toasts.success(`Removed from ${removalPending.orgName}.`);
      await load();
    } catch (err) {
      toasts.fromError(err, "Could not remove user from organization.");
    } finally {
      removalPending = null;
    }
  }

  // -- Delete user ----------------------------------------------------------

  let userPendingDelete = $state<UserSummary | null>(null);

  async function confirmDeleteUser() {
    if (!userPendingDelete) return;
    try {
      await organizationsApi.deleteUser(userPendingDelete.id);
      toasts.success(`${userPendingDelete.email || "User"} deleted.`);
      await load();
    } catch (err) {
      toasts.fromError(err, "Could not delete user.");
    } finally {
      userPendingDelete = null;
    }
  }
</script>

<div class="space-y-6">
  <PageHeader
    category="Platform Governance"
    title="Users & Organizations"
    subtitle="See every user on the platform, assign or remove them from organizations, and manage organizations themselves."
    icon={Users}
  >
    {#snippet actions()}
      <button
        type="button"
        onclick={() => (isCreateOrgOpen = true)}
        class="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-violet-600/30 transition-all hover:bg-violet-500"
      >
        <Plus class="h-4 w-4" />
        <span>New Organization</span>
      </button>
    {/snippet}
  </PageHeader>

  {#if loading}
    <LoadingState message="Loading users and organizations…" />
  {:else if error}
    <EmptyState title="Could not load the platform directory" description={error} icon={Users} />
  {:else}
    <!-- Organizations -->
    <div class="space-y-3">
      <h2 class="text-sm font-bold uppercase tracking-wider text-slate-400">
        Organizations ({orgs.length})
      </h2>
      {#if orgs.length === 0}
        <EmptyState
          title="No organizations yet"
          description="Create the first organization to start assigning users to it."
          icon={Building2}
          actionLabel="New Organization"
          onAction={() => (isCreateOrgOpen = true)}
        />
      {:else}
        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40 shadow-xl">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead>
                <tr class="border-b border-slate-800 bg-slate-950/80">
                  <th class="px-4 py-3 font-semibold text-slate-300">Name</th>
                  <th class="px-4 py-3 font-semibold text-slate-300">Slug</th>
                  <th class="px-4 py-3 text-center font-semibold text-slate-300">Members</th>
                  <th class="w-16 px-4 py-3 text-center font-semibold text-slate-300">Delete</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each orgs as org (org.id)}
                  <tr class="transition-colors hover:bg-slate-800/40">
                    <td class="px-4 py-3 font-semibold text-slate-100">{org.name}</td>
                    <td class="px-4 py-3 font-mono text-micro text-slate-400">{org.slug}</td>
                    <td class="px-4 py-3 text-center font-mono text-slate-300">
                      {memberCounts[org.id] ?? 0}
                    </td>
                    <td class="px-4 py-3 text-center">
                      <button
                        type="button"
                        onclick={() => (orgPendingDelete = org)}
                        class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-rose-950/60 hover:text-rose-400"
                        title={`Delete ${org.name}`}
                      >
                        <Trash2 class="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}
    </div>

    <!-- Users -->
    <div class="space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h2 class="text-sm font-bold uppercase tracking-wider text-slate-400">
          Users ({filteredUsers.length})
        </h2>
        <input
          type="text"
          bind:value={searchQuery}
          placeholder="Search by email, name, or organization…"
          class="w-full max-w-xs rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:border-violet-500 focus:outline-none"
        />
      </div>

      {#if filteredUsers.length === 0}
        <EmptyState
          title="No matching users"
          description="Nobody has signed in yet, or your search didn't match anyone."
          icon={Users}
        />
      {:else}
        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40 shadow-xl">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead>
                <tr class="border-b border-slate-800 bg-slate-950/80">
                  <th class="px-4 py-3 font-semibold text-slate-300">User</th>
                  <th class="min-w-[16rem] px-4 py-3 font-semibold text-slate-300">Organizations</th>
                  <th class="w-32 px-4 py-3 text-center font-semibold text-slate-300">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each paginatedUsers as user (user.id)}
                  <tr class="transition-colors hover:bg-slate-800/40">
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-2">
                        <span class="font-semibold text-slate-100">{user.full_name || user.email || user.id}</span>
                        {#if user.is_superadmin}
                          <span
                            class="inline-flex items-center gap-1 rounded-md border border-violet-500/40 bg-violet-500/10 px-1.5 py-0.5 text-micro font-semibold text-violet-300"
                            title="Platform superadmin"
                          >
                            <ShieldCheck class="h-3 w-3" />
                            Superadmin
                          </span>
                        {/if}
                      </div>
                      {#if user.full_name && user.email}
                        <div class="truncate text-micro text-slate-500">{user.email}</div>
                      {/if}
                    </td>
                    <td class="px-4 py-3">
                      {#if user.organizations.length === 0}
                        <span class="text-micro text-slate-500">No organizations</span>
                      {:else}
                        <div class="flex flex-wrap gap-1.5">
                          {#each user.organizations as membership (membership.organization_id)}
                            <span
                              class="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-micro font-medium text-slate-300"
                            >
                              {membership.name}
                              <span class="text-slate-500">· {membership.role}</span>
                              <button
                                type="button"
                                onclick={() =>
                                  (removalPending = {
                                    user,
                                    organizationId: membership.organization_id,
                                    orgName: membership.name,
                                  })}
                                class="ml-0.5 rounded p-0.5 text-slate-500 transition-colors hover:bg-rose-950/60 hover:text-rose-400"
                                title={`Remove from ${membership.name}`}
                              >
                                <X class="h-3 w-3" />
                              </button>
                            </span>
                          {/each}
                        </div>
                      {/if}
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex items-center justify-center gap-1.5">
                        <button
                          type="button"
                          onclick={() => openAssignModal(user)}
                          disabled={orgs.length === 0}
                          class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-emerald-950/60 hover:text-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
                          title="Assign to an organization"
                        >
                          <UserPlus class="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onclick={() => (userPendingDelete = user)}
                          disabled={user.id === authState.user?.id}
                          class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-rose-950/60 hover:text-rose-400 disabled:cursor-not-allowed disabled:opacity-40"
                          title={user.id === authState.user?.id
                            ? "You cannot delete your own account"
                            : "Delete user"}
                        >
                          <Trash2 class="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <TablePagination
            totalItems={filteredUsers.length}
            pageSize={userPageSize}
            currentPage={userPageIndex}
            onPageChange={(p) => (userPageIndex = p)}
            onPageSizeChange={(s) => {
              userPageSize = s;
              userPageIndex = 1;
            }}
          />
        </div>
      {/if}
    </div>
  {/if}

  <!-- Create Organization Modal -->
  <Modal
    isOpen={isCreateOrgOpen}
    title="New Organization"
    subtitle="Create a new tenant. You can assign users to it right after."
    icon={Building2}
    onClose={() => (isCreateOrgOpen = false)}
  >
    {#snippet children()}
      <label class="block space-y-1.5" for="new-org-name">
        <span class="text-xs font-semibold text-slate-300">Organization name</span>
        <input
          id="new-org-name"
          type="text"
          bind:value={newOrgName}
          placeholder="e.g. Acme Engineering"
          class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:border-violet-500 focus:outline-none"
        />
      </label>
    {/snippet}
    {#snippet footer()}
      <button
        type="button"
        onclick={() => (isCreateOrgOpen = false)}
        class="h-9 rounded-xl border border-slate-700 bg-slate-800 px-4 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-700"
      >
        Cancel
      </button>
      <button
        type="button"
        onclick={submitCreateOrg}
        disabled={isCreatingOrg || !newOrgName.trim()}
        class="h-9 rounded-xl bg-violet-600 px-4 text-xs font-semibold text-white shadow-lg shadow-violet-950/50 transition-all hover:bg-violet-500 disabled:opacity-50"
      >
        {isCreatingOrg ? "Creating…" : "Create"}
      </button>
    {/snippet}
  </Modal>

  <!-- Assign User to Organization Modal -->
  <Modal
    isOpen={assigningUser !== null}
    title="Assign to Organization"
    subtitle={assigningUser ? `Add ${assigningUser.email || assigningUser.full_name} to an organization.` : ""}
    icon={UserPlus}
    onClose={() => (assigningUser = null)}
  >
    {#snippet children()}
      <label class="block space-y-1.5" for="assign-org">
        <span class="text-xs font-semibold text-slate-300">Organization</span>
        <select
          id="assign-org"
          bind:value={assignOrgId}
          class="w-full cursor-pointer rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-violet-500 focus:outline-none"
        >
          {#each orgs as org (org.id)}
            <option value={org.id}>{org.name}</option>
          {/each}
        </select>
      </label>
      <label class="block space-y-1.5" for="assign-role">
        <span class="text-xs font-semibold text-slate-300">Role</span>
        <select
          id="assign-role"
          bind:value={assignRole}
          class="w-full cursor-pointer rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-violet-500 focus:outline-none"
        >
          <option value="member">Member</option>
          <option value="admin">Admin</option>
          <option value="owner">Owner</option>
        </select>
      </label>
    {/snippet}
    {#snippet footer()}
      <button
        type="button"
        onclick={() => (assigningUser = null)}
        class="h-9 rounded-xl border border-slate-700 bg-slate-800 px-4 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-700"
      >
        Cancel
      </button>
      <button
        type="button"
        onclick={submitAssign}
        disabled={isAssigning || assignOrgId === ""}
        class="h-9 rounded-xl bg-emerald-600 px-4 text-xs font-semibold text-white shadow-lg shadow-emerald-950/50 transition-all hover:bg-emerald-500 disabled:opacity-50"
      >
        {isAssigning ? "Assigning…" : "Assign"}
      </button>
    {/snippet}
  </Modal>

  <!-- Confirm: delete organization -->
  <ConfirmModal
    isOpen={orgPendingDelete !== null}
    title="Delete organization?"
    message={orgPendingDelete
      ? `This permanently deletes "${orgPendingDelete.name}", its memberships, invites, groups, and grants. Projects it still owns must be deleted or reassigned first.`
      : ""}
    confirmText="Delete Organization"
    onConfirm={confirmDeleteOrg}
    onCancel={() => (orgPendingDelete = null)}
  />

  <!-- Confirm: remove from organization -->
  <ConfirmModal
    isOpen={removalPending !== null}
    title="Remove from organization?"
    message={removalPending
      ? `Remove ${removalPending.user.email || removalPending.user.full_name} from ${removalPending.orgName}?`
      : ""}
    confirmText="Remove"
    onConfirm={confirmRemoveFromOrg}
    onCancel={() => (removalPending = null)}
  />

  <!-- Confirm: delete user -->
  <ConfirmModal
    isOpen={userPendingDelete !== null}
    title="Delete user?"
    message={userPendingDelete
      ? `This permanently deletes ${userPendingDelete.email || userPendingDelete.full_name}'s account and removes them from every organization. This cannot be undone.`
      : ""}
    confirmText="Delete User"
    onConfirm={confirmDeleteUser}
    onCancel={() => (userPendingDelete = null)}
  />
</div>
