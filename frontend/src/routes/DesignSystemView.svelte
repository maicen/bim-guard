<script lang="ts">
  import {
    Palette,
    CheckCircle2,
    AlertCircle,
    AlertTriangle,
    Info,
    Search,
    Mail,
    Lock,
    ExternalLink,
    Sun,
    Moon,
    Laptop,
    Sparkles,
  } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import {
    Button,
    Input,
    FormField,
    Card,
    CardHeader,
    CardTitle,
    CardContent,
    type ButtonVariant,
    type ButtonSize,
  } from "../lib/components/ui";
  import Badge from "../lib/components/Badge.svelte";
  import SeverityBadge from "../lib/components/SeverityBadge.svelte";
  import Alert from "../lib/components/Alert.svelte";
  import { themeMode, resolvedTheme, setTheme, type ThemeMode } from "../lib/theme";

  // Interactive controls for testing the components
  let isButtonLoading = $state(false);
  let isButtonDisabled = $state(false);
  let sampleInputValue = $state("PRJ-BIMGUARD-001");
  let sampleErrorValue = $state("Invalid ISO 19650 identifier");
  let activeTab = $state<"tokens" | "components" | "forms" | "badges">("tokens");

  const BUTTON_VARIANTS: ButtonVariant[] = [
    "primary",
    "secondary",
    "outline",
    "ghost",
    "destructive",
  ];

  const BUTTON_SIZES: ButtonSize[] = ["xs", "sm", "md", "lg"];

  function handleThemeChange(mode: ThemeMode) {
    setTheme(mode);
  }
</script>

