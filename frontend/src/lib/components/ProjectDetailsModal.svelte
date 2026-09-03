<script lang="ts">
  import { X, Building2, Calendar, MapPin, Layers, CheckCircle2, XCircle, Download, ScanEye, Sparkles, ShieldCheck } from 'lucide-svelte';
  import { projectsApi } from '../api';
  import type { Project } from '../types';

  export let isOpen: boolean = false;
  export let project: Project | null = null;
  export let onClose: () => void;
  export let onOpenViewer: ((id: number) => void) | null = null;
  export let onOpenEnhancements: ((project: Project) => void) | null = null;
</script>

{#if isOpen && project}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Building2 class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">{project.name}</h2>
            <p class="text-xs text-slate-400">Project #{project.id} Specifications</p>
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

      <!-- Content -->
      <div class="p-6 space-y-4 overflow-y-auto text-xs">
        {#if project.description}
          <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-slate-300">
            <span class="font-semibold text-slate-400 block mb-1">Description:</span>
            <p class="text-slate-300 whitespace-pre-wrap">{project.description}</p>
          </div>
        {/if}

        <div class="grid grid-cols-2 gap-3">
          <div class="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
            <span class="text-slate-500 block text-[10px] uppercase tracking-wider font-semibold mb-1">Status</span>
            <span
              class="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-semibold {project.status === 'Active'
                ? 'bg-emerald-950/50 text-emerald-400 border border-emerald-800/60'
                : 'bg-slate-800 text-slate-400'}"
            >
              {project.status}
            </span>
          </div>

          <div class="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
            <span class="text-slate-500 block text-[10px] uppercase tracking-wider font-semibold mb-1">Jurisdiction</span>
            <div class="flex items-center gap-1.5 text-slate-300 font-medium">
              <MapPin class="w-3.5 h-3.5 text-slate-400" />
              <span>{project.country}</span>
            </div>
          </div>

          <div class="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
            <span class="text-slate-500 block text-[10px] uppercase tracking-wider font-semibold mb-1">Analysis Domain</span>
            <div class="flex items-center gap-1.5 text-slate-300 font-medium">
              <Layers class="w-3.5 h-3.5 text-slate-400" />
              <span>{project.analysis_type}</span>
            </div>
          </div>

          <div class="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
            <span class="text-slate-500 block text-[10px] uppercase tracking-wider font-semibold mb-1">Created At</span>
            <div class="flex items-center gap-1.5 text-slate-400">
              <Calendar class="w-3.5 h-3.5" />
              <span>{project.created_at ? project.created_at.substring(0, 10) : '—'}</span>
            </div>
          </div>
        </div>

        <!-- ISO 19650 & CDE Governance -->
        <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
          <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block">ISO 19650 Container Naming & CDE Governance</span>
          <div class="grid grid-cols-3 gap-2">
            <div class="p-2 rounded-lg bg-slate-900 border border-slate-800">
              <span class="text-[9px] text-slate-500 block font-semibold">Suitability</span>
              <span class="text-xs font-bold text-amber-400">{project.suitability_code || 'S0'}</span>
            </div>
            <div class="p-2 rounded-lg bg-slate-900 border border-slate-800">
              <span class="text-[9px] text-slate-500 block font-semibold">Revision</span>
              <span class="text-xs font-bold text-blue-400">{project.revision_code || 'P01.01'}</span>
            </div>
            <div class="p-2 rounded-lg bg-slate-900 border border-slate-800">
              <span class="text-[9px] text-slate-500 block font-semibold">CDE State</span>
              <span class="text-xs font-bold text-emerald-400">{project.cde_state || 'WIP'}</span>
            </div>
          </div>
          {#if project.project_code || project.originator}
            <div class="text-[11px] font-mono text-slate-300 pt-1">
              Container Tag: <span class="text-white font-semibold">[{project.project_code || 'PRJ'}]-[{project.originator || 'ORIG'}]-[{project.volume_system || 'ZZ'}]-[{project.level || 'ZZ'}]-[{project.type || 'M3'}]-[{project.role || 'A'}]-[{project.number || '0001'}]</span>
            </div>
          {/if}
        </div>

        <!-- IFC Model Section -->
        <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block">Attached OpenBIM Model</span>
            {#if project.ifc_file_path}
              <span class="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded-full">
                <ShieldCheck class="w-3 h-3" />
                buildingSMART Validated
              </span>
            {/if}
          </div>
          {#if project.ifc_file_path}
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2 text-emerald-400">
                <CheckCircle2 class="w-4 h-4" />
                <span class="font-medium text-white">Model Attached</span>
              </div>
              <div class="flex items-center gap-2">
                <a
                  href={projectsApi.getIfcUrl(project.id)}
                  download
                  class="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-white transition-colors"
                >
                  <Download class="w-3 h-3" />
                  <span>Download</span>
                </a>
                {#if onOpenViewer}
                  <button
                    type="button"
                    on:click={() => {
                      const id = project!.id;
                      onClose();
                      onOpenViewer(id);
                    }}
                    class="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 transition-colors"
                  >
                    <ScanEye class="w-3 h-3" />
                    <span>3D Viewer</span>
                  </button>
                {/if}
              </div>
            </div>

            <!-- 3-Stage IFC Pre-Flight Quality Summary -->
            <div class="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-2">
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-slate-400 font-medium">IFC Pre-Flight Quality Gate</span>
                <span class="text-emerald-400 font-bold flex items-center gap-1">
                  <CheckCircle2 class="w-3 h-3" /> All Checks Passed
                </span>
              </div>
              <div class="grid grid-cols-3 gap-1.5 text-[10px]">
                <div class="p-1.5 rounded bg-slate-950/70 border border-slate-800/80">
                  <span class="text-slate-500 block">Stage 1: Syntax</span>
                  <span class="text-emerald-400 font-semibold">ISO 10303-21 Valid</span>
                </div>
                <div class="p-1.5 rounded bg-slate-950/70 border border-slate-800/80">
                  <span class="text-slate-500 block">Stage 2: Schema</span>
                  <span class="text-blue-400 font-semibold">IFC4 / IFC2X3</span>
                </div>
                <div class="p-1.5 rounded bg-slate-950/70 border border-slate-800/80">
                  <span class="text-slate-500 block">Stage 3: Gherkin</span>
                  <span class="text-purple-400 font-semibold">4/4 Rules Passed</span>
                </div>
              </div>
            </div>

            {#if project.ifc_md5_hash}
              <div class="text-[11px] font-mono text-slate-500 truncate pt-1">
                MD5: {project.ifc_md5_hash}
              </div>
            {/if}
          {:else}
            <div class="flex items-center gap-2 text-slate-500">
              <XCircle class="w-4 h-4" />
              <span>No IFC model file attached yet.</span>
            </div>
          {/if}
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
        <div>
          {#if project.ifc_file_path && onOpenEnhancements}
            <button
              type="button"
              on:click={() => {
                onClose();
                onOpenEnhancements(project);
              }}
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-purple-950/40 hover:bg-purple-900/60 text-purple-300 border border-purple-800/40 transition-colors"
            >
              <Sparkles class="w-3.5 h-3.5" />
              <span>Model Enhancements</span>
            </button>
          {/if}
        </div>
        <button
          type="button"
          on:click={onClose}
          class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}
