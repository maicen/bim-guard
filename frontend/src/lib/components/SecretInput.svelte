<script lang="ts">
  import { Eye, EyeOff } from "lucide-svelte";

  interface Props {
    value: string;
    id?: string;
    placeholder?: string;
    required?: boolean;
    class?: string;
  }

  let {
    value = $bindable(""),
    id = "",
    placeholder = "",
    required = false,
    class: className = "",
  }: Props = $props();

  let revealed = $state(false);
</script>

<!--
  Masked API-key/secret field shared by every provider config form (Document
  Parsing and LLM Providers) so credential handling looks and behaves the
  same everywhere — a plain type="password" input with a show/hide toggle.
-->
<div class="relative">
  <input
    {id}
    type={revealed ? "text" : "password"}
    autocomplete="off"
    {required}
    bind:value
    {placeholder}
    class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 pr-9 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-hidden {className}"
  />
  <button
    type="button"
    onclick={() => (revealed = !revealed)}
    tabindex="-1"
    class="absolute inset-y-0 right-2 flex items-center text-slate-500 transition-colors hover:text-slate-300"
    aria-label={revealed ? "Hide secret" : "Show secret"}
  >
    {#if revealed}
      <EyeOff class="h-3.5 w-3.5" />
    {:else}
      <Eye class="h-3.5 w-3.5" />
    {/if}
  </button>
</div>
