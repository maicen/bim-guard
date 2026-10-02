<script lang="ts">
  import type { Component } from "svelte";
  import LoadingState from "./LoadingState.svelte";

  // Code-splits a route: `loader` is a dynamic `import()` of the view, fetched
  // the first time that view is shown. Remaining props are forwarded to it.
  interface Props {
    loader: () => Promise<{ default: Component<any> }>;
    [key: string]: unknown;
  }

  let { loader, ...rest }: Props = $props();
  let loaded = $derived(loader());
</script>

{#await loaded}
  <LoadingState message="Loading view…" />
{:then module}
  {@const View = module.default}
  <View {...rest} />
{/await}
