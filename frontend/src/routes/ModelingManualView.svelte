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
            "Unobstructed glass area must be >= 10% of floor area for habitable spaces (Ontario Building Code Part 9). Ensure IfcWindow instances belong to valid IfcSpace boundaries.",
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

<div class="space-y-6 mx-auto">
  <!-- Header -->
  <div>
    <div
      class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1"
    >
      Manuals
    </div>
    <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50">
      3D Modeling Reference Manual
    </h1>
    <p class="text-xs sm:text-sm text-slate-400">
      OpenBIM modeling conventions to ensure IFC models pass automated
      compliance rules.
    </p>
  </div>

  <!-- Architectural 3D Model Checklist -->
  <div class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4">
    <h2 class="text-base font-bold text-slate-50 tracking-tight flex items-center gap-2">
      <CheckCircle2 class="w-4 h-4 text-accent" />
      <span>Architectural 3D Model Checklist</span>
    </h2>
    <p class="text-caption text-slate-400 -mt-2">
      Modeling mistakes that make an element invisible to checking entirely, or fail
      a rule that has nothing to do with a real code issue &mdash; regardless of
      whether its properties are filled in correctly. Check these before export.
    </p>

    {#each CHECKLISTS as group}
      <div class="space-y-2">
        <div class="font-semibold text-xs text-slate-50">{group.domain}</div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          {#each group.items as item}
            <div class="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex gap-3">
              <CheckCircle2 class="w-4 h-4 text-accent shrink-0 mt-0.5" />
              <div class="space-y-1">
                <div class="font-semibold text-xs text-slate-50">{item.title}</div>
                <p class="text-caption text-slate-400 leading-relaxed">{item.why}</p>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>

  <div class="space-y-6">
    {#each GUIDES as group}
      <div
        class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4"
      >
        <h2
          class="text-base font-bold text-slate-50 tracking-tight flex items-center gap-2"
        >
          <Layers class="w-4 h-4 text-accent" />
          <span>{group.domain}</span>
        </h2>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
          {#each group.items as item}
            <div
              class="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2"
            >
              <div class="font-semibold text-xs text-slate-50">{item.element}</div>
              <p class="text-caption text-slate-400 leading-relaxed">
                {item.rules}
              </p>
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>
</div>
