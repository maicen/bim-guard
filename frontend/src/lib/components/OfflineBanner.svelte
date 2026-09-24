<script lang="ts">
  import { WifiOff } from "lucide-svelte";
  import { networkStatus } from "../stores/network.svelte";
</script>

<!--
  Fixed to the top of the viewport regardless of which view is mounted, same
  placement rationale as Toaster -- a dropped connection should be obvious
  no matter what the user is looking at, not just to whichever request
  happens to fail first.
-->
{#if !networkStatus.online}
  <div
    role="status"
    aria-live="polite"
    class="fixed inset-x-0 top-0 z-100 flex items-center justify-center gap-2 bg-warning-bg px-4 py-2 text-xs font-semibold text-warning shadow-md"
  >
    <WifiOff class="h-3.5 w-3.5 shrink-0" />
    <span>You're offline. Changes won't save until your connection comes back.</span>
  </div>
{/if}
