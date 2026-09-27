<script lang="ts">
  import {
    ScanEye,
    Boxes,
    GitBranch,
    Lock,
    Building2,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    Share2,
  } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    url?: string;
    class?: string;
  }

  let {
    url = "https://bim-guard.xyz/arch/audit",
    class: className,
  }: Props = $props();
</script>

<div class={cn("relative rounded-2xl border border-border-default bg-surface-card shadow-2xl overflow-hidden", className)}>
  <!-- Window Header / Chrome -->
  <div class="flex items-center justify-between border-b border-border-subtle bg-surface-overlay/80 px-4 py-3">
    <div class="flex items-center gap-2">
      <div class="h-3 w-3 rounded-full bg-rose-500/80"></div>
      <div class="h-3 w-3 rounded-full bg-amber-500/80"></div>
      <div class="h-3 w-3 rounded-full bg-emerald-500/80"></div>
      <span class="ml-2 text-micro font-mono text-fg-muted hidden sm:inline-block">
        BIM-Guard Workstation — Level 02 Architectural Audit
      </span>
    </div>
    <div class="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-canvas/60 px-3 py-1 text-micro font-mono text-fg-secondary">
      <Lock class="h-3 w-3 text-emerald-400" />
      <span>{url}</span>
    </div>
    <div class="flex items-center gap-2 text-micro text-fg-muted font-medium">
      <span class="inline-flex items-center gap-1 rounded bg-success-bg px-1.5 py-0.5 text-success font-semibold border border-success-border">
        CDE: SHARED
      </span>
    </div>
  </div>

  <!-- App Content Grid -->
  <div class="grid grid-cols-1 lg:grid-cols-12 min-h-[420px] bg-surface-canvas/90">
    <!-- Sidebar Miniature -->
    <div class="hidden lg:flex lg:col-span-3 flex-col border-r border-border-subtle bg-surface-card/40 p-4 justify-between">
      <div class="space-y-4">
        <div class="flex items-center gap-2 px-2 text-xs font-bold text-fg-primary">
          <Building2 class="h-4 w-4 text-accent" />
          <span>Hospital Wing C — IFC4</span>
        </div>
        <div class="space-y-1">
          <div class="flex items-center justify-between rounded-lg bg-surface-selected px-3 py-2 text-xs font-semibold text-accent">
            <span class="flex items-center gap-2">
              <ScanEye class="h-3.5 w-3.5" />
              Architectural Audit
            </span>
            <span class="text-micro font-mono">LIVE</span>
          </div>
          <div class="flex items-center justify-between rounded-lg px-3 py-2 text-xs text-fg-secondary hover:bg-surface-hover">
            <span class="flex items-center gap-2">
              <Boxes class="h-3.5 w-3.5 text-fg-muted" />
              IFC Models (2)
            </span>
            <span class="text-micro text-fg-muted">Primary</span>
          </div>
          <div class="flex items-center justify-between rounded-lg px-3 py-2 text-xs text-fg-secondary hover:bg-surface-hover">
            <span class="flex items-center gap-2">
              <GitBranch class="h-3.5 w-3.5 text-fg-muted" />
              BCF Topics
            </span>
            <span class="rounded-full bg-critical-bg text-critical px-1.5 py-0.2 text-nano font-bold">3 Issues</span>
          </div>
        </div>
      </div>

      <!-- ISO Governance Card in Mini-sidebar -->
      <div class="rounded-xl border border-border-subtle bg-surface-card p-3 space-y-1.5 text-micro">
        <div class="flex items-center justify-between text-fg-muted">
          <span>Suitability</span>
          <span class="font-bold text-fg-primary">S2 (Information)</span>
        </div>
        <div class="flex items-center justify-between text-fg-muted">
          <span>Revision</span>
          <span class="font-mono text-fg-primary">P02.01</span>
        </div>
        <div class="flex items-center justify-between text-fg-muted">
          <span>Originator</span>
          <span class="font-bold text-accent">ARCH-CORP</span>
        </div>
      </div>
    </div>

    <!-- Central 3D Viewport Simulator -->
    <div class="lg:col-span-6 relative flex flex-col items-center justify-center p-6 border-b lg:border-b-0 lg:border-r border-border-subtle bg-surface-canvas overflow-hidden">
      <!-- Grid Background Lines -->
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,var(--color-surface-card)_1px,transparent_1px)] bg-[size:16px_16px] opacity-60"></div>

      <!-- 3D Isometric BIM Mockup Graphic -->
      <div class="relative z-10 w-full max-w-sm aspect-4/3 rounded-xl border border-border-interactive bg-surface-card/60 p-5 flex flex-col justify-between shadow-inner backdrop-blur-xs">
        <div class="flex items-center justify-between text-xs">
          <span class="font-mono text-fg-muted flex items-center gap-1.5">
            <span class="h-2 w-2 rounded-full bg-accent animate-ping"></span>
            Egress Engine Active
          </span>
          <span class="text-nano rounded-md bg-surface-overlay px-2 py-0.5 font-semibold text-fg-secondary">
            Orbit 3D
          </span>
        </div>

        <!-- Schematic Room / Door Audit Visual -->
        <div class="my-auto relative flex items-center justify-center">
          <div class="w-48 h-28 border-2 border-dashed border-accent/40 rounded-lg flex items-center justify-center relative">
            <span class="text-micro font-semibold text-accent/80 uppercase tracking-widest">Corridor 204</span>
            
            <!-- Egress Passage Indicator -->
            <div class="absolute inset-x-4 top-1/2 -translate-y-1/2 h-0.5 bg-accent/60"></div>
            
            <!-- Issue Pin 1 -->
            <div class="absolute -top-3 left-6 flex items-center gap-1 rounded-md border border-critical-border bg-critical-bg px-2 py-0.5 text-nano font-bold text-critical shadow-sm">
              <XCircle class="h-3 w-3" />
              <span>Door Clear Width: 780mm (Req: ≥850mm)</span>
            </div>

            <!-- Pass Pin 2 -->
            <div class="absolute -bottom-3 right-6 flex items-center gap-1 rounded-md border border-success-border bg-success-bg px-2 py-0.5 text-nano font-bold text-success shadow-sm">
              <CheckCircle2 class="h-3 w-3" />
              <span>Exit Travel Distance: 18.4m [PASS]</span>
            </div>
          </div>
        </div>

        <div class="flex items-center justify-between text-micro text-fg-muted pt-2 border-t border-border-subtle">
          <span>IfcDoor #104928</span>
          <span class="font-mono text-fg-secondary">GlobalId: 2O2D_X$5v18wv</span>
        </div>
      </div>
    </div>

    <!-- Right Results Panel -->
    <div class="lg:col-span-3 flex flex-col p-4 bg-surface-card/30 space-y-3 justify-between">
      <div>
        <div class="flex items-center justify-between pb-2 border-b border-border-subtle">
          <span class="text-xs font-bold text-fg-primary">Compliance Findings</span>
          <span class="text-nano font-mono text-fg-muted">14 Rules Checked</span>
        </div>

        <div class="mt-3 space-y-2">
          <div class="rounded-xl border border-critical-border bg-critical-bg p-2.5 space-y-1">
            <div class="flex items-center justify-between text-nano font-bold text-critical">
              <span class="flex items-center gap-1"><XCircle class="h-3 w-3" /> ARCH-EGRESS-001</span>
              <span class="rounded bg-rose-500/20 px-1">CRITICAL</span>
            </div>
            <p class="text-micro text-fg-secondary leading-snug">Door clearance width fails NBC 3.3.1.13 minimum cutoff.</p>
          </div>

          <div class="rounded-xl border border-success-border bg-success-bg p-2.5 space-y-1">
            <div class="flex items-center justify-between text-nano font-bold text-success">
              <span class="flex items-center gap-1"><CheckCircle2 class="h-3 w-3" /> ARCH-SPATIAL-001</span>
              <span class="rounded bg-emerald-500/20 px-1">PASS</span>
            </div>
            <p class="text-micro text-fg-secondary leading-snug">Corridor exit separations meet 2-hour fire barrier requirement.</p>
          </div>

          <div class="rounded-xl border border-warning-border bg-warning-bg p-2.5 space-y-1">
            <div class="flex items-center justify-between text-nano font-bold text-warning">
              <span class="flex items-center gap-1"><AlertTriangle class="h-3 w-3" /> bSDD-PROP-004</span>
              <span class="rounded bg-amber-500/20 px-1">CAUTION</span>
            </div>
            <p class="text-micro text-fg-secondary leading-snug">Pset_DoorCommon acoustic rating missing standard dictionary URI.</p>
          </div>
        </div>
      </div>

      <!-- One-click BCF Export CTA in mockup -->
      <div class="pt-2 border-t border-border-subtle">
        <button
          type="button"
          class="w-full flex items-center justify-center gap-1.5 rounded-lg bg-surface-overlay border border-border-interactive py-1.5 text-xs font-semibold text-fg-primary hover:bg-surface-hover transition-colors"
        >
          <Share2 class="h-3 w-3 text-accent" />
          <span>Sync BCF Topics to Revit</span>
        </button>
      </div>
    </div>
  </div>
</div>
