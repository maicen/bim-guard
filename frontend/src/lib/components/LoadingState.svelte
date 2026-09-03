<script lang="ts">
  interface Props {
    message?: string;
    subMessage?: string;
  }

  let { message = "Loading...", subMessage = "" }: Props = $props();
</script>

<div class="space-y-2 p-12 text-center text-xs text-slate-400 duration-200 animate-in fade-in">
  <div
    class="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent"
  ></div>
  <div class="font-medium text-slate-300">{message}</div>
  {#if subMessage}
    <div class="font-mono text-caption text-slate-500">{subMessage}</div>
  {/if}
</div>
