<script lang="ts">
  import {
    Boxes,
    FileText,
    RefreshCw,
    Cpu,
    ScanEye,
    GitBranch,
    ShieldCheck,
  } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    class?: string;
  }

  let { class: className }: Props = $props();
</script>

<div class={cn("grid grid-cols-1 md:grid-cols-3 gap-6 items-center", className)}>
  <!-- Column 1: Ingestion Sources -->
  <div class="space-y-4">
    <div class="rounded-2xl border border-border-default bg-surface-card p-5 text-left transition-all hover:border-border-interactive">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10 text-accent shrink-0">
          <Boxes class="h-5 w-5" />
        </div>
        <div>
          <h3 class="text-sm font-bold text-fg-primary">IFC 3D Models</h3>
          <p class="text-micro text-fg-muted">IFC2X3, IFC4 & IFC4X3 schema models</p>
        </div>
      </div>
    </div>

    <div class="rounded-2xl border border-border-default bg-surface-card p-5 text-left transition-all hover:border-border-interactive">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 shrink-0">
          <FileText class="h-5 w-5" />
        </div>
        <div>
          <h3 class="text-sm font-bold text-fg-primary">Building Codes (PDF)</h3>
          <p class="text-micro text-fg-muted">Docling AI table & clause extraction</p>
        </div>
      </div>
    </div>

    <div class="rounded-2xl border border-border-default bg-surface-card p-5 text-left transition-all hover:border-border-interactive">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-400 shrink-0">
          <RefreshCw class="h-5 w-5" />
        </div>
        <div>
          <h3 class="text-sm font-bold text-fg-primary">Revit Direct Connector</h3>
          <p class="text-micro text-fg-muted">Bi-directional parameter sync</p>
        </div>
      </div>
    </div>
  </div>

  <!-- Column 2: Central Processing Core -->
  <div class="relative flex flex-col items-center justify-center p-6 rounded-3xl border-2 border-accent/40 bg-surface-card shadow-xl shadow-accent/5">
    <div class="absolute -inset-1 rounded-3xl bg-accent/10 blur-xl pointer-events-none"></div>

    <div class="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-linear-to-tr from-accent to-cyan-400 text-white shadow-lg shadow-blue-500/30 mb-4">
      <Cpu class="h-8 w-8 animate-pulse" />
    </div>

    <h3 class="text-base font-bold text-fg-primary">BIM-Guard Pipeline</h3>
    <p class="text-micro text-fg-muted text-center mt-1">Multi-stage compliance orchestrator</p>

    <div class="mt-4 w-full space-y-1.5 text-micro font-mono">
      <div class="flex items-center justify-between rounded-lg bg-surface-overlay px-3 py-1.5 text-fg-secondary">
        <span>1. Model Validation</span>
        <span class="text-emerald-400 font-bold">SHA-256</span>
      </div>
      <div class="flex items-center justify-between rounded-lg bg-surface-overlay px-3 py-1.5 text-fg-secondary">
        <span>2. Element Extraction</span>
        <span class="text-cyan-400 font-bold">IfcOpenShell</span>
      </div>
      <div class="flex items-center justify-between rounded-lg bg-surface-overlay px-3 py-1.5 text-fg-secondary">
        <span>3. Egress & Spatial Checks</span>
        <span class="text-accent font-bold">Python Kernels</span>
      </div>
      <div class="flex items-center justify-between rounded-lg bg-surface-overlay px-3 py-1.5 text-fg-secondary">
        <span>4. SSE Event Stream</span>
        <span class="text-purple-400 font-bold">/api/events</span>
      </div>
    </div>
  </div>

  <!-- Column 3: Output Deliverables -->
  <div class="space-y-4">
    <div class="rounded-2xl border border-border-default bg-surface-card p-5 text-left transition-all hover:border-border-interactive">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 shrink-0">
          <ScanEye class="h-5 w-5" />
        </div>
        <div>
          <h3 class="text-sm font-bold text-fg-primary">3D Viewport Findings</h3>
          <p class="text-micro text-fg-muted">Isolated element bounding boxes</p>
        </div>
      </div>
    </div>

    <div class="rounded-2xl border border-border-default bg-surface-card p-5 text-left transition-all hover:border-border-interactive">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 shrink-0">
          <GitBranch class="h-5 w-5" />
        </div>
        <div>
          <h3 class="text-sm font-bold text-fg-primary">BCF 2.1 Coordination</h3>
          <p class="text-micro text-fg-muted">Standard viewpoints & author comments</p>
        </div>
      </div>
    </div>

    <div class="rounded-2xl border border-border-default bg-surface-card p-5 text-left transition-all hover:border-border-interactive">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 shrink-0">
          <ShieldCheck class="h-5 w-5" />
        </div>
        <div>
          <h3 class="text-sm font-bold text-fg-primary">ISO 19650 Reports</h3>
          <p class="text-micro text-fg-muted">Immutable audit logs & certificates</p>
        </div>
      </div>
    </div>
  </div>
</div>
