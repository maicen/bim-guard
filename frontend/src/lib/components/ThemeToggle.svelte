<script lang="ts">
  import { Sun, Moon } from 'lucide-svelte';
  import { resolvedTheme, themeMode, toggleTheme } from '../theme';

  export let compact: boolean = false;
</script>

<button
  type="button"
  on:click={toggleTheme}
  class="relative inline-flex items-center justify-center rounded-xl p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800/70 border border-slate-800/80 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500/40 group overflow-hidden"
  title={$resolvedTheme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
  aria-label={$resolvedTheme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
>
  <div class="relative w-4 h-4 flex items-center justify-center">
    {#if $resolvedTheme === 'dark'}
      <Moon
        class="w-4 h-4 text-slate-300 group-hover:text-blue-400 transition-all duration-300 transform group-hover:-rotate-12 group-hover:scale-110"
      />
    {:else}
      <Sun
        class="w-4 h-4 text-amber-500 group-hover:text-amber-600 transition-all duration-300 transform group-hover:rotate-45 group-hover:scale-110"
      />
    {/if}
  </div>

  {#if !compact}
    <span class="sr-only">Toggle theme</span>
  {/if}
</button>
