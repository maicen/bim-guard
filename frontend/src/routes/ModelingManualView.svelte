<script lang="ts">
  import { Box, Layers, ShieldCheck, CheckCircle2 } from 'lucide-svelte';

  const GUIDES = [
    {
      domain: 'Architecture & Egress',
      items: [
        {
          element: 'Doors & Clearances',
          rules: 'Doors must have clear width >= 810mm and explicit fire ratings (e.g. 45 min for separations) defined in Pset_DoorCommon.',
        },
        {
          element: 'Windows & Daylighting',
          rules: 'Unobstructed glass area must be >= 10% of floor area for habitable spaces (Ontario Building Code Part 9). Ensure IfcWindow instances belong to valid IfcSpace boundaries.',
        },
        {
          element: 'Stairs & Handrails',
          rules: 'Riser height must not exceed 200mm, with minimum tread depth of 255mm. Assign proper IfcStairFlight and IfcRailing entities.',
        },
      ],
    },
    {
      domain: 'MEP & Piping',
      items: [
        {
          element: 'Material Specifications',
          rules: 'Assign explicit material definitions (e.g. Copper, Galvanized Steel, PVC) to prevent galvanic coupling risks under GC-001.',
        },
        {
          element: 'Fluid Service & Insulation',
          rules: 'Specify system fluid types and operating temperatures to accurately calculate microbiological corrosion (MC-001) susceptibility.',
        },
        {
          element: 'Seismic Clearance Volume',
          rules: 'Model pipe runs with proper seismic hanger allowances and Blue Halo clearance volumes around equipment interfaces.',
        },
      ],
    },
  ];
</script>

<div class="space-y-6 max-w-4xl mx-auto">
  <!-- Header -->
  <div>
    <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Manuals</div>
    <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">3D Modeling Reference Manual</h1>
    <p class="text-xs sm:text-sm text-slate-400">
      OpenBIM modeling conventions to ensure IFC models pass automated compliance rules.
    </p>
  </div>

  <div class="space-y-6">
    {#each GUIDES as group}
      <div class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4">
        <h2 class="text-base font-bold text-white tracking-tight flex items-center gap-2">
          <Layers class="w-4 h-4 text-[#0071e3]" />
          <span>{group.domain}</span>
        </h2>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
          {#each group.items as item}
            <div class="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <div class="font-semibold text-xs text-white">{item.element}</div>
              <p class="text-[11px] text-slate-400 leading-relaxed">{item.rules}</p>
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>
</div>

