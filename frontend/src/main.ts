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

const target = document.getElementById("app")!;
// Drop the static crawl fallback in index.html: mount() appends rather than
// replaces, which left a second banner landmark and a duplicate <h1>.
target.replaceChildren();

const app = mount(App, { target });

export default app;
