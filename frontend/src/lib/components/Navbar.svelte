<script lang="ts">
  import { onMount } from 'svelte';

  export let activeTab: 'projects' | 'analyze' | 'rules' | 'viewer' = 'projects';
  export let onSelectTab: (tab: 'projects' | 'analyze' | 'rules' | 'viewer') => void;

  let apiOnline = false;

  async function checkHealth() {
    try {
      const res = await fetch('/api/health');
      apiOnline = res.ok;
    } catch {
      apiOnline = false;
    }
  }

  onMount(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  });
</script>

<header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-lg bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center font-bold text-white shadow-lg shadow-emerald-500/20">
        BG
      </div>
      <div>
        <div class="flex items-center gap-2">
          <span class="font-bold tracking-tight text-white text-lg">BIM Guard</span>
          <span class="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            FastAPI + Svelte
          </span>
        </div>
        <p class="text-xs text-slate-400">OpenBIM Compliance Engine</p>
      </div>
    </div>

    <!-- Navigation tabs -->
    <nav class="flex items-center gap-1 bg-slate-950/60 p-1 rounded-lg border border-slate-800">
      <button
        class="px-3.5 py-1.5 rounded-md text-sm font-medium transition-colors {activeTab === 'projects' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'}"
        on:click={() => onSelectTab('projects')}
      >
        Projects
      </button>
      <button
        class="px-3.5 py-1.5 rounded-md text-sm font-medium transition-colors {activeTab === 'analyze' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'}"
        on:click={() => onSelectTab('analyze')}
      >
        Compliance Audit
      </button>
      <button
        class="px-3.5 py-1.5 rounded-md text-sm font-medium transition-colors {activeTab === 'rules' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'}"
        on:click={() => onSelectTab('rules')}
      >
        Rule Library
      </button>
      <button
        class="px-3.5 py-1.5 rounded-md text-sm font-medium transition-colors {activeTab === 'viewer' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'}"
        on:click={() => onSelectTab('viewer')}
      >
        3D Viewer
      </button>
    </nav>

    <!-- Health & Gateway status -->
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border {apiOnline ? 'bg-emerald-950/50 text-emerald-400 border-emerald-800/60' : 'bg-rose-950/50 text-rose-400 border-rose-800/60'}">
        <span class="w-1.5 h-1.5 rounded-full {apiOnline ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}"></span>
        {apiOnline ? 'FastAPI Gateway Active' : 'Gateway Offline'}
      </span>
      <a
        href="/api/docs"
        target="_blank"
        rel="noopener noreferrer"
        class="text-xs text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-slate-800 transition-colors"
      >
        API Docs ↗
      </a>
    </div>
  </div>
</header>

