<script lang="ts">
  import { run } from "svelte/legacy";

  import {
    FolderArchive,
    Shield,
    MessageSquare,
    Camera,
    CheckCircle2,
    AlertTriangle,
    Send,
    Copy,
  } from "lucide-svelte";
  import { bcfApi } from "../api";
  import type { BCFTopicResponse, BCFCommentResponse, BCFViewpointResponse } from "../types";
  import Modal from "./Modal.svelte";
  import { toasts } from "../toast.svelte";
  import IsoGovernanceBadges from "./IsoGovernanceBadges.svelte";
  import SeverityBadge from "./SeverityBadge.svelte";

  interface Props {
    isOpen?: boolean;
    projectId: number | string;
    topic?: BCFTopicResponse | null;
    onClose: () => void;
    onSelectViewer?: ((projectId: number, guid?: string) => void) | undefined;
  }

  let {
    isOpen = false,
    projectId,
    topic = null,
    onClose,
    onSelectViewer = undefined,
  }: Props = $props();

  let comments: BCFCommentResponse[] = $state([]);
  let viewpoints: BCFViewpointResponse[] = $state([]);
  let isLoadingData = false;
  let newCommentText = $state("");
  let isSubmittingComment = $state(false);
  let copiedGuid = false;

  async function loadTopicExtras() {
    if (!topic) return;
    isLoadingData = true;
    try {
      const [comms, vps] = await Promise.all([
        bcfApi.listComments(projectId, topic.guid).catch(() => []),
        bcfApi.listViewpoints(projectId, topic.guid).catch(() => []),
      ]);
      comments = comms;
      viewpoints = vps;
    } finally {
      isLoadingData = false;
    }
  }

  async function handleAddComment() {
    if (!topic || !newCommentText.trim()) return;
    isSubmittingComment = true;
    try {
      const created = await bcfApi.createComment(projectId, topic.guid, {
        comment: newCommentText.trim(),
      });
      comments = [...comments, created];
      newCommentText = "";
    } catch (err: any) {
      toasts.error(err.message || "Unknown error", "Failed to add comment");
    } finally {
      isSubmittingComment = false;
    }
  }

  async function copyToClipboard(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      copiedGuid = true;
      setTimeout(() => (copiedGuid = false), 2000);
    } catch {
      // Clipboard access can be denied; tell the user rather than appearing to succeed.
      toasts.error("Could not copy to the clipboard.");
    }
  }

  function formatDate(d?: string | null) {
    if (!d) return "—";
    try {
      return new Date(d).toLocaleString();
    } catch {
      return d;
    }
  }
  run(() => {
    if (isOpen && topic) {
      loadTopicExtras();
    }
  });
</script>

