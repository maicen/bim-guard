<script lang="ts">
  import { link, push } from "svelte-spa-router";
  import {
    ShieldCheck,
    ScanEye,
    GitBranch,
    Workflow,
    Building2,
    ArrowRight,
    CheckCircle2,
    Database,
    Sparkles,
    FileCode2,
  } from "lucide-svelte";
  import { Button } from "../lib/components/ui";
  import Marquee from "../lib/components/marketing/Marquee.svelte";
  import HeroAppMockup from "../lib/components/marketing/HeroAppMockup.svelte";
  import PipelineFlow from "../lib/components/marketing/PipelineFlow.svelte";
  import ComparisonTable, { type ComparisonRow } from "../lib/components/marketing/ComparisonTable.svelte";
  import FaqAccordion, { type FaqItem } from "../lib/components/marketing/FaqAccordion.svelte";
  import LandingNav from "../lib/components/marketing/LandingNav.svelte";

  // Standards Marquee Data
  const STANDARDS = [
    { name: "buildingSMART International", tag: "Official Member", color: "text-accent" },
    { name: "IFC 2x3 & IFC4", tag: "ISO 16739-1", color: "text-info" },
    { name: "bSDD Dictionary", tag: "Semantic Lookup", color: "text-warning" },
    { name: "BCF 2.1 XML / API", tag: "Coordination", color: "text-success" },
    { name: "ISO 19650 Governance", tag: "CDE Lifecycle", color: "text-accent" },
    { name: "OpenCDE Documents API", tag: "BIM Interop", color: "text-info" },
    { name: "Docling AI Engine", tag: "PDF Extraction", color: "text-purple-400" },
    { name: "Autodesk Revit Sync", tag: "Direct Connector", color: "text-cyan-400" },
  ];

  // Comparison Matrix Data
  const COMPARISONS: ComparisonRow[] = [
    {
      feature: "Cloud-native, zero-install 3D viewer",
      manual: false,
      desktop: false,
      bimguard: true,
      note: "Instant browser access across Mac, Windows, Linux, and mobile",
    },
    {
      feature: "Dynamic database-driven compliance rules",
      manual: false,
      desktop: "Scripted / Hardcoded",
      bimguard: true,
      note: "No re-compilation needed when local building codes change",
    },
    {
      feature: "ISO 19650 CDE State Machine enforcement",
      manual: "Spreadsheets",
      desktop: false,
      bimguard: true,
      note: "WIP → SHARED → PUBLISHED → ARCHIVED state transitions enforced at DB level",
    },
    {
      feature: "Automated BCF 2.1 issue generation & sync",
      manual: false,
      desktop: "Manual Export",
      bimguard: true,
      note: "Directly routes code violations with camera viewpoints into Revit and Solibri",
    },
    {
      feature: "bSDD semantic classification enrichment",
      manual: false,
      desktop: "Add-on plugin",
      bimguard: true,
      note: "Validates element properties against buildingSMART international dictionary",
    },
    {
      feature: "AI regulation clause extraction (Docling)",
      manual: false,
      desktop: false,
      bimguard: true,
      note: "Transforms raw building code PDFs into executable machine-checked rules",
    },
  ];

  // FAQ items
  const FAQS: FaqItem[] = [
    {
      id: "faq-1",
      question: "Which IFC schemas and model formats are supported?",
      answer:
        "BIM-Guard supports all standard OpenBIM formats including IFC2X3, IFC4, and IFC4X3, validated via IfcOpenShell. Models exported from Autodesk Revit, ARCHICAD, Vectorworks, and Tekla Structures are fully compatible.",
    },
    {
      id: "faq-2",
      question: "How does the compliance engine check building regulations?",
      answer:
        "Unlike legacy tools with hardcoded cutoffs, BIM-Guard evaluates architectural models dynamically against rule parameters stored in the database. Engines like ARCH-EGRESS-001 (corridor widths, exit capacities, travel distances) and ARCH-SPATIAL-001 (fire separation, clearance envelopes) compute spatial queries in pure Python.",
    },
    {
      id: "faq-3",
      question: "What is the ISO 19650 Common Data Environment (CDE) state machine?",
      answer:
        "Every project, model, and document entity carries mandatory ISO 19650 metadata (originator, volume, level, type, suitability, revision). BIM-Guard's state machine enforces valid state transitions (WIP → SHARED → PUBLISHED → ARCHIVED) and prevents unapproved assets from being audited or released.",
    },
    {
      id: "faq-4",
      question: "How do findings route back to design teams?",
      answer:
        "Findings are compiled directly into BCF 2.1 (BIM Collaboration Format) topics with camera viewpoints, component GlobalIDs, and severity ratings. Design teams can download standard BCF zip archives or synchronize live with our Revit connector and OpenCDE API endpoints.",
    },
    {
      id: "faq-5",
      question: "Can our organization self-host BIM-Guard?",
      answer:
        "Yes. The entire platform runs on Docker Compose with OrbStack, self-hosted Docling parsing engines, Neo4j graph databases, and Cloudflare Tunnel integration for zero-trust private network deployments.",
    },
  ];