<div class="space-y-8 pb-16">
  <!-- Page Header -->
  <PageHeader
    category="Resources"
    title="Design System & UI Kit"
    subtitle="Interactive component library, semantic tokens, and accessibility standards for BIM-Guard OpenBIM engineering views."
    icon={Palette}
  >
    {#snippet actions()}
      <div class="flex items-center gap-1 rounded-xl border border-border-default bg-surface-card p-1 shadow-xs">
        <button
          type="button"
          onclick={() => handleThemeChange("light")}
          class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-micro font-medium transition-colors {$themeMode === 'light'
            ? 'bg-accent text-white font-semibold'
            : 'text-fg-secondary hover:text-fg-primary'}"
          title="Switch to Light Theme"
        >
          <Sun class="h-3.5 w-3.5" />
          Light
        </button>
        <button
          type="button"
          onclick={() => handleThemeChange("dark")}
          class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-micro font-medium transition-colors {$themeMode === 'dark'
            ? 'bg-accent text-white font-semibold'
            : 'text-fg-secondary hover:text-fg-primary'}"
          title="Switch to Dark Theme"
        >
          <Moon class="h-3.5 w-3.5" />
          Dark
        </button>
        <button
          type="button"
          onclick={() => handleThemeChange("system")}
          class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-micro font-medium transition-colors {$themeMode === 'system'
            ? 'bg-accent text-white font-semibold'
            : 'text-fg-secondary hover:text-fg-primary'}"
          title="Sync with System Theme"
        >
          <Laptop class="h-3.5 w-3.5" />
          System
        </button>
      </div>
    {/snippet}
  </PageHeader>

  <!-- Navigation Tabs -->
  <div class="flex flex-wrap items-center gap-2 border-b border-border-subtle pb-3">
    <Button
      variant={activeTab === "tokens" ? "primary" : "ghost"}
      size="sm"
      onclick={() => (activeTab = "tokens")}
    >
      Color Tokens & Surfaces
    </Button>
    <Button
      variant={activeTab === "components" ? "primary" : "ghost"}
      size="sm"
      onclick={() => (activeTab = "components")}
    >
      Buttons & Primitives
    </Button>
    <Button
      variant={activeTab === "forms" ? "primary" : "ghost"}
      size="sm"
      onclick={() => (activeTab = "forms")}
    >
      Form Controls & Inputs
    </Button>
    <Button
      variant={activeTab === "badges" ? "primary" : "ghost"}
      size="sm"
      onclick={() => (activeTab = "badges")}
    >
      Severity Bands & Alerts
    </Button>
  </div>

  <!-- SECTION 1: Color Tokens & Surfaces -->
  {#if activeTab === "tokens"}
    <div class="space-y-6 duration-200 animate-in fade-in">
      <div>
        <h2 class="text-sm font-bold text-fg-primary">Semantic Surfaces & Architecture</h2>
        <p class="text-xs text-fg-muted mt-0.5">
          Surfaces adapt automatically per theme: deep slate background in dark mode, crisp clean white cards and elevated panels in light mode.
        </p>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Canvas -->
        <Card class="p-4 bg-surface-canvas border-border-default">
          <div class="space-y-2">
            <span class="text-micro font-semibold uppercase tracking-wider text-fg-muted">Canvas Surface</span>
            <div class="h-12 rounded-lg border border-border-subtle bg-surface-canvas flex items-center justify-center text-xs font-mono text-fg-secondary">
              bg-surface-canvas
            </div>
            <p class="text-nano text-fg-muted">Base application viewport background.</p>
          </div>
        </Card>

        <!-- Card -->
        <Card class="p-4 bg-surface-card border-border-default">
          <div class="space-y-2">
            <span class="text-micro font-semibold uppercase tracking-wider text-fg-muted">Card Surface</span>
            <div class="h-12 rounded-lg border border-border-default bg-surface-card flex items-center justify-center text-xs font-mono text-fg-primary shadow-xs">
              bg-surface-card
            </div>
            <p class="text-nano text-fg-muted">Primary container surface for tables, charts, forms.</p>
          </div>
        </Card>

        <!-- Overlay -->
        <Card class="p-4 bg-surface-overlay border-border-default">
          <div class="space-y-2">
            <span class="text-micro font-semibold uppercase tracking-wider text-fg-muted">Overlay Surface</span>
            <div class="h-12 rounded-lg border border-border-default bg-surface-overlay flex items-center justify-center text-xs font-mono text-fg-primary">
              bg-surface-overlay
            </div>
            <p class="text-nano text-fg-muted">Elevated dialogs, popovers, and sticky floating bars.</p>
          </div>
        </Card>

        <!-- Accent -->
        <Card class="p-4 bg-surface-card border-border-default">
          <div class="space-y-2">
            <span class="text-micro font-semibold uppercase tracking-wider text-fg-muted">Chromatic Accent</span>
            <div class="h-12 rounded-lg bg-accent text-white flex items-center justify-center text-xs font-semibold shadow-xs">
              bg-accent
            </div>
            <p class="text-nano text-fg-muted">Strictly reserved for interactive actions and focus rings.</p>
          </div>
        </Card>
      </div>

      <!-- Typography & Contrast Ramp -->
      <Card>
        <CardHeader>
          <CardTitle>Typography & Foreground Contrast Levels</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="space-y-4">
            <div class="flex items-center justify-between border-b border-border-subtle pb-3">
              <div>
                <p class="text-sm font-bold text-fg-primary">text-fg-primary (High Contrast Headings)</p>
                <p class="text-caption text-fg-muted">Pure contrast text (slate-50 in dark, slate-900 in light).</p>
              </div>
              <span class="text-micro font-mono text-fg-muted">WCAG AAA (&gt;7:1)</span>
            </div>
            <div class="flex items-center justify-between border-b border-border-subtle pb-3">
              <div>
                <p class="text-xs font-medium text-fg-secondary">text-fg-secondary (Standard Body Text)</p>
                <p class="text-caption text-fg-muted">Readable body copy and table cell contents.</p>
              </div>
              <span class="text-micro font-mono text-fg-muted">WCAG AA (&gt;4.5:1)</span>
            </div>
            <div class="flex items-center justify-between">
              <div>
                <p class="text-caption text-fg-muted">text-fg-muted (Metadata &amp; Secondary Labels)</p>
                <p class="text-nano text-fg-muted">Timestamps, unit labels, table headers, breadcrumbs.</p>
              </div>
              <span class="text-micro font-mono text-fg-muted">WCAG AA Large (&gt;3:1)</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  {/if}

  <!-- SECTION 2: Buttons & Primitives -->
  {#if activeTab === "components"}
    <div class="space-y-6 duration-200 animate-in fade-in">
      <!-- Interactive Sandbox Toolbar -->
      <Card class="p-4 bg-surface-overlay border-border-default">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 class="text-xs font-bold text-fg-primary">Button Primitive Interactive Matrix</h3>
            <p class="text-nano text-fg-muted">Test real-time loading spinners, disabled states, and size scales.</p>
          </div>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-1.5 text-xs text-fg-secondary cursor-pointer select-none">
              <input type="checkbox" bind:checked={isButtonLoading} class="rounded text-accent focus:ring-accent" />
              <span>Loading State</span>
            </label>
            <label class="flex items-center gap-1.5 text-xs text-fg-secondary cursor-pointer select-none">
              <input type="checkbox" bind:checked={isButtonDisabled} class="rounded text-accent focus:ring-accent" />
              <span>Disabled State</span>
            </label>
          </div>
        </div>
      </Card>

      <!-- Variants Showcase -->
      <Card>
        <CardHeader>
          <CardTitle>Button Variants</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="flex flex-wrap items-center gap-3">
            {#each BUTTON_VARIANTS as variant}
              <Button
                {variant}
                size="md"
                loading={isButtonLoading}
                disabled={isButtonDisabled}
              >
                <Sparkles class="h-3.5 w-3.5" />
                <span class="capitalize">{variant}</span>
              </Button>
            {/each}
          </div>
        </CardContent>
      </Card>

      <!-- Sizes Hierarchy -->
      <Card>
        <CardHeader>
          <CardTitle>Size Hierarchy &amp; Border Radius Compliance</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="flex flex-wrap items-end gap-3">
            {#each BUTTON_SIZES as size}
              <Button
                variant="secondary"
                {size}
                loading={isButtonLoading}
                disabled={isButtonDisabled}
              >
                <span>Size: {size.toUpperCase()}</span>
              </Button>
            {/each}
            <Button
              variant="secondary"
              size="icon"
              loading={isButtonLoading}
              disabled={isButtonDisabled}
              aria-label="Icon Button Sample"
            >
              <Search class="h-4 w-4" />
            </Button>
          </div>
          <p class="text-nano text-fg-muted mt-3">
            Per DESIGN.md §5: XS uses <code>rounded-md</code>, SM uses <code>rounded-lg</code>, MD/LG use <code>rounded-xl</code>. Rectangular buttons never use <code>rounded-full</code>.
          </p>
        </CardContent>
      </Card>
    </div>
  {/if}

  <!-- SECTION 3: Form Controls & Inputs -->
  {#if activeTab === "forms"}
    <div class="space-y-6 duration-200 animate-in fade-in">
      <Card>
        <CardHeader>
          <CardTitle>Standardized Form Controls</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Standard Input -->
            <FormField label="Standard Project Code" htmlFor="std-input" hint="Required for ISO 19650" required>
              <Input id="std-input" bind:value={sampleInputValue} placeholder="e.g. PRJ-ARC-001" />
            </FormField>

            <!-- Input with Prefix Icon -->
            <FormField label="Search Elements" htmlFor="search-input" hint="Filter by GUID or Name">
              <Input id="search-input" placeholder="Search by name, class, material...">
                {#snippet prefixIcon()}
                  <Search class="h-3.5 w-3.5" />
                {/snippet}
              </Input>
            </FormField>

            <!-- Input with Error State -->
            <FormField label="Revision Code" htmlFor="error-input" error={sampleErrorValue} required>
              <Input id="error-input" error={true} value="INVALID_REV" placeholder="P01.01">
                {#snippet prefixIcon()}
                  <AlertCircle class="h-3.5 w-3.5 text-critical" />
                {/snippet}
              </Input>
            </FormField>

            <!-- Disabled Input -->
            <FormField label="System Storage Path (Read Only)" htmlFor="disabled-input">
              <Input id="disabled-input" disabled value="mem://storage/projects/007/models.ifc">
                {#snippet prefixIcon()}
                  <Lock class="h-3.5 w-3.5" />
                {/snippet}
              </Input>
            </FormField>
          </div>
        </CardContent>
      </Card>
    </div>
  {/if}

  <!-- SECTION 4: Severity Bands & Alerts -->
  {#if activeTab === "badges"}
    <div class="space-y-6 duration-200 animate-in fade-in">
      <!-- Severity Bands -->
      <Card>
        <CardHeader>
          <CardTitle>OpenBIM Severity &amp; Risk Badges</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="space-y-4">
            <p class="text-xs text-fg-muted">
              Defined centrally in <code>severity.ts</code> and automatically inverted across light and dark themes using semantic tokens.
            </p>
            <div class="flex flex-wrap items-center gap-2.5">
              <SeverityBadge severity="critical" />
              <SeverityBadge severity="high" />
              <SeverityBadge severity="medium" />
              <SeverityBadge severity="low" />
              <SeverityBadge severity="data_quality" />
              <SeverityBadge severity="neutral" />
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Pipeline Status Badges -->
      <Card>
        <CardHeader>
          <CardTitle>Pipeline Execution Status Badges</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="flex flex-wrap items-center gap-3">
            <Badge variant="complete">Complete</Badge>
            <Badge variant="running">Running Physics</Badge>
            <Badge variant="pending">Queued</Badge>
            <Badge variant="failed">Execution Failed</Badge>
          </div>
        </CardContent>
      </Card>

      <!-- Notification Alerts -->
      <Card>
        <CardHeader>
          <CardTitle>Notification Banners &amp; Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="space-y-3">
            <Alert
              type="error"
              title="Critical Compliance Risk Detected"
              message="Minimum pipe wall thickness threshold (3.2mm) violated on line P-102. Corrosion rate exceeds allowable tolerance."
              dismissible
            />
            <Alert
              type="warning"
              title="CDE State Transition Advisory"
              message="Publishing this model to 'PUBLISHED' state requires authorized Lead Appointed Party review."
              dismissible
            />
            <Alert
              type="success"
              title="Compliance Audit Succeeded"
              message="All 48 structural stair geometry tests passed successfully against ISO and OSHA standards."
              dismissible
            />
            <Alert
              type="info"
              title="bSDD Schema Integration Active"
              message="Classification dictionary synchronizing with buildingSMART Data Dictionary version 2.1."
              dismissible
            />
          </div>
        </CardContent>
      </Card>
    </div>
  {/if}
</div>
