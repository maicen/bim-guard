import { mount } from "svelte";
import "./app.css";
import App from "./App.svelte";

const target = document.getElementById("app")!;
// Drop the static crawl fallback in index.html: mount() appends rather than
// replaces, which left a second banner landmark and a duplicate <h1>.
target.replaceChildren();

const app = mount(App, { target });

export default app;
