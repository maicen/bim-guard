<script lang="ts">
  import { run } from "svelte/legacy";

  import {
    Check,
    FolderArchive,
    Tag,
    Shield,
    Calendar,
    User,
  } from "lucide-svelte";
  import { bcfApi } from "../api";
  import type { BCFTopicResponse, BCFTopicCreatePayload, BCFTopicUpdatePayload } from "../types";
  import { CDE_STATE_CHOICES, SUITABILITY_CODES } from "../types";
  import { DatePicker, Select, type SelectOption } from "./ui";
  import Alert from "./Alert.svelte";
  import Modal from "./Modal.svelte";
  import { toErrorLogEntry, type ErrorLogEntry } from "../utils/errorLog";

  const typeOptions: SelectOption[] = [
    { value: "Issue", label: "Issue" },
    { value: "Clash / Compliance", label: "Clash / Compliance" },
    { value: "Remark", label: "Remark" },
    { value: "Request", label: "Request" },
  ];
  const statusOptions: SelectOption[] = [
    { value: "Open", label: "Open" },
    { value: "In Progress", label: "In Progress" },
    { value: "Resolved", label: "Resolved" },
    { value: "Closed", label: "Closed" },
  ];
  const priorityOptions: SelectOption[] = [
    { value: "Critical", label: "Critical" },
    { value: "High", label: "High" },
    { value: "Normal", label: "Normal" },
    { value: "Low", label: "Low" },
  ];
  const cdeOptions: SelectOption[] = CDE_STATE_CHOICES.map((s) => ({ value: s, label: s }));
  const suitabilityOptions: SelectOption[] = SUITABILITY_CODES.map((s) => ({ value: s, label: s }));

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
  let errorLog: ErrorLogEntry[] = $state([]);

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
    errorLog = [];

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
      errorLog = [toErrorLogEntry(err, title.trim() || "BCF topic")];
    } finally {
      isSaving = false;
    }
  }
</script>

<Modal
  {isOpen}
  {onClose}
  icon={FolderArchive}
  maxWidth="max-w-2xl"
  title={isEditing ? "Edit BCF Topic" : "Create Live BCF 2.1 Topic"}
  subtitle="buildingSMART BCF standard collaboration issue with ISO 19650 governance."
>
        {#if errorMessage}
          <Alert
            type="error"
            message={errorMessage}
            errors={errorLog}
            logTitle="BCF Topic Save Error Log"
          />
        {/if}

        <!-- Title -->
        <div class="space-y-1.5">
          <label for="topic-title" class="block text-xs font-semibold text-fg-secondary">
            Topic Title <span class="text-rose-400">*</span>
          </label>
          <input
            id="topic-title"
            type="text"
            bind:value={title}
            placeholder="e.g. Non-compliant Door Clear Width at Level 1"
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
          />
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <!-- Type -->
          <div class="space-y-1.5">
            <label for="topic-type" class="block text-xs font-semibold text-fg-secondary">
              Type
            </label>
            <Select options={typeOptions} bind:value={topicType} />
          </div>

          <!-- Status -->
          <div class="space-y-1.5">
            <label for="topic-status" class="block text-xs font-semibold text-fg-secondary">
              Status
            </label>
            <Select options={statusOptions} bind:value={topicStatus} />
          </div>

          <!-- Priority -->
          <div class="space-y-1.5">
            <label for="topic-priority" class="block text-xs font-semibold text-fg-secondary">
              Priority
            </label>
            <Select options={priorityOptions} bind:value={priority} />
          </div>
        </div>

        <!-- Description -->
        <div class="space-y-1.5">
          <label for="topic-desc" class="block text-xs font-semibold text-fg-secondary">
            Description &amp; Findings Note
          </label>
          <textarea
            id="topic-desc"
            bind:value={description}
            rows="3"
            placeholder="Detailed description of the architectural or engineering non-compliance..."
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
          ></textarea>
        </div>

        <!-- Assignee & Due Date -->
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div class="space-y-1.5">
            <label for="topic-assignee" class="block text-xs font-semibold text-fg-secondary">
              Assigned To
            </label>
            <input
              id="topic-assignee"
              type="text"
              bind:value={assignedTo}
              placeholder="e.g. Lead Architect / BIM Coordinator"
              class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
            />
          </div>

          <div class="space-y-1.5">
            <label for="topic-due" class="block text-xs font-semibold text-fg-secondary">
              Due Date
            </label>
            <DatePicker bind:value={dueDate} placeholder="Select due date" />
          </div>
        </div>

        <!-- ISO 19650 Governance Section -->
        <div class="space-y-3 rounded-xl border border-border-default bg-surface-canvas/70 p-4">
          <div
            class="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-fg-secondary"
          >
            <Shield class="h-3.5 w-3.5 text-blue-400" />
            <span>ISO 19650 CDE Governance</span>
          </div>

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div class="space-y-1">
              <label for="topic-cde" class="block text-caption font-semibold text-fg-muted"
                >CDE State</label
              >
              <Select options={cdeOptions} bind:value={cdeState} />
            </div>

            <div class="space-y-1">
              <label for="topic-suitability" class="block text-caption font-semibold text-fg-muted"
                >Suitability</label
              >
              <Select options={suitabilityOptions} bind:value={suitabilityCode} />
            </div>

            <div class="space-y-1">
              <label for="topic-revision" class="block text-caption font-semibold text-fg-muted"
                >Revision Code</label
              >
              <input
                id="topic-revision"
                type="text"
                bind:value={revisionCode}
                placeholder="P01.01"
                class="w-full rounded-lg border border-border-default bg-surface-card px-2.5 py-1.5 font-mono text-xs text-fg-primary focus:border-accent focus:outline-hidden"
              />
            </div>
          </div>
        </div>

        <!-- Related Element GUIDs -->
        <div class="space-y-1.5">
          <label for="topic-guids" class="block text-xs font-semibold text-fg-secondary">
            Linked Element GUIDs (comma separated)
          </label>
          <input
            id="topic-guids"
            type="text"
            bind:value={componentGuidsText}
            placeholder="e.g. 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d, 2b3c4d5e-..."
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2 font-mono text-xs text-cyan-300 placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
          />
        </div>

  {#snippet footer()}
        <button
          type="button"
          onclick={onClose}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
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
  {/snippet}
</Modal>
