<script lang="ts">
  import { FolderArchive, Shield, MessageSquare, Camera, CheckCircle2, AlertTriangle, Send, Copy } from 'lucide-svelte';
  import { bcfApi } from '../api';
  import type { BCFTopicResponse, BCFCommentResponse, BCFViewpointResponse } from '../types';
  import Modal from './Modal.svelte';
  import IsoGovernanceBadges from './IsoGovernanceBadges.svelte';
  import SeverityBadge from './SeverityBadge.svelte';

  export let isOpen: boolean = false;
  export let projectId: number | string;
  export let topic: BCFTopicResponse | null = null;
  export let onClose: () => void;
  export let onSelectViewer: ((projectId: number, guid?: string) => void) | undefined = undefined;

  let comments: BCFCommentResponse[] = [];
  let viewpoints: BCFViewpointResponse[] = [];
  let isLoadingData = false;
  let newCommentText = '';
  let isSubmittingComment = false;
  let copiedGuid = false;

  $: if (isOpen && topic) {
    loadTopicExtras();
  }

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
      newCommentText = '';
    } catch (err: any) {
      alert(`Failed to add comment: ${err.message}`);
    } finally {
      isSubmittingComment = false;
    }
  }

  async function copyToClipboard(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      copiedGuid = true;
      setTimeout(() => (copiedGuid = false), 2000);
    } catch {}
  }

  function formatDate(d?: string | null) {
    if (!d) return '—';
    try {
      return new Date(d).toLocaleString();
    } catch {
      return d;
    }
  }
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
        <SeverityBadge severity={topic.topic_status || 'Open'} />
        <span class="text-xs font-semibold text-amber-400 bg-amber-950/60 border border-amber-800/60 px-2 py-0.5 rounded-full">
          {topic.priority || 'Normal'}
        </span>
      </div>
    {/snippet}

    <!-- Topic Properties Grid -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs bg-slate-950 p-3.5 rounded-xl border border-slate-800">
      <div>
        <span class="text-micro font-semibold text-slate-500 uppercase block">Type</span>
        <span class="text-slate-200 font-medium">{topic.topic_type || 'Issue'}</span>
      </div>
      <div>
        <span class="text-micro font-semibold text-slate-500 uppercase block">Priority</span>
        <span class="text-amber-400 font-medium">{topic.priority || 'Normal'}</span>
      </div>
      <div>
        <span class="text-micro font-semibold text-slate-500 uppercase block">Assignee</span>
        <span class="text-slate-200 font-medium">{topic.assigned_to || 'Unassigned'}</span>
      </div>
      <div>
        <span class="text-micro font-semibold text-slate-500 uppercase block">Created</span>
        <span class="text-slate-400">{formatDate(topic.creation_date)}</span>
      </div>
    </div>

    <!-- Description -->
    {#if topic.description}
      <div class="space-y-1">
        <span class="text-xs font-semibold text-slate-300 block">Description &amp; Findings</span>
        <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
          {topic.description}
        </div>
      </div>
    {/if}

    <!-- ISO 19650 Governance Container -->
    <div class="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1.5 text-xs font-bold text-slate-300">
          <Shield class="w-3.5 h-3.5 text-blue-400" />
          <span>ISO 19650 Governance Tags</span>
        </div>
        {#if topic.project_code}
          <span class="text-micro font-mono text-slate-400">Project: {topic.project_code}</span>
        {/if}
      </div>
      <IsoGovernanceBadges
        suitability={topic.suitability_code || 'S0'}
        revision={topic.revision_code || 'P01.01'}
        cdeState={topic.cde_state || 'WIP'}
        size="sm"
      />
    </div>

    <!-- Linked Component GUIDs -->
    {#if topic.component_guids && topic.component_guids.length > 0}
      <div class="space-y-1.5">
        <span class="text-xs font-semibold text-slate-300 block">Linked IFC Elements ({topic.component_guids.length})</span>
        <div class="flex flex-wrap gap-1.5">
          {#each topic.component_guids as guid}
            <div class="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 font-mono text-caption text-cyan-300">
              <span>{guid}</span>
              <button
                type="button"
                on:click={() => copyToClipboard(guid)}
                class="p-0.5 hover:text-slate-50"
                title="Copy GUID"
              >
                <Copy class="w-3 h-3" />
              </button>
              {#if onSelectViewer && typeof projectId === 'number'}
                <button
                  type="button"
                  on:click={() => onSelectViewer && onSelectViewer(Number(projectId), guid)}
                  class="text-micro text-emerald-400 hover:underline ml-1 font-sans"
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
        <span class="text-xs font-semibold text-slate-300 block flex items-center gap-1.5">
          <Camera class="w-3.5 h-3.5 text-blue-400" />
          <span>3D Camera Viewpoints ({viewpoints.length})</span>
        </span>
        <div class="grid grid-cols-2 gap-2">
          {#each viewpoints as vp}
            <div class="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
              <div class="font-mono text-micro text-slate-400">Viewpoint #{vp.index}</div>
              {#if vp.snapshot_url}
                <img src={vp.snapshot_url} alt="Viewpoint snapshot" class="w-full h-24 object-cover rounded mt-1 border border-slate-800" />
              {:else}
                <div class="text-caption text-slate-500 mt-1">3D Perspective Camera Vector Stored</div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Comments Discussion Feed -->
    <div class="space-y-3 pt-2 border-t border-slate-800">
      <div class="flex items-center justify-between">
        <span class="text-xs font-bold text-slate-200 flex items-center gap-1.5">
          <MessageSquare class="w-3.5 h-3.5 text-blue-400" />
          <span>Discussion &amp; History ({comments.length})</span>
        </span>
      </div>

      {#if comments.length === 0}
        <div class="p-4 rounded-xl bg-slate-950/40 border border-slate-800 text-xs text-slate-500 text-center">
          No comments posted yet.
        </div>
      {:else}
        <div class="space-y-2 max-h-48 overflow-y-auto pr-1">
          {#each comments as c}
            <div class="p-3 rounded-xl bg-slate-950 border border-slate-800/80 text-xs space-y-1">
              <div class="flex items-center justify-between text-micro text-slate-500">
                <span class="font-semibold text-slate-300">{c.author || 'Anonymous'}</span>
                <span>{formatDate(c.date)}</span>
              </div>
              <p class="text-slate-200 leading-relaxed whitespace-pre-wrap">{c.comment}</p>
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
          on:keydown={(e) => e.key === 'Enter' && handleAddComment()}
          class="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-50 placeholder-slate-500 focus:outline-none focus:border-accent"
        />
        <button
          type="button"
          disabled={!newCommentText.trim() || isSubmittingComment}
          on:click={handleAddComment}
          class="p-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-40"
          title="Post comment"
        >
          <Send class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    {#snippet footer()}
      <button
        type="button"
        on:click={onClose}
        class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-50 transition-colors"
      >
        Close
      </button>
    {/snippet}
  </Modal>
{/if}
