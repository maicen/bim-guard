<script lang="ts">
  import { link } from "svelte-spa-router";
  import {
    ScanEye,
    Workflow,
    GitBranch,
    Database,
    BookOpenCheck,
    Box,
    BookText,
    Palette,
    ExternalLink,
    ShieldCheck,
    Sparkles,
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

<NavigationMenu viewport={false} class={className}>
  <NavigationMenuList class="flex items-center gap-1.5">
    <!-- Platform / Features Menu -->
    <NavigationMenuItem>
      <NavigationMenuTrigger class="text-sm font-medium">
        Platform
      </NavigationMenuTrigger>
      <NavigationMenuContent class="w-[640px] p-5">
        <div class="grid grid-cols-12 gap-5">
          <!-- Featured Left Box -->
          <div class="col-span-5 rounded-xl bg-linear-to-b from-accent/20 via-surface-overlay to-surface-card p-5 flex flex-col justify-between border border-border-interactive">
            <div class="space-y-3">
              <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-white shadow-md">
                <ScanEye class="h-5 w-5" />
              </div>
              <div>
                <h4 class="text-sm font-bold text-fg-primary leading-snug">OpenBIM Compliance Engine</h4>
                <p class="text-xs text-fg-secondary leading-relaxed mt-1.5">
                  Automated building code compliance, egress routing, and spatial clearance analysis for IFC models.
                </p>
              </div>
            </div>
            <a
              href="#pipeline"
              class="inline-flex items-center gap-1.5 text-xs font-semibold text-accent hover:underline mt-4"
            >
              <span>Explore Engine Pipeline</span>
              <Sparkles class="h-3.5 w-3.5" />
            </a>
          </div>

          <!-- Feature Links Right -->
          <div class="col-span-7 flex flex-col gap-1.5">
            <NavigationMenuLink href="#features">
              <div class="flex items-center gap-2.5">
                <ScanEye class="h-4 w-4 text-accent" />
                <span class="text-sm font-semibold text-fg-primary">3D-Native Architectural Audit</span>
              </div>
              <p class="text-xs text-fg-muted leading-relaxed">Corridor widths, egress exit counts, and spatial clearances.</p>
            </NavigationMenuLink>

            <NavigationMenuLink href="#features">
              <div class="flex items-center gap-2.5">
                <Workflow class="h-4 w-4 text-emerald-400" />
                <span class="text-sm font-semibold text-fg-primary">ISO 19650 Governance</span>
              </div>
              <p class="text-xs text-fg-muted leading-relaxed">Enforced WIP &rarr; SHARED &rarr; PUBLISHED CDE state transitions.</p>
            </NavigationMenuLink>

            <NavigationMenuLink href="#features">
              <div class="flex items-center gap-2.5">
                <GitBranch class="h-4 w-4 text-cyan-400" />
                <span class="text-sm font-semibold text-fg-primary">BCF 2.1 Coordination</span>
              </div>
              <p class="text-xs text-fg-muted leading-relaxed">Direct topic sync with camera viewpoints for Revit and Solibri.</p>
            </NavigationMenuLink>

            <NavigationMenuLink href="#/bsdd-wiki">
              <div class="flex items-center gap-2.5">
                <Database class="h-4 w-4 text-amber-400" />
                <span class="text-sm font-semibold text-fg-primary">bSDD Semantic Enrichment</span>
              </div>
              <p class="text-xs text-fg-muted leading-relaxed">buildingSMART Data Dictionary classification lookup.</p>
            </NavigationMenuLink>
          </div>
        </div>
      </NavigationMenuContent>
    </NavigationMenuItem>

    <!-- Resources & Documentation Menu -->
    <NavigationMenuItem>
      <NavigationMenuTrigger class="text-sm font-medium">
        Documentation
      </NavigationMenuTrigger>
      <NavigationMenuContent class="w-[580px] p-5">
        <div class="grid grid-cols-2 gap-3">
          <NavigationMenuLink href="#/manual">
            <div class="flex items-center gap-2.5">
              <BookOpenCheck class="h-4.5 w-4.5 text-accent" />
              <span class="text-sm font-semibold text-fg-primary">User Manual</span>
            </div>
            <p class="text-xs text-fg-muted leading-relaxed mt-0.5">Full walkthrough for compliance checks, BCF exports, and model inspection.</p>
          </NavigationMenuLink>

          <NavigationMenuLink href="#/modeling-manual">
            <div class="flex items-center gap-2.5">
              <Box class="h-4.5 w-4.5 text-cyan-400" />
              <span class="text-sm font-semibold text-fg-primary">Modeling Manual</span>
            </div>
            <p class="text-xs text-fg-muted leading-relaxed mt-0.5">IFC authoring conventions, space boundaries, and element property sets.</p>
          </NavigationMenuLink>

          <NavigationMenuLink href="#/bsdd-wiki">
            <div class="flex items-center gap-2.5">
              <BookText class="h-4.5 w-4.5 text-amber-400" />
              <span class="text-sm font-semibold text-fg-primary">bSDD Wiki</span>
            </div>
            <p class="text-xs text-fg-muted leading-relaxed mt-0.5">buildingSMART Data Dictionary classifications, domains, and properties.</p>
          </NavigationMenuLink>

          <NavigationMenuLink href="#/design-system">
            <div class="flex items-center gap-2.5">
              <Palette class="h-4.5 w-4.5 text-purple-400" />
              <span class="text-sm font-semibold text-fg-primary">Design System</span>
            </div>
            <p class="text-xs text-fg-muted leading-relaxed mt-0.5">Interactive catalog of semantic design tokens and bits-ui primitives.</p>
          </NavigationMenuLink>
        </div>

        <div class="mt-4 pt-3.5 border-t border-border-subtle flex items-center justify-between px-2 text-xs">
          <span class="text-fg-muted font-medium">Developer Tools & API Reference</span>
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-1.5 font-semibold text-accent hover:underline"
          >
            <span>OpenAPI Specs (/api/docs)</span>
            <ExternalLink class="h-3.5 w-3.5" />
          </a>
        </div>
      </NavigationMenuContent>
    </NavigationMenuItem>

    <!-- About & Research Menu -->
    <NavigationMenuItem>
      <NavigationMenuTrigger class="text-sm font-medium">
        About
      </NavigationMenuTrigger>
      <NavigationMenuContent class="w-[480px] p-5">
        <div class="flex flex-col gap-2">
          <NavigationMenuLink href="#/evaluation">
            <div class="flex items-center gap-2.5">
              <FlaskConical class="h-4.5 w-4.5 text-accent" />
              <span class="text-sm font-semibold text-fg-primary">Accuracy Benchmark & Evaluation</span>
            </div>
            <p class="text-xs text-fg-muted leading-relaxed mt-0.5">Linguistic NLP annotation scoring, 38-model sweeps, and empirical validation.</p>
          </NavigationMenuLink>

          <a
            href="https://github.com/maicen/bim-guard"
            target="_blank"
            rel="noopener noreferrer"
            class="flex flex-col gap-1 rounded-xl p-3 text-sm text-fg-secondary outline-hidden transition-colors hover:bg-surface-hover hover:text-fg-primary focus:bg-surface-hover focus:text-fg-primary"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2.5">
                <Github class="h-4.5 w-4.5 text-fg-primary" />
                <span class="text-sm font-semibold text-fg-primary">Open Source Repository</span>
              </div>
              <ExternalLink class="h-3.5 w-3.5 text-fg-muted" />
            </div>
            <p class="text-xs text-fg-muted leading-relaxed mt-0.5">Source code, Docker Compose stack, and Cloudflare Tunnel configs.</p>
          </a>

          <div class="grid grid-cols-2 gap-2 pt-3 mt-1 border-t border-border-subtle text-xs">
            <a href="/privacy" class="p-2.5 rounded-lg hover:bg-surface-hover flex items-center gap-2 font-medium text-fg-secondary hover:text-fg-primary transition-colors">
              <ShieldCheck class="h-4 w-4 text-emerald-400" />
              <span>Privacy Policy</span>
            </a>
            <a href="/terms" class="p-2.5 rounded-lg hover:bg-surface-hover flex items-center gap-2 font-medium text-fg-secondary hover:text-fg-primary transition-colors">
              <Scale class="h-4 w-4 text-info" />
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
