// Run the BCF archive filter off the main thread.
//
// WHY A WORKER
//
//     JSZip defers every chunk of every inflate through setImmediate, which in
//     a browser is the setimmediate polyfill's postMessage task -- not a
//     microtask. On the main thread those tasks queue behind rendering and
//     input, so scanning 2,764 entries measured 58.6 s in Edge against 365 ms
//     in Node, where setImmediate is real and sub-millisecond. A worker gives
//     that task queue nothing else to compete with, and the page stays
//     responsive while it drains instead of freezing.
//
//     The archive is cloned in rather than transferred, so the caller keeps its
//     bytes and can still run the filter inline if this worker turns out to be
//     unusable. The reduced archive goes back transferred, which is free.
//
// The caller falls back to running the filter inline if this worker cannot be
// constructed, so nothing here is load-bearing for correctness.

import JSZip from "https://esm.sh/jszip@3.10.1";
import { filterBcfArchive } from "./bcf-filter.js?v=viewer-isolate-5";

self.onmessage = async (event) => {
  const { buffer, elementGuid } = event.data || {};
  try {
    const result = await filterBcfArchive(JSZip, buffer, elementGuid);
    // `data` is null when nothing matched; only transfer a real buffer.
    const transfer = result.data ? [result.data.buffer] : [];
    self.postMessage({ ok: true, result }, transfer);
  } catch (error) {
    self.postMessage({ ok: false, error: String(error?.stack || error?.message || error) });
  }
};
