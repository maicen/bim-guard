import { mount } from "svelte";
// Self-hosted fonts (unicode-range subsets, fetched on demand): no render-blocking third-party stylesheet.
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "./app.css";
import App from "./App.svelte";
import { CONSENT_PATH, watchPendingConsent } from "./lib/oauthConsent";

const target = document.getElementById("app")!;
// Drop the static crawl fallback in index.html: mount() appends rather than
// replaces, which left a second banner landmark and a duplicate <h1>.
target.replaceChildren();

// Supabase Auth's OAuth 2.1 server (MCP client sign-in) redirects here for
// consent; it is a plain path, outside the hash-routed app shell.
const onConsentPage = window.location.pathname === CONSENT_PATH;
if (!onConsentPage) watchPendingConsent();
// PERF: the consent view (Card, sidebar context, extra bits-ui) is only for its
// own URL, so keep it out of the entry chunk every other visitor downloads.
// (No top-level await: the build target does not support it.)
const component = onConsentPage
  ? import("./routes/OAuthConsentView.svelte").then((m) => m.default)
  : Promise.resolve(App);
const app = component.then((c) => mount(c, { target }));

export default app;
