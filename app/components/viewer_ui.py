"""Presentation layer for the multi-model IFC viewer.

The single-model viewer (``app/routes/viewer.py``) renders one project's
attached ``ifc_file_path``. This module renders every IFC recorded against a
project in ``uploaded_files`` at once, so a federated model split across
several files can be inspected together.

The browser does the federation: the page loads each model into one
``initViewer`` instance over the per-file download route, rather than the
server merging anything. That keeps the route a metadata query and leaves the
IFC bytes untouched.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from fasthtml.common import Div, P, Script, Style

from app.components.ui import Card, CardContent, CardHeader, CardTitle, Checkbox

#: DOM id the viewer mounts into. Deliberately *not* ``viewer-container``: the
#: single-model page owns that id along with a block of ``#viewer-container``
#: CSS, and reusing it would make either page's rules apply to the other.
VIEWER_CONTAINER_ID = "multi-viewer-container"

#: Pinned to match ``app/routes/viewer.py`` -- two web-ifc versions on one
#: origin would load two WASM runtimes.
WEB_IFC_IMPORTMAP = '{"imports":{"web-ifc":"https://unpkg.com/web-ifc@0.0.77/web-ifc-api.js"}}'

MULTI_VIEWER_STYLES = f"""
#{VIEWER_CONTAINER_ID} {{
    height: clamp(32rem, 68vh, 56rem);
}}
#{VIEWER_CONTAINER_ID} .bimguard-topics-grid {{
    display: grid;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
}}
#{VIEWER_CONTAINER_ID} .bimguard-viewport {{
    display: block;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
}}
#{VIEWER_CONTAINER_ID} .bimguard-topics-toolbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}}
#{VIEWER_CONTAINER_ID} .bimguard-topics-actions {{
    display: flex;
    flex: 0 0 auto;
    gap: 0.5rem;
}}
@media (max-width: 900px) {{
    #{VIEWER_CONTAINER_ID} {{
        height: 44rem;
    }}
}}
"""

#: Loads every model into one viewer, then wires the per-model checkboxes to
#: three.js visibility. Only the first load replaces the scene; the rest are
#: additive, which is what makes this a *multi*-model viewer.
_LOADER_TEMPLATE = """
import { initViewer } from '/static/js/viewer/ifc-viewer.js';

async function startMultiViewer() {
    const models = MODELS_PLACEHOLDER;
    const status = document.getElementById('STATUS_ID_PLACEHOLDER');
    const viewerAPI = await initViewer('CONTAINER_ID_PLACEHOLDER');
    if (!viewerAPI) return;

    const loaded = new Map();
    let failures = 0;
    for (const [index, model] of models.entries()) {
        try {
            const handle = await viewerAPI.loadIfc(model.url, {
                replace: index === 0,
                name: `${model.filename} (#${model.file_id})`,
            });
            loaded.set(String(model.file_id), handle);
        } catch (error) {
            failures += 1;
            console.error(`Could not load ${model.filename}`, error);
        }
    }

    if (status) {
        const ok = models.length - failures;
        status.textContent = failures
            ? `${ok} of ${models.length} models loaded — ${failures} failed, see the console.`
            : `${ok} model${ok === 1 ? '' : 's'} loaded.`;
    }

    for (const box of document.querySelectorAll('[data-model-toggle]')) {
        box.addEventListener('change', async () => {
            const handle = loaded.get(box.dataset.modelToggle);
            if (handle && handle.object) {
                handle.object.visible = box.checked;
                await viewerAPI.refresh();
            }
        });
    }
}

if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', startMultiViewer);
} else {
    startMultiViewer();
}
"""


@dataclass(frozen=True)
class ViewerModel:
    """One IFC file offered to the multi-model viewer.

    Attributes:
        file_id: ``uploaded_files.id``. Identifies the model in the DOM and in
            the download URL.
        filename: Original upload name, shown in the model list.
        url: Route serving the raw IFC bytes for this file.
        size_bytes: Stored size, rendered as a hint. Zero when unrecorded.
        created_at: ISO-8601 upload timestamp, or ``""`` when unrecorded.
    """

    file_id: int
    filename: str
    url: str
    size_bytes: int = 0
    created_at: str = ""

    def as_payload(self) -> dict:
        """Return the subset the browser loader needs."""
        return {"file_id": self.file_id, "filename": self.filename, "url": self.url}


def _embed_json(value: object) -> str:
    """Serialise ``value`` for embedding inside a ``<script>`` element.

    ``<`` is escaped because a filename containing ``</script>`` would
    otherwise close the element early -- upload names are user-supplied and
    only stripped of their directory component.
    """
    return json.dumps(value).replace("<", "\\u003c")


def _size_label(size_bytes: int) -> str:
    """Return a human-readable size, or ``""`` when the size is unknown."""
    if size_bytes <= 0:
        return ""
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def model_list(models: list[ViewerModel]) -> Card:
    """Render the per-model visibility checklist."""
    rows = []
    for model in models:
        size = _size_label(model.size_bytes)
        rows.append(
            Div(
                Checkbox(
                    checked=True,
                    id=f"model-toggle-{model.file_id}",
                    data_model_toggle=str(model.file_id),
                ),
                Div(
                    P(model.filename, cls="text-sm font-medium"),
                    P(
                        " · ".join(part for part in (size, model.created_at) if part),
                        cls="text-xs text-muted-foreground",
                    ),
                    cls="min-w-0",
                ),
                cls="flex items-start gap-3",
            )
        )
    return Card(
        CardHeader(CardTitle(f"Models ({len(models)})")),
        CardContent(Div(*rows, cls="space-y-3")),
    )


def multi_model_viewer(
    models: list[ViewerModel],
    *,
    project_name: str = "",
) -> Div:
    """Render the multi-model viewer for ``models``.

    Args:
        models: IFC files to federate. An empty list renders the empty state
            rather than an inert viewport.
        project_name: Shown in the heading when given.

    Returns:
        The page body. Callers wrap it in ``Title`` + ``DashboardLayout``.
    """
    heading = f"Model Viewer — {project_name}" if project_name else "Model Viewer"

    if not models:
        return Div(
            Card(
                CardHeader(CardTitle(heading)),
                CardContent(
                    P(
                        "No IFC models have been uploaded to this project yet.",
                        cls="text-sm text-muted-foreground",
                    )
                ),
            ),
            cls="space-y-4",
        )

    status_id = "multi-viewer-status"
    loader = (
        _LOADER_TEMPLATE.replace(
            "MODELS_PLACEHOLDER", _embed_json([model.as_payload() for model in models])
        )
        .replace("CONTAINER_ID_PLACEHOLDER", VIEWER_CONTAINER_ID)
        .replace("STATUS_ID_PLACEHOLDER", status_id)
    )

    return Div(
        Card(
            CardHeader(CardTitle(heading)),
            CardContent(
                P(
                    "Loading models…",
                    id=status_id,
                    cls="text-sm text-muted-foreground",
                )
            ),
        ),
        model_list(models),
        Div(
            id=VIEWER_CONTAINER_ID,
            cls="w-full rounded-xl shadow-xl overflow-hidden border border-border relative z-10",
            style="background-color: hsl(var(--foreground) / 0.95);",
        ),
        Style(MULTI_VIEWER_STYLES),
        Script(WEB_IFC_IMPORTMAP, type="importmap"),
        Script(loader, type="module"),
        cls="space-y-4",
    )
