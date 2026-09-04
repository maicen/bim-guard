<script lang="ts">
  import { onMount, onDestroy, tick } from "svelte";
  import { ChevronLeft, ChevronRight, Loader2, AlertCircle } from "lucide-svelte";
  import { documentsApi } from "../api";

  interface Props {
    documentId: number;
    /** 1-based page to open on, when known (from GET /api/rules/{id}/source). */
    page?: number | null;
    /** Source snippet to highlight — matched against the PDF text layer, or the plain-text panel for non-PDF documents. */
    highlightText?: string | null;
  }

  let { documentId, page = null, highlightText = null }: Props = $props();

  let textLayerEl: HTMLDivElement = $state();
  let canvasEl: HTMLCanvasElement = $state();
  let textPanelEl: HTMLDivElement = $state();

  let loading = $state(true);
  let error: string | null = $state(null);
  let isPdf = $state(false);
  let plainText = $state("");
  let filename = $state("");

  let pdfDoc: any = $state(null);
  let currentPage = $state(1);
  let pageCount = $state(0);
  let renderTask: any = null;

  let loadedDocumentId: number | null = null;

  function normalize(text: string): string {
    return (text || "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  async function load() {
    if (loadedDocumentId === documentId) return;
    loadedDocumentId = documentId;
    loading = true;
    error = null;
    pdfDoc = null;
    isPdf = false;

    try {
      const url = documentsApi.getFileUrl(documentId);
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Failed to load document file (HTTP ${res.status})`);
      const contentType = res.headers.get("content-type") || "";
      const disposition = res.headers.get("content-disposition") || "";
      const nameMatch = disposition.match(/filename="?([^";]+)"?/);
      filename = nameMatch?.[1] || `document-${documentId}`;
      const buffer = await res.arrayBuffer();

      if (contentType.includes("pdf") || filename.toLowerCase().endsWith(".pdf")) {
        isPdf = true;
        await openPdf(buffer);
      } else {
        isPdf = false;
        const detail = await documentsApi.get(documentId);
        plainText = detail.extracted_text || "";
        loading = false;
        queueMicrotask(scrollToHighlightInText);
      }
    } catch (err: any) {
      error = err?.message || "Failed to load document.";
      loading = false;
    }
  }

  async function openPdf(buffer: ArrayBuffer) {
    const pdfjsLib = await import("pdfjs-dist");
    const workerUrl = (await import("pdfjs-dist/build/pdf.worker.mjs?url")).default;
    pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

    const doc = await pdfjsLib.getDocument({ data: buffer }).promise;
    pdfDoc = doc;
    pageCount = doc.numPages;
    currentPage = Math.min(Math.max(page || 1, 1), pageCount);
    loading = false;
    // canvasEl only mounts once Svelte flushes the DOM update from
    // `loading = false` (the template switches from the loading branch to
    // the canvas branch) — without this, renderCurrentPage() would run
    // against a not-yet-bound canvasEl and silently no-op.
    await tick();
    await renderCurrentPage();
  }

  const RENDER_TIMEOUT_MS = 20000;

  async function renderCurrentPage() {
    if (!pdfDoc || !canvasEl) return;
    if (renderTask) {
      try {
        renderTask.cancel();
      } catch {
        // ignore — a stale render being cancelled is expected
      }
    }

    const pdfjsLib = await import("pdfjs-dist");
    const pdfPage = await pdfDoc.getPage(currentPage);
    const viewport = pdfPage.getViewport({ scale: 1.4 });

    canvasEl.width = viewport.width;
    canvasEl.height = viewport.height;
    const ctx = canvasEl.getContext("2d");
    if (!ctx) return;

    renderTask = pdfPage.render({ canvasContext: ctx, viewport });
    try {
      await withTimeout(renderTask.promise, RENDER_TIMEOUT_MS, "Rendering this page took too long.");
    } catch (err: any) {
      if (err?.name === "RenderingCancelledException") return;
      error = err?.message || "Failed to render this page.";
      return;
    }

    if (textLayerEl) {
      // textLayerEl is an opaque mount target handed to pdf.js's own TextLayer
      // builder (like IfcViewer's canvas container) — Svelte never reconciles
      // its children, so clearing it imperatively before each re-render is the
      // correct, intended usage rather than state Svelte should own.
      // eslint-disable-next-line svelte/no-dom-manipulating
      textLayerEl.innerHTML = "";
      textLayerEl.style.width = `${viewport.width}px`;
      textLayerEl.style.height = `${viewport.height}px`;
      try {
        const textContent = await pdfPage.getTextContent();
        const layer = new (pdfjsLib as any).TextLayer({
          textContentSource: textContent,
          container: textLayerEl,
          viewport,
        });
        await withTimeout(layer.render(), RENDER_TIMEOUT_MS, "Rendering the text layer took too long.");
        highlightInPdfTextLayer();
      } catch {
        // Non-fatal: the page image itself already rendered above: losing the
        // text layer only means no selection/highlight overlay on this page.
      }
    }
  }

  function withTimeout<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => setTimeout(() => reject(new Error(message)), ms)),
    ]);
  }

  function highlightInPdfTextLayer() {
    if (!textLayerEl || !highlightText) return;
    const target = normalize(highlightText);
    if (!target) return;

    const spans = Array.from(textLayerEl.querySelectorAll("span")) as HTMLSpanElement[];
    let running = "";
    const ranges: { span: HTMLSpanElement; start: number; end: number }[] = [];
    for (const span of spans) {
      const text = normalize(span.textContent || "");
      const start = running.length;
      running += text + " ";
      ranges.push({ span, start, end: start + text.length });
    }

    const matchStart = running.indexOf(target);
    if (matchStart === -1) return;
    const matchEnd = matchStart + target.length;

    let firstMatch: HTMLSpanElement | null = null;
    for (const { span, start, end } of ranges) {
      if (end > matchStart && start < matchEnd) {
        span.classList.add("bg-amber-400/60", "rounded-sm");
        if (!firstMatch) firstMatch = span;
      }
    }
    firstMatch?.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  function scrollToHighlightInText() {
    if (!textPanelEl || !highlightText) return;
    const mark = textPanelEl.querySelector("mark");
    mark?.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  interface HighlightSplit {
    before: string;
    match: string;
    after: string;
  }

  function splitOnHighlight(text: string, highlight: string | null | undefined): HighlightSplit | null {
    if (!highlight) return null;
    const idx = text.toLowerCase().indexOf(highlight.toLowerCase());
    if (idx === -1) return null;
    return {
      before: text.slice(0, idx),
      match: text.slice(idx, idx + highlight.length),
      after: text.slice(idx + highlight.length),
    };
  }

  let highlightSplit = $derived(splitOnHighlight(plainText, highlightText));

  async function goToPage(next: number) {
    if (next < 1 || next > pageCount) return;
    currentPage = next;
    await renderCurrentPage();
  }

  onMount(() => {
    load();
  });

  onDestroy(() => {
    try {
      renderTask?.cancel();
    } catch {
      // ignore
    }
    pdfDoc?.destroy?.();
  });

  $effect(() => {
    if (documentId !== loadedDocumentId) {
      load();
    }
  });
</script>

<div class="flex h-full min-h-[60vh] flex-col">
  {#if loading}
    <div class="flex flex-1 items-center justify-center gap-2 text-sm text-slate-400">
      <Loader2 class="h-5 w-5 animate-spin" />
      <span>Loading document…</span>
    </div>
  {:else if error}
    <div class="flex flex-1 flex-col items-center justify-center gap-2 text-sm text-red-400">
      <AlertCircle class="h-6 w-6" />
      <span>{error}</span>
    </div>
  {:else if isPdf}
    <div class="flex flex-1 flex-col overflow-hidden">
      <div class="flex-1 overflow-auto bg-slate-950/60 p-4">
        <div class="relative mx-auto w-fit">
          <canvas bind:this={canvasEl} class="block rounded-lg shadow-lg"></canvas>
          <div bind:this={textLayerEl} class="pdf-text-layer"></div>
        </div>
      </div>
      {#if pageCount > 1}
        <div
          class="flex shrink-0 items-center justify-center gap-4 border-t border-slate-800 bg-slate-950 px-4 py-2.5"
        >
          <button
            type="button"
            onclick={() => goToPage(currentPage - 1)}
            disabled={currentPage <= 1}
            class="rounded-lg p-1.5 text-slate-300 hover:bg-slate-800 disabled:opacity-30"
            aria-label="Previous page"
          >
            <ChevronLeft class="h-4 w-4" />
          </button>
          <span class="text-xs text-slate-400">Page {currentPage} of {pageCount}</span>
          <button
            type="button"
            onclick={() => goToPage(currentPage + 1)}
            disabled={currentPage >= pageCount}
            class="rounded-lg p-1.5 text-slate-300 hover:bg-slate-800 disabled:opacity-30"
            aria-label="Next page"
          >
            <ChevronRight class="h-4 w-4" />
          </button>
        </div>
      {/if}
    </div>
  {:else}
    <div
      bind:this={textPanelEl}
      class="flex-1 overflow-y-auto whitespace-pre-wrap bg-slate-950/60 p-6 font-mono text-xs leading-relaxed text-slate-300"
    >
      {#if highlightSplit}
        {highlightSplit.before}<mark class="rounded-sm bg-amber-400/60 text-slate-950">{highlightSplit.match}</mark
        >{highlightSplit.after}
      {:else}
        {plainText || "No extracted text found."}
      {/if}
    </div>
  {/if}
</div>

<style>
  /* Standard pdf.js text-layer positioning — spans are transparent and laid
     out to match the canvas glyphs exactly, so selection/highlighting lines
     up with what's visually rendered underneath. */
  .pdf-text-layer {
    position: absolute;
    inset: 0;
    overflow: hidden;
    line-height: 1;
    text-align: initial;
    transform-origin: 0 0;
  }
  .pdf-text-layer :global(span),
  .pdf-text-layer :global(br) {
    color: transparent;
    position: absolute;
    white-space: pre;
    cursor: text;
    transform-origin: 0% 0%;
  }
</style>
