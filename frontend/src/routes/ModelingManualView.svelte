<script lang="ts">
  import { Box, Layers, ShieldCheck, CheckCircle2 } from "lucide-svelte";

  const CHECKLISTS = [
    {
      domain: "Doors",
      items: [
        {
          title: "True door family, not a generic model",
          why: "A generic model dressed up to look like a door doesn't export as IfcDoor — it drops out of every door check, with no error or warning.",
        },
        {
          title: "Hosted in a wall, not freestanding",
          why: "An unhosted door doesn't get modeled as a real opening, which breaks space-boundary and fire-separation checks that depend on it sitting inside a wall.",
        },
        {
          title: "Assigned to the correct building storey",
          why: "A door with no level assigned, or the wrong level, fails the storey-assignment check even if every other property is correct.",
        },
        {
          title: "Connects two room-bounding spaces",
          why: "The most common false failure: if the Rooms/Spaces on either side of the door aren't placed or set to room-bounding, the space-connection check fails even though the door itself is modeled correctly.",
        },
      ],
    },
  ];

  const GUIDES = [
    {
      domain: "Architecture & Egress",
      items: [
        {
          element: "Doors & Clearances",
          rules:
            "Doors must have clear width >= 810mm and explicit fire ratings (e.g. 45 min for separations) defined in Pset_DoorCommon.",
        },
        {
          element: "Windows & Daylighting",
          rules:
            "Unobstructed glass area must be >= 10% of floor area for habitable spaces (per the active building-code ruleset). Ensure IfcWindow instances belong to valid IfcSpace boundaries.",
        },
        {
          element: "Stairs & Handrails",
          rules:
            "Riser height must not exceed 200mm, with minimum tread depth of 255mm. Assign proper IfcStairFlight and IfcRailing entities.",
        },
      ],
    },
    {
      domain: "MEP & Piping",
      items: [
        {
          element: "Material Specifications",
          rules:
            "Assign explicit material definitions (e.g. Copper, Galvanized Steel, PVC) to prevent galvanic coupling risks under GC-001.",
        },
        {
          element: "Fluid Service & Insulation",
          rules:
            "Specify system fluid types and operating temperatures to accurately calculate microbiological corrosion (MC-001) susceptibility.",
        },
        {
          element: "Seismic Clearance Volume",
          rules:
            "Model pipe runs with proper seismic hanger allowances and Blue Halo clearance volumes around equipment interfaces.",
        },
      ],
    },
  ];
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <div>
    <div class="mb-1 text-xs font-bold uppercase tracking-widest text-slate-400">Manuals</div>
    <h1 class="text-2xl font-bold tracking-tight text-slate-50 sm:text-3xl">
      3D Modeling Reference Manual
    </h1>
    <p class="text-xs text-slate-400 sm:text-sm">
      OpenBIM modeling conventions to ensure IFC models pass automated compliance rules.
    </p>
  </div>

  <!-- Architectural 3D Model Checklist -->
  <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
    <h2 class="flex items-center gap-2 text-base font-bold tracking-tight text-slate-50">
      <CheckCircle2 class="h-4 w-4 text-accent" />
      <span>Architectural 3D Model Checklist</span>
    </h2>
    <p class="-mt-2 text-caption text-slate-400">
      Modeling mistakes that make an element invisible to checking entirely, or fail a rule that has
      nothing to do with a real code issue &mdash; regardless of whether its properties are filled
      in correctly. Check these before export.
    </p>

    {#each CHECKLISTS as group (group)}
      <div class="space-y-2">
        <div class="text-xs font-semibold text-slate-50">{group.domain}</div>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          {#each group.items as item (item)}
            <div class="flex gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <CheckCircle2 class="mt-0.5 h-4 w-4 shrink-0 text-accent" />
              <div class="space-y-1">
                <div class="text-xs font-semibold text-slate-50">{item.title}</div>
                <p class="text-caption leading-relaxed text-slate-400">{item.why}</p>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>

  <div class="space-y-6">
    {#each GUIDES as group (group)}
      <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 class="flex items-center gap-2 text-base font-bold tracking-tight text-slate-50">
          <Layers class="h-4 w-4 text-accent" />
          <span>{group.domain}</span>
        </h2>

        <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
          {#each group.items as item (item)}
            <div class="space-y-2 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <div class="text-xs font-semibold text-slate-50">{item.element}</div>
              <p class="text-caption leading-relaxed text-slate-400">
                {item.rules}
              </p>
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>
</div>