</script>

<div class="min-h-screen bg-surface-canvas font-sans text-fg-primary antialiased selection:bg-accent selection:text-white">
  <!-- Top Navigation Header -->
  <header class="sticky top-0 z-40 border-b border-border-subtle bg-surface-canvas/80 backdrop-blur-md">
    <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
      <div class="flex items-center gap-3">
        <a href="/" use:link class="flex items-center gap-2.5 outline-hidden group">
          <div
            class="flex h-9 w-9 items-center justify-center rounded-xl bg-linear-to-tr from-accent to-cyan-400 text-sm font-bold text-white shadow-md shadow-blue-500/20 transition-transform group-hover:scale-105"
          >
            BG
          </div>
          <div class="flex flex-col">
            <span class="text-base font-bold leading-none tracking-tight text-fg-primary">BIM Guard</span>
            <span class="text-nano font-semibold uppercase tracking-widest text-fg-muted mt-0.5"
              >OpenBIM Compliance</span
            >
          </div>
        </a>
      </div>

      <LandingNav class="hidden md:flex" />

      <div class="flex items-center gap-3">
        <Button variant="ghost" size="sm" onclick={() => push("/login")}>
          Sign in
        </Button>
        <Button variant="primary" size="sm" onclick={() => push("/login")}>
          Get started
          <ArrowRight class="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  </header>

  <main>
    <!-- Hero Section -->
    <section class="relative overflow-hidden pt-12 pb-20 md:pt-20 md:pb-28">
      <!-- Ambient Glow Backdrop -->
      <div class="pointer-events-none absolute inset-x-0 top-0 -z-10 flex justify-center overflow-hidden">
        <div class="h-[450px] w-[800px] rounded-full bg-accent/15 blur-[120px]"></div>
        <div class="h-[300px] w-[500px] -translate-x-1/2 rounded-full bg-cyan-400/10 blur-[100px]"></div>
      </div>

      <div class="mx-auto max-w-5xl px-6 text-center">
        <!-- Badge -->
        <div class="inline-flex items-center gap-2 rounded-full border border-border-interactive bg-surface-card/80 px-3.5 py-1 text-xs font-medium text-fg-secondary shadow-xs backdrop-blur-xs">
          <span class="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>OpenBIM Automated Code Compliance</span>
          <span class="text-border-interactive">|</span>
          <span class="text-accent font-semibold flex items-center gap-1">ISO 19650 Governed <Sparkles class="h-3 w-3" /></span>
        </div>

        <!-- Headline -->
        <h1 class="mt-6 text-4xl font-extrabold tracking-tight text-fg-primary sm:text-6xl md:text-7xl leading-[1.08]">
          Automated code compliance for the models you
          <span class="bg-linear-to-r from-accent via-cyan-400 to-blue-400 bg-clip-text text-transparent"
            >already have.</span
          >
        </h1>

        <!-- Subtitle -->
        <p class="mx-auto mt-6 max-w-3xl text-sm leading-relaxed text-fg-muted sm:text-lg">
          BIM Guard directly parses your IFC architectural models, executes dynamic database-stored compliance
          rules in pure Python, and streams every finding as a BCF 2.1 topic straight to your coordination team.
        </p>

        <!-- CTA Buttons -->
        <div class="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button variant="primary" size="lg" onclick={() => push("/login")} class="shadow-lg shadow-blue-500/20">
            Start Free Trial
            <ArrowRight class="h-4 w-4" />
          </Button>
          <Button variant="outline" size="lg" onclick={() => push("/login")}>
            Sign in as Dev User
          </Button>
        </div>

        <div class="mt-6 flex items-center justify-center gap-6 text-xs text-fg-muted font-medium">
          <div class="flex items-center gap-1.5">
            <CheckCircle2 class="h-3.5 w-3.5 text-success" />
            <span>Zero software installation</span>
          </div>
          <div class="flex items-center gap-1.5">
            <CheckCircle2 class="h-3.5 w-3.5 text-success" />
            <span>Pure OpenBIM / IFC native</span>
          </div>
          <div class="flex items-center gap-1.5">
            <CheckCircle2 class="h-3.5 w-3.5 text-success" />
            <span>BCF 2.1 coordination</span>
          </div>
        </div>
      </div>

      <!-- Hero Perspective App Mockup (Modular Component) -->
      <div class="mx-auto mt-14 max-w-6xl px-6">
        <HeroAppMockup />
      </div>
    </section>

    <!-- Standards & OpenBIM Marquee Ticker (Modular Component) -->
    <section class="border-y border-border-subtle bg-surface-card/40 py-6 overflow-hidden">
      <div class="mx-auto max-w-7xl px-6 mb-3 text-center">
        <span class="text-micro font-bold tracking-widest uppercase text-fg-muted"
          >Built on Open Standards & Industry Interoperability</span
        >
      </div>

      <Marquee durationSeconds={32}>
        {#each STANDARDS as item}
          <div class="flex shrink-0 items-center gap-2 rounded-xl border border-border-default bg-surface-card px-4 py-2 shadow-2xs">
            <span class="text-xs font-bold text-fg-primary">{item.name}</span>
            <span class="rounded-md bg-surface-overlay px-1.5 py-0.5 text-nano font-mono font-semibold {item.color}">
              {item.tag}
            </span>
          </div>
        {/each}
      </Marquee>
    </section>

    <!-- Animated Pipeline & Data Flow Section (Modular Component) -->
    <section id="pipeline" class="py-20 md:py-28 border-b border-border-subtle">
      <div class="mx-auto max-w-5xl px-6 text-center">
        <div class="inline-flex items-center gap-1.5 rounded-md border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
          <Workflow class="h-3.5 w-3.5" />
          End-to-End Orchestration
        </div>
        <h2 class="mt-4 text-3xl font-bold tracking-tight text-fg-primary sm:text-4xl">
          From Raw Model to Actionable BCF Topic
        </h2>
        <p class="mx-auto mt-4 max-w-2xl text-xs sm:text-sm text-fg-muted">
          Watch how BIM-Guard unifies IFC geometry, regulatory PDFs, and live model synchronization
          through a framework-agnostic architectural evaluation pipeline.
        </p>

        <div class="mt-14">
          <PipelineFlow />
        </div>
      </div>
    </section>

    <!-- Interactive Bento Grid Section -->
    <section id="features" class="py-20 md:py-28">
      <div class="mx-auto max-w-6xl px-6">
        <div class="text-center max-w-3xl mx-auto">
          <div class="inline-flex items-center gap-1.5 rounded-md border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
            <Sparkles class="h-3.5 w-3.5" />
            Next-Generation OpenBIM Features
          </div>
          <h2 class="mt-4 text-3xl font-bold tracking-tight text-fg-primary sm:text-4xl">
            Everything your team needs for compliance assurance
          </h2>
          <p class="mt-3 text-xs sm:text-sm text-fg-muted">
            Engineered from first principles for architects, BIM managers, and general contractors.
          </p>
        </div>

        <div class="mt-14 grid grid-cols-1 md:grid-cols-3 gap-5">
          <!-- Bento Card 1: 3D-Native Compliance (Span 2 cols) -->
          <div class="md:col-span-2 rounded-3xl border border-border-default bg-surface-card p-8 flex flex-col justify-between hover:border-border-interactive transition-colors">
            <div>
              <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent/10 text-accent mb-4">
                <ScanEye class="h-5 w-5" />
              </div>
              <h3 class="text-xl font-bold text-fg-primary">3D-Native Architectural Compliance</h3>
              <p class="mt-2 text-xs sm:text-sm text-fg-muted leading-relaxed max-w-xl">
                Every flagged egress violation, door clearance deficiency, and spatial clash is isolated
                directly in your IFC model. Inspect geometric measurements and citations without cross-referencing
                external spreadsheets.
              </p>
            </div>

            <!-- Mini Interactive Visual inside Bento Card -->
            <div class="mt-6 rounded-2xl border border-border-subtle bg-surface-canvas p-4 space-y-2">
              <div class="flex items-center justify-between text-xs font-semibold">
                <span class="text-fg-primary">Corridor Egress Checks (NBC 3.4.3.2)</span>
                <span class="rounded bg-success-bg text-success px-2 py-0.5 text-micro font-bold border border-success-border">PASS 98.4%</span>
              </div>
              <div class="w-full bg-surface-overlay h-2 rounded-full overflow-hidden">
                <div class="bg-emerald-400 h-full rounded-full" style="width: 98.4%"></div>
              </div>
              <div class="flex items-center justify-between text-nano text-fg-muted font-mono">
                <span>124 doors audited</span>
                <span>Max travel distance: 24.1m (Cutoff: ≤30.0m)</span>
              </div>
            </div>
          </div>

          <!-- Bento Card 2: ISO 19650 Governance -->
          <div class="rounded-3xl border border-border-default bg-surface-card p-8 flex flex-col justify-between hover:border-border-interactive transition-colors">
            <div>
              <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400 mb-4">
                <Workflow class="h-5 w-5" />
              </div>
              <h3 class="text-xl font-bold text-fg-primary">ISO 19650 Governance</h3>
              <p class="mt-2 text-xs sm:text-sm text-fg-muted leading-relaxed">
                State transitions enforced by a strict database state machine: WIP &rarr; SHARED &rarr; PUBLISHED &rarr; ARCHIVED.
              </p>
            </div>

            <div class="mt-6 space-y-2 text-micro font-mono">
              <div class="flex items-center gap-2 rounded-lg bg-surface-overlay px-3 py-1.5 text-fg-secondary">
                <span class="h-2 w-2 rounded-full bg-amber-400"></span>
                <span>WIP &rarr; SHARED (Approval Gate)</span>
              </div>
              <div class="flex items-center gap-2 rounded-lg bg-surface-overlay px-3 py-1.5 text-fg-secondary">
                <span class="h-2 w-2 rounded-full bg-emerald-400"></span>
                <span>SHARED &rarr; PUBLISHED (Signed)</span>
              </div>
            </div>
          </div>

          <!-- Bento Card 3: bSDD Semantic Enrichment -->
          <div class="rounded-3xl border border-border-default bg-surface-card p-8 flex flex-col justify-between hover:border-border-interactive transition-colors">
            <div>
              <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-400 mb-4">
                <Database class="h-5 w-5" />
              </div>
              <h3 class="text-xl font-bold text-fg-primary">bSDD Semantic Enrichment</h3>
              <p class="mt-2 text-xs sm:text-sm text-fg-muted leading-relaxed">
                Query buildingSMART's live data dictionary to map element property sets to international standards automatically.
              </p>
            </div>

            <div class="mt-6 rounded-2xl border border-border-subtle bg-surface-canvas p-3 text-micro space-y-1">
              <div class="flex items-center justify-between text-fg-muted">
                <span>Domain</span>
                <span class="font-bold text-fg-primary">buildingSMART</span>
              </div>
              <div class="flex items-center justify-between text-fg-muted">
                <span>Class</span>
                <span class="font-mono text-accent">IfcDoor.FireRating</span>
              </div>
            </div>
          </div>

          <!-- Bento Card 4: BCF 2.1 Coordination (Span 2 cols) -->
          <div class="md:col-span-2 rounded-3xl border border-border-default bg-surface-card p-8 flex flex-col justify-between hover:border-border-interactive transition-colors">
            <div>
              <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-400 mb-4">
                <GitBranch class="h-5 w-5" />
              </div>
              <h3 class="text-xl font-bold text-fg-primary">BCF 2.1 Native Issue Coordination</h3>
              <p class="mt-2 text-xs sm:text-sm text-fg-muted leading-relaxed max-w-xl">
                Every code violation is compiled into a standardized BCF topic. Subcontractors and engineers
                view the exact viewpoint camera angle and component guid in Autodesk Revit, Solibri, and Archicad.
              </p>
            </div>

            <div class="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3 text-micro">
              <div class="rounded-xl border border-border-subtle bg-surface-canvas p-3 space-y-1">
                <div class="flex items-center justify-between font-bold text-critical">
                  <span>Topic #104 · Egress</span>
                  <span class="rounded bg-rose-500/20 px-1 text-nano">CRITICAL</span>
                </div>
                <p class="text-fg-secondary">Door 102 swing direction impedes exit corridor.</p>
              </div>
              <div class="rounded-xl border border-border-subtle bg-surface-canvas p-3 space-y-1">
                <div class="flex items-center justify-between font-bold text-warning">
                  <span>Topic #105 · Spatial</span>
                  <span class="rounded bg-amber-500/20 px-1 text-nano">HIGH</span>
                </div>
                <p class="text-fg-secondary">Fire damper clearance envelope missing 150mm gap.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Comparison Matrix Section (Modular Component) -->
    <section id="comparison" class="py-20 md:py-28 border-t border-border-subtle bg-surface-card/20">
      <div class="mx-auto max-w-6xl px-6">
        <div class="text-center max-w-3xl mx-auto">
          <div class="inline-flex items-center gap-1.5 rounded-md border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
            <CheckCircle2 class="h-3.5 w-3.5" />
            The Clear Choice
          </div>
          <h2 class="mt-4 text-3xl font-bold tracking-tight text-fg-primary sm:text-4xl">
            Why Teams Choose BIM-Guard
          </h2>
          <p class="mt-3 text-xs sm:text-sm text-fg-muted">
            See how BIM-Guard compares to manual plan reviews and legacy desktop checking software.
          </p>
        </div>

        <div class="mt-12">
          <ComparisonTable items={COMPARISONS} />
        </div>
      </div>
    </section>

    <!-- FAQ Section (Modular Component) -->
    <section id="faq" class="py-20 md:py-28 border-t border-border-subtle">
      <div class="mx-auto max-w-4xl px-6">
        <div class="text-center">
          <div class="inline-flex items-center gap-1.5 rounded-md border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
            <FileCode2 class="h-3.5 w-3.5" />
            Frequently Asked Questions
          </div>
          <h2 class="mt-4 text-3xl font-bold tracking-tight text-fg-primary sm:text-4xl">
            Everything you need to know
          </h2>
          <p class="mt-3 text-xs sm:text-sm text-fg-muted">
            Have questions about integrations, security, or self-hosting? Find answers below.
          </p>
        </div>

        <div class="mt-12">
          <FaqAccordion items={FAQS} />
        </div>
      </div>
    </section>

    <!-- Bottom High-Conversion CTA Banner -->
    <section class="py-20 border-t border-border-subtle relative overflow-hidden bg-surface-card/30">
      <div class="pointer-events-none absolute inset-0 flex items-center justify-center -z-10">
        <div class="h-80 w-[600px] rounded-full bg-accent/15 blur-[100px]"></div>
      </div>

      <div class="mx-auto max-w-4xl px-6 text-center">
        <h2 class="text-3xl font-bold tracking-tight text-fg-primary sm:text-5xl">
          Start auditing your BIM models in seconds.
        </h2>
        <p class="mx-auto mt-4 max-w-2xl text-xs sm:text-sm text-fg-muted">
          No credit card required. Upload an IFC file or explore our seeded architectural demo models.
        </p>
        <div class="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button variant="primary" size="lg" onclick={() => push("/login")} class="shadow-lg shadow-blue-500/20">
            Get Started with BIM Guard
            <ArrowRight class="h-4 w-4" />
          </Button>
          <Button variant="outline" size="lg" onclick={() => push("/login")}>
            Sign in
          </Button>
        </div>
      </div>
    </section>
  </main>

  <!-- Modern Clean Footer -->
  <footer class="border-t border-border-default bg-surface-canvas px-6 py-8 text-xs text-fg-muted">
    <div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <div class="flex h-6 w-6 items-center justify-center rounded-lg bg-linear-to-tr from-accent to-cyan-400 text-micro font-bold text-white">
          BG
        </div>
        <span class="font-semibold text-fg-secondary">BIM Guard OpenBIM Compliance Engine</span>
        <span>&copy; {new Date().getFullYear()}</span>
      </div>

      <div class="flex items-center gap-6">
        <a href="/features" class="hover:text-fg-primary transition-colors">Features</a>
        <a href="/docs" class="hover:text-fg-primary transition-colors">Docs</a>
        <a href="/terms" class="hover:text-fg-primary transition-colors">Terms of Service</a>
        <a href="/privacy" class="hover:text-fg-primary transition-colors">Privacy Policy</a>
        <a href="/sitemap.xml" class="hover:text-fg-primary transition-colors">Sitemap</a>
      </div>
    </div>
  </footer>
</div>
