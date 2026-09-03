import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  // Consult https://svelte.dev/docs#compile-time-svelte-preprocess
  // for more information about preprocessors
  preprocess: vitePreprocess(),

  vitePlugin: {
    /**
     * Enforce runes mode for this project's own components only.
     *
     * A blanket `compilerOptions.runes` would also apply to dependencies, and
     * lucide-svelte still ships legacy components that use `$$props`. Scoping
     * it here turns reintroduced legacy syntax (`export let`, `on:click`, `$:`,
     * `<slot>`) into a compile error in src/ while leaving node_modules alone.
     */
    dynamicCompileOptions({ filename }) {
      if (!filename.includes('node_modules')) {
        return { runes: true };
      }
    },
  },
};