{#if topic}
  <Modal
    {isOpen}
    title={topic.title}
    subtitle={`BCF GUID: ${topic.guid}`}
    icon={FolderArchive}
    maxWidth="max-w-2xl"
    {onClose}
  >
    {#snippet headerExtra()}
      <div class="flex items-center gap-2">
        <SeverityBadge severity={topic.topic_status || "Open"} />
        <span
          class="rounded-full border border-amber-800/60 bg-amber-950/60 px-2 py-0.5 text-xs font-semibold text-amber-400"
        >
          {topic.priority || "Normal"}
        </span>
      </div>
    {/snippet}

    <!-- Topic Properties Grid -->
    <div
      class="grid grid-cols-2 gap-2.5 rounded-xl border border-slate-800 bg-slate-950 p-3.5 text-xs sm:grid-cols-4"
    >
      <div>
        <span class="block text-micro font-semibold uppercase text-slate-500">Type</span>
        <span class="font-medium text-slate-200">{topic.topic_type || "Issue"}</span>
      </div>
      <div>
        <span class="block text-micro font-semibold uppercase text-slate-500">Priority</span>
        <span class="font-medium text-amber-400">{topic.priority || "Normal"}</span>
      </div>
      <div>
        <span class="block text-micro font-semibold uppercase text-slate-500">Assignee</span>
        <span class="font-medium text-slate-200">{topic.assigned_to || "Unassigned"}</span>
      </div>
      <div>
        <span class="block text-micro font-semibold uppercase text-slate-500">Created</span>
        <span class="text-slate-400">{formatDate(topic.creation_date)}</span>
      </div>
    </div>

    <!-- Description -->
    {#if topic.description}
      <div class="space-y-1">
        <span class="block text-xs font-semibold text-slate-300">Description &amp; Findings</span>
        <div
          class="whitespace-pre-wrap rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs leading-relaxed text-slate-200"
        >
          {topic.description}
        </div>
      </div>
    {/if}

    <!-- ISO 19650 Governance Container -->
    <div class="space-y-2 rounded-xl border border-slate-800 bg-slate-950/70 p-3.5">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1.5 text-xs font-bold text-slate-300">
          <Shield class="h-3.5 w-3.5 text-blue-400" />
          <span>ISO 19650 Governance Tags</span>
        </div>
        {#if topic.project_code}
          <span class="font-mono text-micro text-slate-400">Project: {topic.project_code}</span>
        {/if}
      </div>
      <IsoGovernanceBadges
        suitability={topic.suitability_code || "S0"}
        revision={topic.revision_code || "P01.01"}
        cdeState={topic.cde_state || "WIP"}
        size="sm"
      />
    </div>

    <!-- Linked Component GUIDs -->
    {#if topic.component_guids && topic.component_guids.length > 0}
      <div class="space-y-1.5">
        <span class="block text-xs font-semibold text-slate-300"
          >Linked IFC Elements ({topic.component_guids.length})</span
        >
        <div class="flex flex-wrap gap-1.5">
          {#each topic.component_guids as guid (guid)}
            <div
              class="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1 font-mono text-caption text-cyan-300"
            >
              <span>{guid}</span>
              <button
                type="button"
                onclick={() => copyToClipboard(guid)}
                class="p-0.5 hover:text-slate-50"
                title="Copy GUID"
              >
                <Copy class="h-3 w-3" />
              </button>
              {#if onSelectViewer && typeof projectId === "number"}
                <button
                  type="button"
                  onclick={() => onSelectViewer && onSelectViewer(Number(projectId), guid)}
                  class="ml-1 font-sans text-micro text-emerald-400 hover:underline"
                >
                  View 3D
                </button>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Viewpoints & Snapshots -->
    {#if viewpoints.length > 0}
      <div class="space-y-2">
        <span class="block flex items-center gap-1.5 text-xs font-semibold text-slate-300">
          <Camera class="h-3.5 w-3.5 text-blue-400" />
          <span>3D Camera Viewpoints ({viewpoints.length})</span>
        </span>
        <div class="grid grid-cols-2 gap-2">
          {#each viewpoints as vp (vp)}
            <div class="rounded-xl border border-slate-800 bg-slate-950 p-2.5 text-xs">
              <div class="font-mono text-micro text-slate-400">Viewpoint #{vp.index}</div>
              {#if vp.snapshot_url}
                <img
                  src={vp.snapshot_url}
                  alt="Viewpoint snapshot"
                  class="mt-1 h-24 w-full rounded border border-slate-800 object-cover"
                />
              {:else}
                <div class="mt-1 text-caption text-slate-500">
                  3D Perspective Camera Vector Stored
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Comments Discussion Feed -->
    <div class="space-y-3 border-t border-slate-800 pt-2">
      <div class="flex items-center justify-between">
        <span class="flex items-center gap-1.5 text-xs font-bold text-slate-200">
          <MessageSquare class="h-3.5 w-3.5 text-blue-400" />
          <span>Discussion &amp; History ({comments.length})</span>
        </span>
      </div>

      {#if comments.length === 0}
        <div
          class="rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-center text-xs text-slate-500"
        >
          No comments posted yet.
        </div>
      {:else}
        <div class="max-h-48 space-y-2 overflow-y-auto pr-1">
          {#each comments as c (c)}
            <div class="space-y-1 rounded-xl border border-slate-800/80 bg-slate-950 p-3 text-xs">
              <div class="flex items-center justify-between text-micro text-slate-500">
                <span class="font-semibold text-slate-300">{c.author || "Anonymous"}</span>
                <span>{formatDate(c.date)}</span>
              </div>
              <p class="whitespace-pre-wrap leading-relaxed text-slate-200">{c.comment}</p>
            </div>
          {/each}
        </div>
      {/if}

      <!-- New Comment Input -->
      <div class="flex items-center gap-2 pt-1">
        <input
          type="text"
          bind:value={newCommentText}
          placeholder="Post a coordination reply or update..."
          onkeydown={(e) => e.key === "Enter" && handleAddComment()}
          class="flex-1 rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
        />
        <button
          type="button"
          disabled={!newCommentText.trim() || isSubmittingComment}
          onclick={handleAddComment}
          class="rounded-xl bg-blue-600 p-2 text-white transition-colors hover:bg-blue-500 disabled:opacity-40"
          title="Post comment"
        >
          <Send class="h-3.5 w-3.5" />
        </button>
      </div>
    </div>

    {#snippet footer()}
      <button
        type="button"
        onclick={onClose}
        class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
      >
        Close
      </button>
    {/snippet}
  </Modal>
{/if}
