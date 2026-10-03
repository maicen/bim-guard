<script lang="ts">
  import { onMount } from "svelte";
  import { ShieldCheck } from "lucide-svelte";
  import type { OAuthAuthorizationDetails } from "@supabase/supabase-js";
  import { supabase } from "../lib/supabaseClient";
  import { stashPendingConsent } from "../lib/oauthConsent";
  import { Button, Card } from "../lib/components/ui";

  let details = $state<OAuthAuthorizationDetails | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);

  const authorizationId = new URLSearchParams(window.location.search).get("authorization_id");

  onMount(async () => {
    if (!authorizationId) {
      error = "Missing authorization_id. Restart the sign-in from your MCP client.";
      return;
    }
    const { data: sessionData } = await supabase.auth.getSession();
    if (!sessionData.session) {
      stashPendingConsent(window.location.href);
      window.location.replace("/#/login");
      return;
    }
    const { data, error: detailsError } = await supabase.auth.oauth.getAuthorizationDetails(authorizationId);
    if (detailsError || !data) {
      error = detailsError?.message ?? "Invalid authorization request.";
    } else if ("authorization_id" in data) {
      details = data;
    } else {
      // Already consented to this client: go straight back to it.
      window.location.replace(data.redirect_url);
    }
  });

  async function decide(approve: boolean) {
    if (!authorizationId) return;
    busy = true;
    const { data, error: decisionError } = approve
      ? await supabase.auth.oauth.approveAuthorization(authorizationId)
      : await supabase.auth.oauth.denyAuthorization(authorizationId);
    if (decisionError || !data) {
      error = decisionError?.message ?? "Could not record your decision.";
      busy = false;
      return;
    }
    window.location.replace(data.redirect_url);
  }

  let scopes = $derived(details?.scope?.trim() ? details.scope.trim().split(/\s+/) : []);
</script>

<main class="min-h-screen bg-surface-canvas flex items-center justify-center p-4">
  <Card class="w-full max-w-md p-6 space-y-4">
    <div class="flex items-center gap-2 text-fg-primary">
      <ShieldCheck class="h-5 w-5 text-accent" />
      <h1 class="text-lg font-semibold">Authorize application</h1>
    </div>

    {#if error}
      <p class="rounded-md border border-critical-border bg-critical-bg p-3 text-sm text-critical" role="alert">
        {error}
      </p>
    {:else if details}
      <p class="text-sm text-fg-secondary">
        <strong class="text-fg-primary">{details.client.name}</strong> wants to access BIM-Guard as
        <strong class="text-fg-primary">{details.user.email}</strong>. It can read the projects and
        rulesets you can access and run compliance analyses on your behalf.
      </p>
      <p class="text-xs text-fg-muted break-all">Redirects to {details.redirect_uri}</p>
      {#if scopes.length}
        <ul class="list-disc pl-5 text-sm text-fg-secondary">
          {#each scopes as scope (scope)}<li>{scope}</li>{/each}
        </ul>
      {/if}
      <div class="flex justify-end gap-2 pt-2">
        <Button variant="outline" disabled={busy} onclick={() => decide(false)}>Deny</Button>
        <Button variant="primary" loading={busy} onclick={() => decide(true)}>Approve</Button>
      </div>
    {:else}
      <p class="text-sm text-fg-muted">Loading…</p>
    {/if}
  </Card>
</main>
