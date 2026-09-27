<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    pauseOnHover?: boolean;
    durationSeconds?: number;
    class?: string;
    children?: Snippet;
  }

  let {
    pauseOnHover = true,
    durationSeconds = 30,
    class: className,
    children,
  }: Props = $props();
</script>

<div
  class={cn("relative w-full overflow-hidden mask-fade-edges", className)}
>
  <div
    class={cn(
      "animate-marquee flex items-center gap-6",
      pauseOnHover && "hover:[animation-play-state:paused]"
    )}
    style="animation-duration: {durationSeconds}s"
  >
    <!-- Slot rendered twice for infinite loop continuity -->
    <div class="flex shrink-0 items-center gap-6">
      {@render children?.()}
    </div>
    <div class="flex shrink-0 items-center gap-6" aria-hidden="true">
      {@render children?.()}
    </div>
  </div>
</div>
