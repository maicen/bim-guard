<script lang="ts">
  import { X, Check, FolderArchive, AlertTriangle, Tag, Shield, Calendar, User } from 'lucide-svelte';
  import { bcfApi } from '../api';
  import type { BCFTopicResponse, BCFTopicCreatePayload, BCFTopicUpdatePayload } from '../types';
  import { CDE_STATE_CHOICES, SUITABILITY_CODES } from '../types';

  export let isOpen: boolean = false;
  export let projectId: number | string;
  export let topicToEdit: BCFTopicResponse | null = null;
  export let onClose: () => void;
  export let onSaved: (topic: BCFTopicResponse) => void;

  let title = '';
  let topicType = 'Issue';
  let topicStatus = 'Open';
  let priority = 'Normal';
  let description = '';
  let assignedTo = '';
  let dueDate = '';
  let suitabilityCode = 'S0';
  let revisionCode = 'P01.01';
  let cdeState: any = 'WIP';
  let componentGuidsText = '';

  let isSaving = false;
  let errorMessage = '';

  $: isEditing = !!topicToEdit;

  $: if (isOpen) {
    errorMessage = '';
    if (topicToEdit) {
      title = topicToEdit.title || '';
      topicType = topicToEdit.topic_type || 'Issue';
      topicStatus = topicToEdit.topic_status || 'Open';
      priority = topicToEdit.priority || 'Normal';
      description = topicToEdit.description || '';
      assignedTo = topicToEdit.assigned_to || '';
      dueDate = topicToEdit.due_date || '';
      suitabilityCode = topicToEdit.suitability_code || 'S0';
      revisionCode = topicToEdit.revision_code || 'P01.01';
      cdeState = topicToEdit.cde_state || 'WIP';
      componentGuidsText = (topicToEdit.component_guids || []).join(', ');
    } else {
      title = '';
      topicType = 'Clash / Compliance';
      topicStatus = 'Open';
      priority = 'Normal';
      description = '';
      assignedTo = 'BIM Coordinator';
      dueDate = '';
      suitabilityCode = 'S0';
      revisionCode = 'P01.01';
      cdeState = 'WIP';
      componentGuidsText = '';
    }
  }

  async function handleSave() {
    if (!title.trim()) {
      errorMessage = 'Topic title is required.';
      return;
    }

    isSaving = true;
    errorMessage = '';

    const guids = componentGuidsText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      if (isEditing && topicToEdit) {
        const payload: BCFTopicUpdatePayload = {
          title: title.trim(),
          topic_type: topicType,
          topic_status: topicStatus,
          priority,
          description: description.trim(),
          assigned_to: assignedTo.trim() || undefined,
          due_date: dueDate || undefined,
          component_guids: guids,
          suitability_code: suitabilityCode,
          revision_code: revisionCode,
          cde_state: cdeState,
        };
        const updated = await bcfApi.updateTopic(projectId, topicToEdit.guid, payload);
        onSaved(updated);
      } else {
        const payload: BCFTopicCreatePayload = {
          title: title.trim(),
          topic_type: topicType,
          topic_status: topicStatus,
          priority,
          description: description.trim(),
          assigned_to: assignedTo.trim() || undefined,
          due_date: dueDate || undefined,
          component_guids: guids,
          suitability_code: suitabilityCode,
          revision_code: revisionCode,
          cde_state: cdeState,
        };
        const created = await bcfApi.createTopic(projectId, payload);
        onSaved(created);
      }
      onClose();
    } catch (err: any) {
      errorMessage = err.message || 'Failed to save BCF topic.';
    } finally {
      isSaving = false;
    }
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <FolderArchive class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">
              {isEditing ? 'Edit BCF Topic' : 'Create Live BCF 2.1 Topic'}
            </h2>
            <p class="text-xs text-slate-400">
              buildingSMART BCF standard collaboration issue with ISO 19650 governance.
            </p>
          </div>
        </div>
        <button
          type="button"
          on:click={onClose}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Form Body -->
      <div class="p-6 space-y-4 overflow-y-auto">
        {#if errorMessage}
          <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle class="w-4 h-4 shrink-0 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
        {/if}

        <!-- Title -->
        <div class="space-y-1.5">
          <label for="topic-title" class="block text-xs font-semibold text-slate-300">
            Topic Title <span class="text-rose-400">*</span>
          </label>
          <input
            id="topic-title"
            type="text"
            bind:value={title}
            placeholder="e.g. Non-compliant Door Clear Width at Level 1"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
          />
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <!-- Type -->
          <div class="space-y-1.5">
            <label for="topic-type" class="block text-xs font-semibold text-slate-300">
              Type
            </label>
            <select
              id="topic-type"
              bind:value={topicType}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            >
              <option value="Issue">Issue</option>
              <option value="Clash / Compliance">Clash / Compliance</option>
              <option value="Remark">Remark</option>
              <option value="Request">Request</option>
            </select>
          </div>

          <!-- Status -->
          <div class="space-y-1.5">
            <label for="topic-status" class="block text-xs font-semibold text-slate-300">
              Status
            </label>
            <select
              id="topic-status"
              bind:value={topicStatus}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            >
              <option value="Open">Open</option>
              <option value="In Progress">In Progress</option>
              <option value="Resolved">Resolved</option>
              <option value="Closed">Closed</option>
            </select>
          </div>

          <!-- Priority -->
          <div class="space-y-1.5">
            <label for="topic-priority" class="block text-xs font-semibold text-slate-300">
              Priority
            </label>
            <select
              id="topic-priority"
              bind:value={priority}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            >
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Normal">Normal</option>
              <option value="Low">Low</option>
            </select>
          </div>
        </div>

        <!-- Description -->
        <div class="space-y-1.5">
          <label for="topic-desc" class="block text-xs font-semibold text-slate-300">
            Description &amp; Findings Note
          </label>
          <textarea
            id="topic-desc"
            bind:value={description}
            rows="3"
            placeholder="Detailed description of the architectural or engineering non-compliance..."
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
          ></textarea>
        </div>

        <!-- Assignee & Due Date -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="space-y-1.5">
            <label for="topic-assignee" class="block text-xs font-semibold text-slate-300">
              Assigned To
            </label>
            <input
              id="topic-assignee"
              type="text"
              bind:value={assignedTo}
              placeholder="e.g. Lead Architect / BIM Coordinator"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
            />
          </div>

          <div class="space-y-1.5">
            <label for="topic-due" class="block text-xs font-semibold text-slate-300">
              Due Date
            </label>
            <input
              id="topic-due"
              type="date"
              bind:value={dueDate}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
            />
          </div>
        </div>

        <!-- ISO 19650 Governance Section -->
        <div class="p-4 rounded-xl bg-slate-950/70 border border-slate-800 space-y-3">
          <div class="flex items-center gap-1.5 text-xs font-bold text-slate-300 uppercase tracking-wider">
            <Shield class="w-3.5 h-3.5 text-blue-400" />
            <span>ISO 19650 CDE Governance</span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div class="space-y-1">
              <label for="topic-cde" class="block text-[11px] font-semibold text-slate-400">CDE State</label>
              <select
                id="topic-cde"
                bind:value={cdeState}
                class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
              >
                {#each CDE_STATE_CHOICES as state}
                  <option value={state}>{state}</option>
                {/each}
              </select>
            </div>

            <div class="space-y-1">
              <label for="topic-suitability" class="block text-[11px] font-semibold text-slate-400">Suitability</label>
              <select
                id="topic-suitability"
                bind:value={suitabilityCode}
                class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
              >
                {#each SUITABILITY_CODES as code}
                  <option value={code}>{code}</option>
                {/each}
              </select>
            </div>

            <div class="space-y-1">
              <label for="topic-revision" class="block text-[11px] font-semibold text-slate-400">Revision Code</label>
              <input
                id="topic-revision"
                type="text"
                bind:value={revisionCode}
                placeholder="P01.01"
                class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#0071e3]"
              />
            </div>
          </div>
        </div>

        <!-- Related Element GUIDs -->
        <div class="space-y-1.5">
          <label for="topic-guids" class="block text-xs font-semibold text-slate-300">
            Linked Element GUIDs (comma separated)
          </label>
          <input
            id="topic-guids"
            type="text"
            bind:value={componentGuidsText}
            placeholder="e.g. 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d, 2b3c4d5e-..."
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs font-mono text-cyan-300 placeholder-slate-600 focus:outline-none focus:border-[#0071e3]"
          />
        </div>
      </div>

      <!-- Footer Actions -->
      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-end gap-2">
        <button
          type="button"
          on:click={onClose}
          class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isSaving}
          on:click={handleSave}
          class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white transition-all disabled:opacity-40"
        >
          {#if isSaving}
            <div class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            <span>Saving...</span>
          {:else}
            <Check class="w-3.5 h-3.5" />
            <span>{isEditing ? 'Save Changes' : 'Create Topic'}</span>
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
