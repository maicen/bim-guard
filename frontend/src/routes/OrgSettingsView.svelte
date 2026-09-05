<script lang="ts">
  import { Building2, Mail, Plus, Shield, Trash2, UserPlus } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import Modal from "../lib/components/Modal.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import { organizationsApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { toasts } from "../lib/toast.svelte";
  import type { OrganizationInvite, OrganizationMember } from "../lib/types";

  let activeOrg = $derived(authState.activeOrganization);

  let members = $state.raw<OrganizationMember[]>([]);
  let invites = $state.raw<OrganizationInvite[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Members table state — search, sort, page, selection.
  let search = $state("");
  let sortField = $state<"full_name" | "role">("full_name");
  let sortAsc = $state(true);
  let pageIndex = $state(1);
  let pageSize = $state(10);
  let selected = $state.raw<Set<string>>(new Set());

  let filtered = $derived(
    members.filter((m) => {
      const q = search.trim().toLowerCase();
      if (!q) return true;
      return m.full_name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q);
    }),
  );
  let sorted = $derived.by(() => {
    const dir = sortAsc ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const av = (a[sortField] || (a.full_name ? "" : a.email)).toLowerCase();
      const bv = (b[sortField] || (b.full_name ? "" : b.email)).toLowerCase();
      return av < bv ? -dir : av > bv ? dir : 0;
    });
  });
  let page = $derived(sorted.slice((pageIndex - 1) * pageSize, pageIndex * pageSize));

  function handleSort(col: "full_name" | "role") {
    if (sortField === col) sortAsc = !sortAsc;
    else {
      sortField = col;
      sortAsc = true;
    }
  }

  function toggleRow(userId: string) {
    const next = new Set(selected);
    if (next.has(userId)) next.delete(userId);
    else next.add(userId);
    selected = next;
  }

  function toggleAllOnPage() {
    const pageIds = page.map((m) => m.user_id);
    const allSelected = pageIds.every((id) => selected.has(id));
    const next = new Set(selected);
    for (const id of pageIds) {
      if (allSelected) next.delete(id);
      else next.add(id);
    }
    selected = next;
  }

  let allOnPageSelected = $derived(page.length > 0 && page.every((m) => selected.has(m.user_id)));
  let someOnPageSelected = $derived(page.some((m) => selected.has(m.user_id)) && !allOnPageSelected);

  async function load() {
    if (!activeOrg) return;
    loading = true;
    error = null;
    try {
      const [memberRes, inviteRes] = await Promise.all([
        organizationsApi.listMembers(activeOrg.organization_id),
        organizationsApi.listInvites(activeOrg.organization_id),
      ]);
      members = memberRes.members;
      invites = inviteRes.invites.filter((i) => !i.accepted_at);
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (activeOrg) load();
  });

  // Bulk / row role changes
  let bulkRoleModalOpen = $state(false);
  let removeTarget: OrganizationMember | null = $state(null);

  async function setRole(userId: string, role: OrganizationMember["role"]) {
    if (!activeOrg) return;
    try {
      const res = await organizationsApi.updateMemberRole(activeOrg.organization_id, userId, role);
      members = res.members;
      toasts.success("Role updated.");
    } catch (err) {
      toasts.fromError(err, "Could not update role.");
    }
  }

  async function applyBulkRole(role: OrganizationMember["role"]) {
    if (!activeOrg) return;
    bulkRoleModalOpen = false;
    for (const userId of selected) {
      try {
        await organizationsApi.updateMemberRole(activeOrg.organization_id, userId, role);
      } catch (err) {
        toasts.fromError(err, `Could not update role for one member.`);
      }
    }
    selected = new Set();
    await load();
  }

  async function removeMember(userId: string) {
    if (!activeOrg) return;
    try {
      const res = await organizationsApi.removeMember(activeOrg.organization_id, userId);
      members = res.members;
      toasts.success("Member removed.");
    } catch (err) {
      toasts.fromError(err, "Could not remove member.");
    }
  }

  async function removeBulk() {
    if (!activeOrg) return;
    for (const userId of selected) {
      try {
        await organizationsApi.removeMember(activeOrg.organization_id, userId);
      } catch (err) {
        toasts.fromError(err, "Could not remove one member.");
      }
    }
    selected = new Set();
    await load();
  }

  // Invite modal
  let inviteModalOpen = $state(false);
  let inviteEmail = $state("");
  let inviteRole = $state<OrganizationInvite["role"]>("member");
  let inviteSubmitting = $state(false);
  let revokeTarget: OrganizationInvite | null = $state(null);

  async function submitInvite(e: Event) {
    e.preventDefault();
    if (!activeOrg || !inviteEmail.trim()) return;
    inviteSubmitting = true;
    try {
      const res = await organizationsApi.createInvite(activeOrg.organization_id, {
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      invites = res.invites.filter((i) => !i.accepted_at);
      toasts.success(`Invited ${inviteEmail.trim()}.`);
      inviteEmail = "";
      inviteRole = "member";
      inviteModalOpen = false;
    } catch (err) {
      toasts.fromError(err, "Could not send invite.");
    } finally {
      inviteSubmitting = false;
    }
  }

  async function revokeInvite(invite: OrganizationInvite) {
    if (!activeOrg) return;
    try {
      const res = await organizationsApi.revokeInvite(activeOrg.organization_id, invite.id);
      invites = res.invites.filter((i) => !i.accepted_at);
      toasts.success("Invite revoked.");
    } catch (err) {
      toasts.fromError(err, "Could not revoke invite.");
    } finally {
      revokeTarget = null;
    }
  }
</script>

<div class="space-y-6">
  <PageHeader
    category="Admin"
    title="Organization Settings"
    subtitle={activeOrg
      ? `Members and pending invites for ${activeOrg.name}.`
      : "Select an organization to manage its members."}
    icon={Building2}
  >
    {#snippet actions()}
      <button
        type="button"
        onclick={() => (inviteModalOpen = true)}
        disabled={!activeOrg}
        class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:opacity-50"
      >
        <UserPlus class="h-3.5 w-3.5" />
        Invite member
      </button>
    {/snippet}
  </PageHeader>

  {#if !activeOrg}
    <EmptyState
      title="No organization selected"
      description="Choose an organization from the header switcher to manage it here."
      icon={Building2}
    />
  {:else if loading}
    <LoadingState message="Loading members and invites…" />
  {:else if error}
    <EmptyState title="Could not load organization settings" description={error} icon={Shield} />
  {:else}
    <!-- Members -->
    <div class="rounded-2xl border border-slate-800 bg-slate-900/40">
      <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 p-4">
        <h2 class="text-sm font-bold text-slate-100">Members ({filtered.length})</h2>
        <input
          type="search"
          bind:value={search}
          placeholder="Search members…"
          class="w-56 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      <div class="px-4 pt-3">
        <BulkActionBar
          selectedCount={selected.size}
          itemLabel="member"
          onClearSelection={() => (selected = new Set())}
          onBulkEdit={() => (bulkRoleModalOpen = true)}
          onBulkDelete={removeBulk}
        />
      </div>

      {#if page.length === 0}
        <EmptyState
          title="No members match your search"
          description="Try a different name or email."
          icon={Shield}
        />
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead>
              <tr class="border-b border-slate-800">
                <th class="w-10 py-3 px-4">
                  <TableCheckbox
                    checked={allOnPageSelected}
                    indeterminate={someOnPageSelected}
                    ariaLabel="Select all members on this page"
                    onchange={toggleAllOnPage}
                  />
                </th>
                <SortHeader column="full_name" {sortField} {sortAsc} onSort={handleSort}>
                  Member
                </SortHeader>
                <SortHeader column="role" {sortField} {sortAsc} onSort={handleSort}>Role</SortHeader>
                <th class="py-3 px-4 text-right text-caption font-semibold uppercase tracking-wider text-slate-400"
                  >Actions</th
                >
              </tr>
            </thead>
            <tbody>
              {#each page as member (member.user_id)}
                <tr class="border-b border-slate-800/60 hover:bg-slate-900/60">
                  <td class="px-4 py-3">
                    <TableCheckbox
                      checked={selected.has(member.user_id)}
                      ariaLabel={`Select ${member.full_name || member.email}`}
                      onchange={() => toggleRow(member.user_id)}
                    />
                  </td>
                  <td class="px-4 py-3">
                    <div class="font-semibold text-slate-100">{member.full_name || "—"}</div>
                    <div class="flex items-center gap-1 text-slate-500">
                      <Mail class="h-3 w-3" />
                      {member.email || "no email on file"}
                    </div>
                  </td>
                  <td class="px-4 py-3">
                    <select
                      value={member.role}
                      onchange={(e) =>
                        setRole(member.user_id, (e.target as HTMLSelectElement).value as OrganizationMember["role"])}
                      class="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-xs capitalize text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    >
                      <option value="owner">Owner</option>
                      <option value="admin">Admin</option>
                      <option value="member">Member</option>
                    </select>
                  </td>
                  <td class="px-4 py-3 text-right">
                    <button
                      type="button"
                      onclick={() => (removeTarget = member)}
                      class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-rose-400 transition-colors hover:bg-rose-950/60"
                    >
                      <Trash2 class="h-3.5 w-3.5" />
                      Remove
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <TablePagination
          currentPage={pageIndex}
          {pageSize}
          totalItems={filtered.length}
          onPageChange={(p) => (pageIndex = p)}
          onPageSizeChange={(s) => {
            pageSize = s;
            pageIndex = 1;
          }}
        />
      {/if}
    </div>

    <!-- Pending invites -->
    <div class="rounded-2xl border border-slate-800 bg-slate-900/40">
      <div class="border-b border-slate-800 p-4">
        <h2 class="text-sm font-bold text-slate-100">Pending invites ({invites.length})</h2>
      </div>
      {#if invites.length === 0}
        <EmptyState
          title="No pending invites"
          description="Invite someone by email to give them access to this organization."
          icon={Mail}
          actionLabel="Invite member"
          onAction={() => (inviteModalOpen = true)}
        />
      {:else}
        <ul class="divide-y divide-slate-800/60">
          {#each invites as invite (invite.id)}
            <li class="flex items-center justify-between gap-3 px-4 py-3 text-xs">
              <div class="flex items-center gap-2 text-slate-200">
                <Mail class="h-3.5 w-3.5 text-slate-500" />
                {invite.email}
                <span class="rounded-full border border-slate-700 px-2 py-0.5 capitalize text-slate-400"
                  >{invite.role}</span
                >
              </div>
              <button
                type="button"
                onclick={() => (revokeTarget = invite)}
                class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-rose-400 transition-colors hover:bg-rose-950/60"
              >
                <Trash2 class="h-3.5 w-3.5" />
                Revoke
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}
</div>

<!-- Invite modal -->
<Modal
  isOpen={inviteModalOpen}
  title="Invite a member"
  subtitle={activeOrg?.name}
  icon={UserPlus}
  onClose={() => (inviteModalOpen = false)}
>
  <form onsubmit={submitInvite} class="space-y-4">
    <div>
      <label for="invite-email" class="mb-1 block font-semibold text-slate-300">Email address</label>
      <input
        id="invite-email"
        type="email"
        required
        bind:value={inviteEmail}
        placeholder="name@company.com"
        class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
    </div>
    <div>
      <label for="invite-role" class="mb-1 block font-semibold text-slate-300">Role</label>
      <select
        id="invite-role"
        bind:value={inviteRole}
        class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 capitalize text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option value="member">Member</option>
        <option value="admin">Admin</option>
        <option value="owner">Owner</option>
      </select>
    </div>
    <div class="flex justify-end gap-2 pt-1">
      <button
        type="button"
        onclick={() => (inviteModalOpen = false)}
        class="h-9 rounded-xl border border-slate-700 bg-slate-800 px-4 text-xs font-semibold text-slate-300 hover:bg-slate-700"
      >
        Cancel
      </button>
      <button
        type="submit"
        disabled={inviteSubmitting}
        class="inline-flex h-9 items-center gap-1.5 rounded-xl bg-accent px-4 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
      >
        <Plus class="h-3.5 w-3.5" />
        {inviteSubmitting ? "Sending…" : "Send invite"}
      </button>
    </div>
  </form>
</Modal>

<!-- Bulk role change -->
<Modal
  isOpen={bulkRoleModalOpen}
  title="Change role"
  subtitle={`${selected.size} member${selected.size === 1 ? "" : "s"} selected`}
  icon={Shield}
  onClose={() => (bulkRoleModalOpen = false)}
>
  <div class="grid grid-cols-3 gap-2">
    {#each ["owner", "admin", "member"] as const as role (role)}
      <button
        type="button"
        onclick={() => applyBulkRole(role)}
        class="rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-center text-xs font-semibold capitalize text-slate-200 transition-colors hover:border-accent hover:text-accent"
      >
        {role}
      </button>
    {/each}
  </div>
</Modal>

<ConfirmModal
  isOpen={removeTarget !== null}
  title="Remove member"
  message={`Remove ${removeTarget?.full_name || removeTarget?.email} from ${activeOrg?.name}? They will lose access to every project in this organization.`}
  confirmText="Remove"
  onConfirm={() => removeTarget && removeMember(removeTarget.user_id)}
  onCancel={() => (removeTarget = null)}
/>

<ConfirmModal
  isOpen={revokeTarget !== null}
  title="Revoke invite"
  message={`Revoke the invite sent to ${revokeTarget?.email}? They will no longer be able to join by signing in.`}
  confirmText="Revoke"
  onConfirm={() => revokeTarget && revokeInvite(revokeTarget)}
  onCancel={() => (revokeTarget = null)}
/>
