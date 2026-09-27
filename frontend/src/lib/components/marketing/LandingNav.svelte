<script lang="ts">
  import { link } from "svelte-spa-router";
  import {
    ScanEye,
    Workflow,
    GitBranch,
    Boxes,
    Database,
    BookOpenCheck,
    Box,
    BookText,
    Palette,
    ExternalLink,
    ShieldCheck,
    Sparkles,
    FileText,
    Code2,
    Building2,
    FlaskConical,
    Github,
    Scale,
  } from "lucide-svelte";
  import {
    NavigationMenu,
    NavigationMenuList,
    NavigationMenuItem,
    NavigationMenuTrigger,
    NavigationMenuContent,
    NavigationMenuLink,
    navigationMenuTriggerStyle,
  } from "../ui/navigation-menu";

  interface Props {
    class?: string;
  }

  let { class: className }: Props = $props();
</script>

<NavigationMenu class={className}>
  <NavigationMenuList class="flex items-center gap-1">
    <!-- Platform / Features Menu -->
    <NavigationMenuItem>
      <NavigationMenuTrigger class="text-xs font-semibold">
        Platform
      </NavigationMenuTrigger>
      <NavigationMenuContent class="w-[580px] p-4">
        <div class="grid grid-cols-12 gap-4">
          <!-- Featured Left Box -->
          <div class="col-span-5 rounded-xl bg-linear-to-b from-accent/20 via-surface-overlay to-surface-card p-4 flex flex-col justify-between border border-border-interactive">
            <div class="space-y-2">
              <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-accent text-white shadow-md">
                <ScanEye class="h-5 w-5" />
              </div>
              <h4 class="text-xs font-bold text-fg-primary leading-tight">OpenBIM Compliance Engine</h4>
              <p class="text-nano text-fg-muted leading-relaxed">
                Automated code compliance and spatial analysis for IFC2X3 & IFC4 models.
              </p>
            </div>
            <a
              href="#pipeline"
              class="inline-flex items-center gap-1 text-nano font-bold text-accent hover:underline mt-3"
            >
              <span>Explore Engine Pipeline</span>
              <Sparkles class="h-3 w-3" />
            </a>
          </div>

          <!-- Feature Links Right -->
          <div class="col-span-7 flex flex-col gap-1">
            <NavigationMenuLink href="#features">
              <div class="flex items-center gap-2">
                <ScanEye class="h-3.5 w-3.5 text-accent" />
                <span class="font-bold text-fg-primary">3D-Native Architectural Audit</span>
              </div>
              <p class="text-nano text-fg-muted">Corridor widths, egress exit counts, and spatial clearances.</p>
            </NavigationMenuLink>

            <NavigationMenuLink href="#features">
              <div class="flex items-center gap-2">
                <Workflow class="h-3.5 w-3.5 text-emerald-400" />
                <span class="font-bold text-fg-primary">ISO 19650 Governance</span>
              </div>
              <p class="text-nano text-fg-muted">Enforced WIP &rarr; SHARED &rarr; PUBLISHED CDE state transitions.</p>
            </NavigationMenuLink>

            <NavigationMenuLink href="#features">
              <div class="flex items-center gap-2">
                <GitBranch class="h-3.5 w-3.5 text-cyan-400" />
                <span class="font-bold text-fg-primary">BCF 2.1 Coordination</span>
              </div>
              <p class="text-nano text-fg-muted">Direct topic sync with camera viewpoints for Revit and Solibri.</p>
            </NavigationMenuLink>

            <NavigationMenuLink href="#/bsdd-wiki">
              <div class="flex items-center gap-2">
                <Database class="h-3.5 w-3.5 text-amber-400" />
                <span class="font-bold text-fg-primary">bSDD Semantic Enrichment</span>
              </div>
              <p class="text-nano text-fg-muted">buildingSMART Data Dictionary classification lookup.</p>
            </NavigationMenuLink>
          </div>
        </div>
      </NavigationMenuContent>
    </NavigationMenuItem>

    <!-- Resources & Documentation Menu -->
    <NavigationMenuItem>
      <NavigationMenuTrigger class="text-xs font-semibold">
        Documentation
      </NavigationMenuTrigger>
      <NavigationMenuContent class="w-[520px] p-3">
        <div class="grid grid-cols-2 gap-2">
          <NavigationMenuLink href="#/manual">
            <div class="flex items-center gap-2">
              <BookOpenCheck class="h-4 w-4 text-accent" />
              <span class="font-bold text-fg-primary">User Manual</span>
            </div>
            <p class="text-nano text-fg-muted">Full walkthrough for compliance checks, BCF exports, and model inspection.</p>
          </NavigationMenuLink>

          <NavigationMenuLink href="#/modeling-manual">
            <div class="flex items-center gap-2">
              <Box class="h-4 w-4 text-cyan-400" />
              <span class="font-bold text-fg-primary">Modeling Manual</span>
            </div>
            <p class="text-nano text-fg-muted">IFC authoring conventions, space boundaries, and element property sets.</p>
          </NavigationMenuLink>

          <NavigationMenuLink href="#/bsdd-wiki">
            <div class="flex items-center gap-2">
              <BookText class="h-4 w-4 text-amber-400" />
              <span class="font-bold text-fg-primary">bSDD Wiki</span>
            </div>
            <p class="text-nano text-fg-muted">buildingSMART Data Dictionary classifications, domains, and properties.</p>
          </NavigationMenuLink>

          <NavigationMenuLink href="#/design-system">
            <div class="flex items-center gap-2">
              <Palette class="h-4 w-4 text-purple-400" />
              <span class="font-bold text-fg-primary">Design System</span>
            </div>
            <p class="text-nano text-fg-muted">Interactive catalog of semantic design tokens and bits-ui primitives.</p>
          </NavigationMenuLink>
        </div>

        <div class="mt-2 pt-2 border-t border-border-subtle flex items-center justify-between px-2 text-micro">
          <span class="text-fg-muted font-medium">Developer Tools & API</span>
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-1 font-bold text-accent hover:underline"
          >
            <span>OpenAPI Specs (/api/docs)</span>
            <ExternalLink class="h-3 w-3" />
          </a>
        </div>
      </NavigationMenuContent>
    </NavigationMenuItem>

    <!-- About & Research Menu -->
    <NavigationMenuItem>
      <NavigationMenuTrigger class="text-xs font-semibold">
        About
      </NavigationMenuTrigger>
      <NavigationMenuContent class="w-[460px] p-3">
        <div class="space-y-1">
          <NavigationMenuLink href="#/evaluation">
            <div class="flex items-center gap-2">
              <FlaskConical class="h-4 w-4 text-accent" />
              <span class="font-bold text-fg-primary">Accuracy Benchmark & Evaluation</span>
            </div>
            <p class="text-nano text-fg-muted">Linguistic NLP annotation scoring, 38-model sweeps, and empirical validation.</p>
          </NavigationMenuLink>

          <a
            href="https://github.com/maicen/bim-guard"
            target="_blank"
            rel="noopener noreferrer"
            class="flex flex-col gap-1 rounded-lg p-2.5 text-xs text-fg-secondary outline-hidden transition-colors hover:bg-surface-hover hover:text-fg-primary"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <Github class="h-4 w-4 text-fg-primary" />
                <span class="font-bold text-fg-primary">Open Source Repository</span>
              </div>
              <ExternalLink class="h-3 w-3 text-fg-muted" />
            </div>
            <p class="text-nano text-fg-muted">Source code, Docker Compose stack, and Cloudflare Tunnel configs.</p>
          </a>

          <div class="grid grid-cols-2 gap-2 pt-2 border-t border-border-subtle text-micro">
            <a href="/privacy" class="p-2 rounded-lg hover:bg-surface-hover flex items-center gap-1.5 font-medium text-fg-secondary hover:text-fg-primary">
              <ShieldCheck class="h-3.5 w-3.5 text-emerald-400" />
              <span>Privacy Policy</span>
            </a>
            <a href="/terms" class="p-2 rounded-lg hover:bg-surface-hover flex items-center gap-1.5 font-medium text-fg-secondary hover:text-fg-primary">
              <Scale class="h-3.5 w-3.5 text-info" />
              <span>Terms of Service</span>
            </a>
          </div>
        </div>
      </NavigationMenuContent>
    </NavigationMenuItem>

    <!-- Direct Anchors -->
    <NavigationMenuItem>
      <a href="#comparison" class={navigationMenuTriggerStyle()}>
        Comparison
      </a>
    </NavigationMenuItem>

    <NavigationMenuItem>
      <a href="#faq" class={navigationMenuTriggerStyle()}>
        FAQ
      </a>
    </NavigationMenuItem>
  </NavigationMenuList>
</NavigationMenu>
