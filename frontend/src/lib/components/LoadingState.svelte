<script lang="ts">
  interface Props {
    message?: string;
    subMessage?: string;
  }

  let { message = "Loading...", subMessage = "" }: Props = $props();
</script>

<div class="space-y-2 p-12 text-center text-xs text-fg-muted duration-200 animate-in fade-in">
  <div
    class="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent"
  ></div>
  <div class="font-medium text-fg-secondary">{message}</div>
  {#if subMessage}
    <div class="font-mono text-caption text-fg-muted">{subMessage}</div>
  {/if}
</div>
