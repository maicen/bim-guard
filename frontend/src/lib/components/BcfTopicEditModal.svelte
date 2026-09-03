<script lang="ts">
  import { run } from "svelte/legacy";

  import {
    X,
    Check,
    FolderArchive,
    AlertTriangle,
    Tag,
    Shield,
    Calendar,
    User,
  } from "lucide-svelte";
  import { bcfApi } from "../api";
  import type { BCFTopicResponse, BCFTopicCreatePayload, BCFTopicUpdatePayload } from "../types";
  import { CDE_STATE_CHOICES, SUITABILITY_CODES } from "../types";

  interface Props {
    isOpen?: boolean;
    projectId: number | string;
    topicToEdit?: BCFTopicResponse | null;
    onClose: () => void;
    onSaved: (topic: BCFTopicResponse) => void;
  }

  let { isOpen = false, projectId, topicToEdit = null, onClose, onSaved }: Props = $props();

  let title = $state("");
  let topicType = $state("Issue");
  let topicStatus = $state("Open");
  let priority = $state("Normal");
  let description = $state("");
  let assignedTo = $state("");
  let dueDate = $state("");
  let suitabilityCode = $state("S0");
  let revisionCode = $state("P01.01");
  let cdeState: any = $state("WIP");
  let componentGuidsText = $state("");

  let isSaving = $state(false);
  let errorMessage = $state("");

  let isEditing = $derived(!!topicToEdit);

  run(() => {
    if (isOpen) {
      errorMessage = "";
      if (topicToEdit) {
        title = topicToEdit.title || "";
        topicType = topicToEdit.topic_type || "Issue";
        topicStatus = topicToEdit.topic_status || "Open";
        priority = topicToEdit.priority || "Normal";
        description = topicToEdit.description || "";
        assignedTo = topicToEdit.assigned_to || "";
        dueDate = topicToEdit.due_date || "";
        suitabilityCode = topicToEdit.suitability_code || "S0";
        revisionCode = topicToEdit.revision_code || "P01.01";
        cdeState = topicToEdit.cde_state || "WIP";
        componentGuidsText = (topicToEdit.component_guids || []).join(", ");
      } else {
        title = "";
        topicType = "Clash / Compliance";
        topicStatus = "Open";
        priority = "Normal";
        description = "";
        assignedTo = "BIM Coordinator";
        dueDate = "";
        suitabilityCode = "S0";
        revisionCode = "P01.01";
        cdeState = "WIP";
        componentGuidsText = "";
      }
    }
  });

  async function handleSave() {
    if (!title.trim()) {
      errorMessage = "Topic title is required.";
      return;
    }

    isSaving = true;
    errorMessage = "";

    const guids = componentGuidsText
      .split(",")
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
      errorMessage = err.message || "Failed to save BCF topic.";
    } finally {
      isSaving = false;
    }
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2 text-blue-400">
            <FolderArchive class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">
              {isEditing ? "Edit BCF Topic" : "Create Live BCF 2.1 Topic"}
            </h2>
            <p class="text-xs text-slate-400">
              buildingSMART BCF standard collaboration issue with ISO 19650 governance.
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={onClose}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Form Body -->
      <div class="space-y-4 overflow-y-auto p-6">
        {#if errorMessage}
          <div
            class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300"
          >
            <AlertTriangle class="h-4 w-4 shrink-0 text-rose-400" />
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
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          />
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <!-- Type -->
          <div class="space-y-1.5">
            <label for="topic-type" class="block text-xs font-semibold text-slate-300">
              Type
            </label>
            <select
              id="topic-type"
              bind:value={topicType}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          ></textarea>
        </div>

        <!-- Assignee & Due Date -->
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div class="space-y-1.5">
            <label for="topic-assignee" class="block text-xs font-semibold text-slate-300">
              Assigned To
            </label>
            <input
              id="topic-assignee"
              type="text"
              bind:value={assignedTo}
              placeholder="e.g. Lead Architect / BIM Coordinator"
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
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
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        <!-- ISO 19650 Governance Section -->
        <div class="space-y-3 rounded-xl border border-slate-800 bg-slate-950/70 p-4">
          <div
            class="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-300"
          >
            <Shield class="h-3.5 w-3.5 text-blue-400" />
            <span>ISO 19650 CDE Governance</span>
          </div>

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div class="space-y-1">
              <label for="topic-cde" class="block text-caption font-semibold text-slate-400"
                >CDE State</label
              >
              <select
                id="topic-cde"
                bind:value={cdeState}
                class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
              >
                {#each CDE_STATE_CHOICES as state}
                  <option value={state}>{state}</option>
                {/each}
              </select>
            </div>

            <div class="space-y-1">
              <label for="topic-suitability" class="block text-caption font-semibold text-slate-400"
                >Suitability</label
              >
              <select
                id="topic-suitability"
                bind:value={suitabilityCode}
                class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
              >
                {#each SUITABILITY_CODES as code}
                  <option value={code}>{code}</option>
                {/each}
              </select>
            </div>

            <div class="space-y-1">
              <label for="topic-revision" class="block text-caption font-semibold text-slate-400"
                >Revision Code</label
              >
              <input
                id="topic-revision"
                type="text"
                bind:value={revisionCode}
                placeholder="P01.01"
                class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 font-mono text-xs text-slate-50 focus:border-accent focus:outline-none"
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
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 font-mono text-xs text-cyan-300 placeholder-slate-600 focus:border-accent focus:outline-none"
          />
        </div>
      </div>

      <!-- Footer Actions -->
      <div
        class="flex items-center justify-end gap-2 border-t border-slate-800 bg-slate-950/60 px-6 py-3"
      >
        <button
          type="button"
          onclick={onClose}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isSaving}
          onclick={handleSave}
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white transition-all hover:bg-accent-hover disabled:opacity-40"
        >
          {#if isSaving}
            <div
              class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white"
            ></div>
            <span>Saving...</span>
          {:else}
            <Check class="h-3.5 w-3.5" />
            <span>{isEditing ? "Save Changes" : "Create Topic"}</span>
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
