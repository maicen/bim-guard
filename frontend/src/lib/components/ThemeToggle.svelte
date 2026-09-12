<script lang="ts">
  import { Sun, Moon } from "lucide-svelte";
  import { resolvedTheme, themeMode, toggleTheme } from "../theme";

  interface Props {
    compact?: boolean;
  }

  let { compact = false }: Props = $props();
</script>

<button
  type="button"
  onclick={toggleTheme}
  class="group relative inline-flex items-center justify-center overflow-hidden rounded-xl border border-border-default p-2 text-fg-muted transition-all duration-200 hover:bg-surface-hover hover:text-fg-primary focus:outline-hidden focus:ring-2 focus:ring-blue-500/40"
  title={$resolvedTheme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
  aria-label={$resolvedTheme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
>
  <div class="relative flex h-4 w-4 items-center justify-center">
    {#if $resolvedTheme === "dark"}
      <Moon
        class="h-4 w-4 transform text-fg-secondary transition-all duration-300 group-hover:-rotate-12 group-hover:scale-110 group-hover:text-blue-400"
      />
    {:else}
      <Sun
        class="h-4 w-4 transform text-amber-500 transition-all duration-300 group-hover:rotate-45 group-hover:scale-110 group-hover:text-amber-600"
      />
    {/if}
  </div>

  {#if !compact}
    <span class="sr-only">Toggle theme</span>
  {/if}
</button>
