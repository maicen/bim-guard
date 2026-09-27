<script lang="ts">
  import { cn } from "../../../utils/cn";

  interface Props {
    class?: string;
  }

  let { class: className }: Props = $props();
</script>

<div
  data-sidebar="separator"
  class={cn("mx-2 my-1 h-px bg-border-default/60 shrink-0", className)}
></div>
