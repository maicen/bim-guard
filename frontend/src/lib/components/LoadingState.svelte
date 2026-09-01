<script lang="ts">
  export let message: string = "Loading...";
  export let subMessage: string = "";
</script>

<div class="p-12 text-center text-xs text-slate-400 space-y-2 animate-in fade-in duration-200">
  <div
    class="animate-spin w-6 h-6 border-2 border-[#0071e3] border-t-transparent rounded-full mx-auto"
  ></div>
  <div class="font-medium text-slate-300">{message}</div>
  {#if subMessage}
    <div class="text-[11px] text-slate-500 font-mono">{subMessage}</div>
  {/if}
</div>
