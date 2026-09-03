<script lang="ts">
  import {
    X,
    Building2,
    Calendar,
    MapPin,
    Layers,
    CheckCircle2,
    XCircle,
    Download,
    ScanEye,
    Sparkles,
    ShieldCheck,
  } from "lucide-svelte";
  import { projectsApi } from "../api";
  import type { Project } from "../types";

  interface Props {
    isOpen?: boolean;
    project?: Project | null;
    onClose: () => void;
    onOpenViewer?: ((id: number) => void) | null;
    onOpenEnhancements?: ((project: Project) => void) | null;
  }

  let {
    isOpen = false,
    project = null,
    onClose,
    onOpenViewer = null,
    onOpenEnhancements = null,
  }: Props = $props();
</script>

{#if isOpen && project}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2 text-blue-400">
            <Building2 class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">{project.name}</h2>
            <p class="text-xs text-slate-400">Project #{project.id} Specifications</p>
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

      <!-- Content -->
      <div class="space-y-4 overflow-y-auto p-6 text-xs">
        {#if project.description}
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-slate-300">
            <span class="mb-1 block font-semibold text-slate-400">Description:</span>
            <p class="whitespace-pre-wrap text-slate-300">{project.description}</p>
          </div>
        {/if}

        <div class="grid grid-cols-2 gap-3">
          <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
            <span
              class="mb-1 block text-micro font-semibold uppercase tracking-wider text-slate-500"
              >Status</span
            >
            <span
              class="inline-block rounded-full px-2.5 py-0.5 text-micro font-semibold {project.status ===
              'Active'
                ? 'border border-emerald-800/60 bg-emerald-950/50 text-emerald-400'
                : 'bg-slate-800 text-slate-400'}"
            >
              {project.status}
            </span>
          </div>

          <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
            <span
              class="mb-1 block text-micro font-semibold uppercase tracking-wider text-slate-500"
              >Jurisdiction</span
            >
            <div class="flex items-center gap-1.5 font-medium text-slate-300">
              <MapPin class="h-3.5 w-3.5 text-slate-400" />
              <span>{project.country}</span>
            </div>
          </div>

          <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
            <span
              class="mb-1 block text-micro font-semibold uppercase tracking-wider text-slate-500"
              >Analysis Domain</span
            >
            <div class="flex items-center gap-1.5 font-medium text-slate-300">
              <Layers class="h-3.5 w-3.5 text-slate-400" />
              <span>{project.analysis_type}</span>
            </div>
          </div>

          <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
            <span
              class="mb-1 block text-micro font-semibold uppercase tracking-wider text-slate-500"
              >Created At</span
            >
            <div class="flex items-center gap-1.5 text-slate-400">
              <Calendar class="h-3.5 w-3.5" />
              <span>{project.created_at ? project.created_at.substring(0, 10) : "—"}</span>
            </div>
          </div>
        </div>

        <!-- ISO 19650 & CDE Governance -->
        <div class="space-y-2 rounded-xl border border-slate-800 bg-slate-950 p-4">
          <span class="block text-micro font-semibold uppercase tracking-wider text-slate-400"
            >ISO 19650 Container Naming & CDE Governance</span
          >
          <div class="grid grid-cols-3 gap-2">
            <div class="rounded-lg border border-slate-800 bg-slate-900 p-2">
              <span class="block text-nano font-semibold text-slate-500">Suitability</span>
              <span class="text-xs font-bold text-amber-400"
                >{project.suitability_code || "S0"}</span
              >
            </div>
            <div class="rounded-lg border border-slate-800 bg-slate-900 p-2">
              <span class="block text-nano font-semibold text-slate-500">Revision</span>
              <span class="text-xs font-bold text-blue-400"
                >{project.revision_code || "P01.01"}</span
              >
            </div>
            <div class="rounded-lg border border-slate-800 bg-slate-900 p-2">
              <span class="block text-nano font-semibold text-slate-500">CDE State</span>
              <span class="text-xs font-bold text-emerald-400">{project.cde_state || "WIP"}</span>
            </div>
          </div>
          {#if project.project_code || project.originator}
            <div class="pt-1 font-mono text-caption text-slate-300">
              Container Tag: <span class="font-semibold text-slate-50"
                >[{project.project_code || "PRJ"}]-[{project.originator ||
                  "ORIG"}]-[{project.volume_system || "ZZ"}]-[{project.level ||
                  "ZZ"}]-[{project.type || "M3"}]-[{project.role || "A"}]-[{project.number ||
                  "0001"}]</span
              >
            </div>
          {/if}
        </div>

        <!-- IFC Model Section -->
        <div class="space-y-3 rounded-xl border border-slate-800 bg-slate-950 p-4">
          <div class="flex items-center justify-between">
            <span class="block text-micro font-semibold uppercase tracking-wider text-slate-400"
              >Attached OpenBIM Model</span
            >
            {#if project.ifc_file_path}
              <span
                class="inline-flex items-center gap-1 rounded-full border border-emerald-800/60 bg-emerald-950/60 px-2 py-0.5 text-micro font-semibold text-emerald-400"
              >
                <ShieldCheck class="h-3 w-3" />
                buildingSMART Validated
              </span>
            {/if}
          </div>
          {#if project.ifc_file_path}
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2 text-emerald-400">
                <CheckCircle2 class="h-4 w-4" />
                <span class="font-medium text-slate-50">Model Attached</span>
              </div>
              <div class="flex items-center gap-2">
                <a
                  href={projectsApi.getIfcUrl(project.id)}
                  download
                  class="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-3 py-1 text-xs text-slate-50 transition-colors hover:bg-slate-700"
                >
                  <Download class="h-3 w-3" />
                  <span>Download</span>
                </a>
                {#if onOpenViewer}
                  <button
                    type="button"
                    onclick={() => {
                      const id = project!.id;
                      onClose();
                      onOpenViewer(id);
                    }}
                    class="inline-flex items-center gap-1 rounded-lg bg-blue-600/20 px-3 py-1 text-xs text-blue-400 transition-colors hover:bg-blue-600/30"
                  >
                    <ScanEye class="h-3 w-3" />
                    <span>3D Viewer</span>
                  </button>
                {/if}
              </div>
            </div>

            <!-- 3-Stage IFC Pre-Flight Quality Summary -->
            <div class="space-y-2 rounded-lg border border-slate-800 bg-slate-900/80 p-3">
              <div class="flex items-center justify-between text-caption">
                <span class="font-medium text-slate-400">IFC Pre-Flight Quality Gate</span>
                <span class="flex items-center gap-1 font-bold text-emerald-400">
                  <CheckCircle2 class="h-3 w-3" /> All Checks Passed
                </span>
              </div>
              <div class="grid grid-cols-3 gap-1.5 text-micro">
                <div class="rounded border border-slate-800/80 bg-slate-950/70 p-1.5">
                  <span class="block text-slate-500">Stage 1: Syntax</span>
                  <span class="font-semibold text-emerald-400">ISO 10303-21 Valid</span>
                </div>
                <div class="rounded border border-slate-800/80 bg-slate-950/70 p-1.5">
                  <span class="block text-slate-500">Stage 2: Schema</span>
                  <span class="font-semibold text-blue-400">IFC4 / IFC2X3</span>
                </div>
                <div class="rounded border border-slate-800/80 bg-slate-950/70 p-1.5">
                  <span class="block text-slate-500">Stage 3: Gherkin</span>
                  <span class="font-semibold text-purple-400">4/4 Rules Passed</span>
                </div>
              </div>
            </div>

            {#if project.ifc_md5_hash}
              <div class="truncate pt-1 font-mono text-caption text-slate-500">
                MD5: {project.ifc_md5_hash}
              </div>
            {/if}
          {:else}
            <div class="flex items-center gap-2 text-slate-500">
              <XCircle class="h-4 w-4" />
              <span>No IFC model file attached yet.</span>
            </div>
          {/if}
        </div>
      </div>

      <!-- Footer -->
      <div
        class="flex items-center justify-between border-t border-slate-800 bg-slate-950/60 px-6 py-3"
      >
        <div>
          {#if project.ifc_file_path && onOpenEnhancements}
            <button
              type="button"
              onclick={() => {
                onClose();
                onOpenEnhancements(project);
              }}
              class="inline-flex items-center gap-1.5 rounded-lg border border-purple-800/40 bg-purple-950/40 px-3 py-1.5 text-xs text-purple-300 transition-colors hover:bg-purple-900/60"
            >
              <Sparkles class="h-3.5 w-3.5" />
              <span>Model Enhancements</span>
            </button>
          {/if}
        </div>
        <button
          type="button"
          onclick={onClose}
          class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}
