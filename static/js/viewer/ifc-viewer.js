import * as BUI from "https://esm.sh/@thatopen/ui@3.4.10";
import * as OBC from "https://esm.sh/@thatopen/components@3.4.8?external=web-ifc&deps=three@0.182.0,@thatopen/fragments@3.4.7";
import * as OBF from "https://esm.sh/@thatopen/components-front@3.4.4?external=web-ifc&deps=@thatopen/components@3.4.8,@thatopen/fragments@3.4.7,three@0.182.0";
import * as CUI from "https://esm.sh/@thatopen/ui-obc@3.4.2?external=web-ifc&deps=@thatopen/ui@3.4.10,@thatopen/components@3.4.8,three@0.182.0,@thatopen/fragments@3.4.7";
import * as THREE from "https://esm.sh/three@0.182.0";

const ERROR_HIGHLIGHT_STYLE = "bimguard-error";

// The BCF viewpoints the corrosion engine generates carry the failing
// element's GUID in their selection (see bcf_generator._viewpoint_xml), but
// Viewpoint.go() only moves the camera and applies visibility — it never
// colors the linked component. Patching go() once here means every way a
// viewpoint can be shown (the topic list's row click below, and the native
// eye-icon button ui-obc renders per viewpoint) highlights the offending
// element in red instead of just zooming to it.
function installErrorHighlighting(components, world) {
    components.get(OBC.Raycasters).get(world);
    const highlighter = components.get(OBF.Highlighter);
    highlighter.setup({ world, selectEnabled: false, autoHighlightOnClick: false });
    highlighter.styles.set(ERROR_HIGHLIGHT_STYLE, {
        color: new THREE.Color("red"),
        opacity: 1,
        transparent: false,
        renderedFaces: 0,
    });

    const hider = components.get(OBC.Hider);

    // Tracks the ModelIdMap behind whatever is currently highlighted (a single
    // topic's viewpoint selection, or the joined selection of a multi-select),
    // so the "Isolate" toolbar button knows what to show/hide without having
    // to recompute it, and so isolate mode can follow the selection as it changes.
    let currentSelectionMap = null;
    let isolateActive = false;
    const selectionListeners = new Set();

    async function applyIsolation(map) {
        if (map) {
            await hider.isolate(map);
        } else {
            await hider.set(true);
        }
    }

    function setSelectionMap(map) {
        currentSelectionMap = map;
        if (isolateActive) applyIsolation(map);
        for (const listener of selectionListeners) listener(map);
    }

    function toggleIsolate() {
        isolateActive = !isolateActive;
        applyIsolation(isolateActive ? currentSelectionMap : null);
        return isolateActive;
    }

    function resetIsolate() {
        isolateActive = false;
        currentSelectionMap = null;
        hider.set(true);
    }

    const originalGo = OBC.Viewpoint.prototype.go;
    OBC.Viewpoint.prototype.go = async function highlightingGo(config) {
        await originalGo.call(this, config);
        await highlighter.clear(ERROR_HIGHLIGHT_STYLE);
        const selectionMap = await this.getSelectionMap();
        const map = OBC.ModelIdMapUtils.isEmpty(selectionMap) ? null : selectionMap;
        setSelectionMap(map);
        if (map) {
            await highlighter.highlightByID(ERROR_HIGHLIGHT_STYLE, selectionMap, false, false);
        }
    };

    // Highlights every element linked to the given topics at once (used for
    // the topics table's checkbox multi-select), replacing whatever a single
    // go() call highlighted.
    async function highlightTopics(topicList) {
        const viewpoints = components.get(OBC.Viewpoints);
        const maps = [];
        for (const topic of topicList) {
            const viewpointGuid = topic.viewpoints.values().next().value;
            const viewpoint = viewpointGuid ? viewpoints.list.get(viewpointGuid) : null;
            if (!viewpoint) continue;
            const map = await viewpoint.getSelectionMap();
            if (!OBC.ModelIdMapUtils.isEmpty(map)) maps.push(map);
        }
        await highlighter.clear(ERROR_HIGHLIGHT_STYLE);
        const joined = maps.length > 0 ? OBC.ModelIdMapUtils.join(maps) : null;
        setSelectionMap(joined);
        if (joined) {
            await highlighter.highlightByID(ERROR_HIGHLIGHT_STYLE, joined, false, false);
        }
    }

    return {
        highlightTopics,
        isolate: {
            toggle: toggleIsolate,
            reset: resetIsolate,
            isActive: () => isolateActive,
            hasSelection: () => currentSelectionMap !== null,
            onSelectionChange: (cb) => selectionListeners.add(cb),
        },
    };
}

const USERS = {
    "reviewer@bimguard.local": { name: "BIM Guard Reviewer" },
    "coordinator@bimguard.local": { name: "BIM Coordinator" },
};

function createTopicPanel(components, topics, world) {
    const renderTopicPanel = (topic) => {
        const panel = BUI.Component.create(() => {
            if (!topic) {
                return BUI.html`
                    <bim-panel>
                        <bim-panel-section label="Topic details" icon="material-symbols:info-outline">
                            <bim-label style="white-space: normal">
                                Select a topic to inspect its information, comments, viewpoints, and relations.
                            </bim-label>
                        </bim-panel-section>
                    </bim-panel>
                `;
            }

            const [information] = CUI.sections.topicInformation({
                components,
                topic,
                styles: { users: USERS },
            });
            const [comments] = CUI.sections.topicComments({
                topic,
                styles: USERS,
            });
            const [viewpoints] = CUI.sections.topicViewpoints({
                components,
                topic,
                world,
            });
            const [relations] = CUI.sections.topicRelations({ components, topic });

            return BUI.html`
                <bim-panel>
                    <bim-panel-section label="Information" icon="material-symbols:info-outline">
                        ${information}
                    </bim-panel-section>
                    <bim-panel-section label="Comments" icon="material-symbols:comment-outline">
                        ${comments}
                    </bim-panel-section>
                    <bim-panel-section label="Viewpoints" icon="material-symbols:photo-camera-outline">
                        ${viewpoints}
                    </bim-panel-section>
                    <bim-panel-section label="Related topics" icon="material-symbols:link">
                        ${relations}
                    </bim-panel-section>
                </bim-panel>
            `;
        });
        return panel;
    };

    let selectedTopic;
    const topicPanel = document.createElement("div");
    topicPanel.style.minWidth = "0";
    topicPanel.style.minHeight = "0";
    const updateTopicPanel = ({ topic } = {}) => {
        if (topic) selectedTopic = topic;
        topicPanel.replaceChildren(renderTopicPanel(selectedTopic));
    };
    updateTopicPanel();

    topics.list.onItemUpdated.add(() => updateTopicPanel());
    return [topicPanel, updateTopicPanel];
}

function createTopicsWorkspace(components, world, viewport, highlightTopics) {
    const topics = components.get(OBC.BCFTopics);
    topics.setup({
        users: new Set(Object.keys(USERS)),
        labels: new Set(["Architecture", "Structure", "MEP", "Compliance"]),
    });

    const viewpoints = components.get(OBC.Viewpoints);
    topics.list.onItemSet.add(({ value: topic }) => {
        if (topic.viewpoints.size > 0) return;
        const viewpoint = viewpoints.create();
        viewpoint.world = world;
        topic.viewpoints.add(viewpoint.guid);
    });

    const [topicsList] = CUI.tables.topicsList({
        components,
        dataStyles: { users: USERS },
    });
    topicsList.selectableRows = true;
    const updateMultiHighlight = () => {
        const selected = [...topicsList.selection]
            .map(({ Guid }) => (Guid ? topics.list.get(Guid) : null))
            .filter(Boolean);
        highlightTopics(selected);
    };
    topicsList.addEventListener("dataselected", updateMultiHighlight);
    topicsList.addEventListener("datadeselected", updateMultiHighlight);
    topicsList.addEventListener("dataselectioncleared", updateMultiHighlight);
    const refreshTopicsList = () => {
        window.setTimeout(() => {
            topicsList.data = [...topicsList.data];
            topicsList.requestUpdate();
        }, 150);
    };
    topics.list.onItemSet.add(refreshTopicsList);
    topics.list.onItemUpdated.add(refreshTopicsList);

    const [topicPanel, updateTopicPanel] = createTopicPanel(components, topics, world);
    const selectTopic = async (topic) => {
        updateTopicPanel({ topic });
        const viewpointGuid = topic.viewpoints.values().next().value;
        const viewpoint = viewpointGuid ? viewpoints.list.get(viewpointGuid) : null;
        if (!viewpoint) return;

        viewpoint.world = world;
        await viewpoint.go({ transition: true, applyVisibility: true });
    };
    topicsList.addEventListener("rowcreated", (event) => {
        const { row } = event.detail;
        row.style.cursor = "pointer";
        row.addEventListener("click", () => {
            const topic = row?.data?.Guid ? topics.list.get(row.data.Guid) : null;
            if (topic) selectTopic(topic);
        });
    });

    const [topicForm, updateTopicForm] = CUI.forms.topic({
        components,
        styles: { users: USERS },
    });
    const assigneeDropdown = topicForm.querySelector("bim-dropdown[name='assignedTo']");
    if (assigneeDropdown) assigneeDropdown.searchBox = true;

    const topicsModal = BUI.Component.create(() => BUI.html`
        <dialog class="bimguard-topic-dialog">
            <bim-panel>
                ${topicForm}
            </bim-panel>
        </dialog>
    `);
    document.body.append(topicsModal);
    updateTopicForm({
        onCancel: () => topicsModal.close(),
        onSubmit: () => topicsModal.close(),
    });

    const topicsPanel = BUI.Component.create(() => {
        const searchTopics = (event) => {
            topicsList.queryString = event.target.value;
        };
        const exportTopics = async () => {
            const selected = [...topicsList.selection]
                .map(({ Guid }) => (Guid ? topics.list.get(Guid) : null))
                .filter(Boolean);
            const topicsToExport = selected.length ? selected : [...topics.list.values()];
            if (!topicsToExport.length) return;

            const bcfData = await topics.export(topicsToExport);
            const href = URL.createObjectURL(new File([bcfData], "bimguard-topics.bcf"));
            const link = document.createElement("a");
            link.href = href;
            link.download = "bimguard-topics.bcf";
            link.click();
            URL.revokeObjectURL(href);
        };

        return BUI.html`
            <bim-panel>
                <bim-panel-section label="BCF topics" icon="material-symbols:task-outline" fixed>
                    <div class="bimguard-topics-toolbar">
                        <bim-text-input
                            @input=${searchTopics}
                            placeholder="Search topics..."
                            debounce="100">
                        </bim-text-input>
                        <div class="bimguard-topics-actions">
                            <bim-button
                                @click=${() => topicsModal.showModal()}
                                label="Create topic"
                                icon="material-symbols:add-task">
                            </bim-button>
                            <bim-button
                                @click=${exportTopics}
                                label="Download BCF"
                                icon="material-symbols:download">
                            </bim-button>
                        </div>
                    </div>
                    ${topicsList}
                </bim-panel-section>
            </bim-panel>
        `;
    });

    const app = document.createElement("bim-grid");
    app.className = "bimguard-topics-grid";
    app.layouts = {
        desktop: {
            template: `
                "details viewport" minmax(28rem, 1fr)
                "details topics" 22rem
                / minmax(18rem, 22rem) minmax(0, 1fr)
            `,
            elements: { details: topicPanel, viewport, topics: topicsPanel },
        },
        compact: {
            template: `
                "viewport" minmax(24rem, 55vh)
                "topics" 24rem
                "details" minmax(20rem, auto)
                / minmax(0, 1fr)
            `,
            elements: { details: topicPanel, viewport, topics: topicsPanel },
        },
    };

    const setLayout = () => {
        app.layout = app.clientWidth < 760 ? "compact" : "desktop";
    };
    const layoutObserver = new ResizeObserver(setLayout);
    layoutObserver.observe(app);

    return {
        app,
        topics,
        topicsModal,
        refreshTopicsList,
        selectTopic,
        dispose: () => layoutObserver.disconnect(),
    };
}

// ─── Viewer Toolbar ──────────────────────────────────────────────────────────
// Creates a floating BUI toolbar overlaid on top of the bim-viewport element.
// Controls exposed:
//   • Camera projection: Perspective / Orthographic
//   • Navigation mode: Orbit / First Person / Plan
//   • Fit model to camera
//   • Toggle section clipping planes (double-click viewport to add, toolbar to delete all / toggle)
//   • Toggle grid
//   • Fullscreen
function createViewerToolbar(components, world, viewport, grids, isolate) {
    // ── Clipping planes ────────────────────────────────────────────────────
    const clipper = components.get(OBC.Clipper);
    clipper.enabled = false;   // start with clipping disabled

    // ── Mutable toolbar UI state ───────────────────────────────────────────
    let clippingActive = false;
    let clippingEnabled = true; // visibility toggle when planes exist

    // Double-click on the viewport to create a clipping plane at the clicked surface.
    viewport.addEventListener("dblclick", () => {
        if (!clippingActive) return;
        clipper.create(world);
    });

    // ── Grid visibility ────────────────────────────────────────────────────
    let gridVisible = true;

    // ── Isolate selected element ───────────────────────────────────────────
    // isolate mode follows whatever is currently highlighted (a "View in 3D"
    // element, or a selected topic) so switching topics while isolated keeps
    // showing only the new selection, rather than snapping back to the full model.
    isolate.onSelectionChange(() => updateToolbar({}));

    // ── Toolbar: stateful BUI component so updateToolbar() triggers re-renders ─
    const [toolbar, updateToolbar] = BUI.Component.create(
        (state) => {
            const { clippingActive, clippingEnabled, gridVisible } = state;
            const isolateActive = isolate.isActive();
            const canIsolate = isolate.hasSelection();

            const toggleIsolate = () => {
                isolate.toggle();
                updateToolbar({});
            };

            // Camera projection
            const toggleProjection = () => {
                const cam = world.camera;
                const current = cam.projection.current;
                cam.projection.set(current === "Perspective" ? "Orthographic" : "Perspective");
                updateToolbar({});
            };

            // Navigation mode
            const setNavMode = (mode) => {
                world.camera.set(mode);
                updateToolbar({});
            };

            // Fit all models in view
            const fitModel = async () => {
                const meshes = [];
                for (const [, model] of components.get(OBC.FragmentsManager).list) {
                    if (model.object) meshes.push(model.object);
                }
                if (meshes.length > 0) {
                    await world.camera.fit(meshes, 0.5);
                }
            };

            // Clipping plane controls
            const toggleClipping = () => {
                const next = !clippingActive;
                clipper.enabled = next;
                updateToolbar({ clippingActive: next });
            };

            const toggleClippingVisibility = () => {
                const next = !clippingEnabled;
                clipper.visible = next;
                updateToolbar({ clippingEnabled: next });
            };

            const deleteAllClippingPlanes = () => {
                clipper.deleteAll();
                clipper.enabled = false;
                updateToolbar({ clippingActive: false });
            };

            // Grid toggle
            const toggleGrid = () => {
                const next = !gridVisible;
                for (const [, grid] of grids.list) {
                    grid.three.visible = next;
                }
                updateToolbar({ gridVisible: next });
            };

            // Fullscreen
            const toggleFullscreen = () => {
                const container = viewport.closest(".bimguard-viewer-root") || viewport.parentElement;
                if (!document.fullscreenElement) {
                    (container || viewport).requestFullscreen().catch(() => {});
                } else {
                    document.exitFullscreen();
                }
            };

            const projCurrent = world.camera.projection?.current ?? "Perspective";
            const navCurrent = world.camera.mode?.id ?? "Orbit";

            return BUI.html`
                <div class="bimguard-toolbar">
                    <!-- Camera Projection -->
                    <div class="bimguard-toolbar-group" title="Camera projection">
                        <button
                            class="bimguard-tb-btn ${projCurrent === 'Perspective' ? 'active' : ''}"
                            @click=${() => { world.camera.projection.set("Perspective"); updateToolbar({}); }}
                            title="Perspective camera">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M4 20V4l16 8-16 8zm2-2.7L16.85 12 6 6.7V9.4l6 2.6-6 2.6v2.7z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">Persp</span>
                        </button>
                        <button
                            class="bimguard-tb-btn ${projCurrent === 'Orthographic' ? 'active' : ''}"
                            @click=${() => { world.camera.projection.set("Orthographic"); updateToolbar({}); }}
                            title="Orthographic camera">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M20 3H4v18h16V3zm-2 16H6V5h12v14z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">Ortho</span>
                        </button>
                    </div>

                    <div class="bimguard-toolbar-divider"></div>

                    <!-- Navigation Modes -->
                    <div class="bimguard-toolbar-group" title="Navigation mode">
                        <button
                            class="bimguard-tb-btn ${navCurrent === 'Orbit' ? 'active' : ''}"
                            @click=${() => { world.camera.set("Orbit"); updateToolbar({}); }}
                            title="Orbit navigation">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">Orbit</span>
                        </button>
                        <button
                            class="bimguard-tb-btn ${navCurrent === 'FirstPerson' ? 'active' : ''}"
                            @click=${() => { world.camera.set("FirstPerson"); updateToolbar({}); }}
                            title="First person navigation (WASD)">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">Walk</span>
                        </button>
                        <button
                            class="bimguard-tb-btn ${navCurrent === 'Plan' ? 'active' : ''}"
                            @click=${() => { world.camera.set("Plan"); updateToolbar({}); }}
                            title="Plan (2D top-down) navigation">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14z"/><path fill="currentColor" d="M7 7h10v2H7zm0 4h10v2H7zm0 4h7v2H7z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">Plan</span>
                        </button>
                    </div>

                    <div class="bimguard-toolbar-divider"></div>

                    <!-- Fit to view -->
                    <div class="bimguard-toolbar-group">
                        <button class="bimguard-tb-btn" @click=${fitModel} title="Fit model to view">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M15 3l2.3 2.3-2.89 2.87 1.42 1.42L18.7 6.7 21 9V3h-6zM3 9l2.3-2.3 2.87 2.89 1.42-1.42L6.7 5.3 9 3H3v6zm6 12l-2.3-2.3 2.89-2.87-1.42-1.42L5.3 17.3 3 15v6h6zm12-6l-2.3 2.3-2.87-2.89-1.42 1.42 2.89 2.87L15 21h6v-6z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">Fit</span>
                        </button>
                    </div>

                    <div class="bimguard-toolbar-divider"></div>

                    <!-- Clipping planes -->
                    <div class="bimguard-toolbar-group" title="Section clipping planes">
                        <button
                            class="bimguard-tb-btn ${clippingActive ? 'active warning' : ''}"
                            @click=${toggleClipping}
                            title="${clippingActive ? 'Disable clipping mode (double-click adds planes)' : 'Enable clipping mode (double-click to add planes)'}">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M11 15H6l7-14v8h5l-7 14v-8z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">Section</span>
                        </button>
                        <button
                            class="bimguard-tb-btn"
                            @click=${toggleClippingVisibility}
                            title="${clippingEnabled ? 'Hide clipping planes' : 'Show clipping planes'}">
                            <span class="bimguard-tb-icon">
                                ${clippingEnabled
                                    ? BUI.html`<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>`
                                    : BUI.html`<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/></svg>`
                                }
                            </span>
                            <span class="bimguard-tb-label">${clippingEnabled ? 'Visible' : 'Hidden'}</span>
                        </button>
                        <button
                            class="bimguard-tb-btn danger"
                            @click=${deleteAllClippingPlanes}
                            title="Delete all clipping planes">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">Clear</span>
                        </button>
                    </div>

                    <div class="bimguard-toolbar-divider"></div>

                    <!-- Grid toggle -->
                    <div class="bimguard-toolbar-group">
                        <button
                            class="bimguard-tb-btn ${gridVisible ? 'active' : ''}"
                            @click=${toggleGrid}
                            title="${gridVisible ? 'Hide grid' : 'Show grid'}">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M20 2H4c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-9 17H4v-7h7v7zm0-9H4V4h7v6zm9 9h-7v-7h7v7zm0-9h-7V4h7v6z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">Grid</span>
                        </button>
                    </div>

                    <div class="bimguard-toolbar-divider"></div>

                    <!-- Isolate selected element -->
                    <div class="bimguard-toolbar-group">
                        <button
                            class="bimguard-tb-btn ${isolateActive ? 'active' : ''}"
                            ?disabled=${!canIsolate}
                            @click=${toggleIsolate}
                            title="${canIsolate
                                ? (isolateActive ? 'Show all elements' : 'Show only the selected element')
                                : 'Select an element to isolate it'}">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">${isolateActive ? 'Isolated' : 'Isolate'}</span>
                        </button>
                    </div>

                    <div class="bimguard-toolbar-divider"></div>

                    <!-- Fullscreen -->
                    <div class="bimguard-toolbar-group">
                        <button class="bimguard-tb-btn" @click=${toggleFullscreen} title="Toggle fullscreen">
                            <span class="bimguard-tb-icon">
                                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>
                            </span>
                            <span class="bimguard-tb-label">Full</span>
                        </button>
                    </div>

                    ${clippingActive ? BUI.html`
                        <div class="bimguard-toolbar-hint">
                            ✂️ Double-click model surface to add a section plane
                        </div>
                    ` : ''}
                </div>
            `;
        },
        { clippingActive: false, clippingEnabled: true, gridVisible: true }
    );

    // Wrap the viewport with a relative-positioned container to overlay the toolbar
    const viewportWrapper = document.createElement("div");
    viewportWrapper.className = "bimguard-viewport-wrapper";
    viewportWrapper.style.cssText = "position:relative;display:flex;flex-direction:column;width:100%;height:100%;min-height:0;";

    // Inject toolbar styles once
    if (!document.getElementById("bimguard-toolbar-styles")) {
        const style = document.createElement("style");
        style.id = "bimguard-toolbar-styles";
        style.textContent = `
            .bimguard-viewport-wrapper {
                position: relative;
                display: flex;
                flex-direction: column;
                width: 100%;
                height: 100%;
                min-height: 0;
            }
            .bimguard-toolbar {
                position: absolute;
                top: 10px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 100;
                display: flex;
                align-items: center;
                gap: 4px;
                background: rgba(10, 12, 22, 0.88);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(99, 102, 241, 0.25);
                border-radius: 12px;
                padding: 6px 10px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04) inset;
                flex-wrap: wrap;
                max-width: calc(100% - 24px);
            }
            .bimguard-toolbar-group {
                display: flex;
                align-items: center;
                gap: 2px;
            }
            .bimguard-toolbar-divider {
                width: 1px;
                height: 24px;
                background: rgba(99, 102, 241, 0.2);
                margin: 0 4px;
                flex-shrink: 0;
            }
            .bimguard-tb-btn {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 2px;
                padding: 5px 7px;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                color: rgba(148, 163, 184, 0.9);
                cursor: pointer;
                font-size: 9px;
                font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
                font-weight: 500;
                letter-spacing: 0.03em;
                transition: all 0.15s ease;
                min-width: 38px;
                white-space: nowrap;
                user-select: none;
            }
            .bimguard-tb-btn:hover {
                background: rgba(99, 102, 241, 0.15);
                border-color: rgba(99, 102, 241, 0.3);
                color: #e2e8f0;
            }
            .bimguard-tb-btn.active {
                background: rgba(99, 102, 241, 0.25);
                border-color: rgba(99, 102, 241, 0.6);
                color: #a5b4fc;
            }
            .bimguard-tb-btn.active.warning {
                background: rgba(245, 158, 11, 0.2);
                border-color: rgba(245, 158, 11, 0.5);
                color: #fcd34d;
            }
            .bimguard-tb-btn.danger:hover {
                background: rgba(239, 68, 68, 0.15);
                border-color: rgba(239, 68, 68, 0.4);
                color: #fca5a5;
            }
            .bimguard-tb-btn:disabled {
                opacity: 0.35;
                cursor: not-allowed;
                pointer-events: none;
            }
            .bimguard-tb-icon {
                display: flex;
                align-items: center;
                justify-content: center;
                line-height: 1;
            }
            .bimguard-tb-label {
                font-size: 9px;
                line-height: 1;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            .bimguard-toolbar-hint {
                font-size: 10px;
                color: #fcd34d;
                background: rgba(245, 158, 11, 0.1);
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 6px;
                padding: 3px 8px;
                margin-left: 4px;
                white-space: nowrap;
                font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
                font-weight: 500;
            }
        `;
        document.head.appendChild(style);
    }

    viewportWrapper.appendChild(toolbar);
    viewportWrapper.appendChild(viewport);

    return viewportWrapper;
}

export async function initViewer(containerOrId) {
    const container = typeof containerOrId === "string"
        ? document.getElementById(containerOrId)
        : containerOrId;
    if (!container) {
        console.error("Container not found:", containerOrId);
        return null;
    }

    BUI.Manager.init();

    const viewport = document.createElement("bim-viewport");
    viewport.className = "bimguard-viewport";
    const components = new OBC.Components();

    const worlds = components.get(OBC.Worlds);
    const world = worlds.create();

    world.scene = new OBC.SimpleScene(components);
    world.renderer = new OBC.SimpleRenderer(components, viewport);
    world.camera = new OBC.OrthoPerspectiveCamera(components);

    world.scene.setup();
    world.scene.three.background = null;
    world.camera.controls.setLookAt(74, 16, 0.2, 30, -4, 27);
    components.init();

    const grids = components.get(OBC.Grids);
    grids.create(world);

    const { highlightTopics, isolate } = installErrorHighlighting(components, world);

    const fragments = components.get(OBC.FragmentsManager);
    const workerUrl = await OBC.FragmentsManager.getWorker();
    fragments.init(workerUrl);

    world.camera.controls.addEventListener("update", () => fragments.core.update());
    fragments.list.onItemSet.add(async ({ value: model }) => {
        model.useCamera(world.camera.three);
        world.scene.three.add(model.object);
        await fragments.core.update(true);
    });

    const fragmentIfcLoader = components.get(OBC.IfcLoader);
    await fragmentIfcLoader.setup({
        autoSetWasm: false,
        wasm: {
            path: "https://unpkg.com/web-ifc@0.0.77/",
            absolute: true,
        },
    });

    viewport.addEventListener("resize", () => {
        if (world.renderer) world.renderer.resize();
        if (world.camera) world.camera.updateAspect();
    });

    const workspace = createTopicsWorkspace(components, world, viewport, highlightTopics);

    // Wrap the viewport (which is already embedded inside workspace.app) with a
    // toolbar overlay. We intercept by replacing the viewport inside the grid layout.
    const viewportWrapper = createViewerToolbar(components, world, viewport, grids, isolate);

    // Patch the bim-grid layout to use the wrapper instead of the raw viewport
    // by updating its element references before the first layout is set.
    const origLayouts = workspace.app.layouts;
    workspace.app.layouts = {
        desktop: {
            ...origLayouts.desktop,
            elements: { ...origLayouts.desktop.elements, viewport: viewportWrapper },
        },
        compact: {
            ...origLayouts.compact,
            elements: { ...origLayouts.compact.elements, viewport: viewportWrapper },
        },
    };

    container.replaceChildren(workspace.app);

    async function clearModels() {
        try {
            isolate.reset();
            for (const [, model] of fragments.list) {
                if (model.object) world.scene.three.remove(model.object);
                if (model.dispose) model.dispose();
            }
            fragments.list.clear();
        } catch (e) {
            console.warn("Could not clear previous models:", e);
        }
    }

    // The host page's project/file selection can update twice in one user
    // action (e.g. a reactive prop settling in two steps), which fires two
    // concurrent loadIfc calls for the same model. Racing clearModels() and
    // fragmentIfcLoader.load() against each other silently ends with nothing
    // in the scene — no error, since both individual loads succeed, they just
    // stomp on each other. Serializing here means the second call always
    // starts clean after the first one has actually finished attaching its
    // model, regardless of what triggered the double call upstream.
    let activeLoad = Promise.resolve();
    async function loadIfc(urlOrFile, headers) {
        const previous = activeLoad;
        let release;
        activeLoad = new Promise((resolve) => { release = resolve; });
        try {
            await previous;
            await clearModels();
            const file = typeof urlOrFile === "string"
                ? await fetch(urlOrFile, { headers }).then(async (response) => {
                    if (!response.ok) throw new Error(`IFC request failed (${response.status})`);
                    return new File([await response.blob()], "project.ifc");
                })
                : urlOrFile;
            const data = await file.arrayBuffer();
            const buffer = new Uint8Array(data);
            await fragmentIfcLoader.load(buffer, true, file.name.replace(/\.ifc$/i, ""));
        } catch (error) {
            console.error("Error loading IFC file", error);
            throw error;
        } finally {
            release();
        }
    }

    // Topics don't carry a dedicated "linked element" field of their own —
    // that lives inside each viewpoint's component selection instead — so
    // the server embeds the element's IFC GUID as an "ElementGUID:" line in
    // the topic's Description (a basic, spec-required BCF field every
    // compliant reader must preserve verbatim). Matching that substring is
    // how a "View in 3D" link for one specific element finds its topic here.
    function findTopicByElementGuid(elementGuid) {
        if (!elementGuid) return null;
        const needle = `ElementGUID: ${elementGuid}`;
        for (const topic of workspace.topics.list.values()) {
            if ((topic.description || "").includes(needle)) return topic;
        }
        return null;
    }

    async function loadBcf(urlOrFile, elementGuid, headers) {
        try {
            const file = typeof urlOrFile === "string"
                ? await fetch(urlOrFile, { headers }).then(async (response) => {
                    if (!response.ok) throw new Error(`BCF request failed (${response.status})`);
                    return new File([await response.blob()], "report.bcf");
                })
                : urlOrFile;
            const imported = await workspace.topics.load(new Uint8Array(await file.arrayBuffer()));
            const importedViewpoints = Array.from(imported.viewpoints);
            for (const viewpoint of importedViewpoints) viewpoint.world = world;
            workspace.refreshTopicsList();

            const targetTopic = findTopicByElementGuid(elementGuid)
                || workspace.topics.list.values().next().value;
            if (targetTopic) await workspace.selectTopic(targetTopic);
            return imported;
        } catch (error) {
            console.error("Error loading BCF file", error);
            throw error;
        }
    }

    function setupFileLoader(inputId) {
        const input = document.getElementById(inputId);
        if (input) {
            input.addEventListener('change', async (event) => {
                const file = event.target.files[0];
                if (file) await loadIfc(file);
            });
        }
    }

    // Switching which of a project's models is on screen is a change of subject,
    // not of viewpoint: the user is looking at one corner of one building and
    // wants the structural model of that same corner. loadIfc refits the camera
    // to the new model's bounds, so the caller reads the state first and puts it
    // back afterwards.
    function getCameraState() {
        try {
            const position = new THREE.Vector3();
            const target = new THREE.Vector3();
            world.camera.controls.getPosition(position);
            world.camera.controls.getTarget(target);
            return { position: position.toArray(), target: target.toArray() };
        } catch (e) {
            console.warn("Could not read camera state:", e);
            return null;
        }
    }

    async function setCameraState(state) {
        if (!state || !state.position || !state.target) return;
        try {
            const [px, py, pz] = state.position;
            const [tx, ty, tz] = state.target;
            await world.camera.controls.setLookAt(px, py, pz, tx, ty, tz, false);
        } catch (e) {
            console.warn("Could not restore camera state:", e);
        }
    }

    return {
        components,
        world,
        topics: workspace.topics,
        loadBcf,
        loadIfc,
        getCameraState,
        setCameraState,
        setupFileLoader,
        selectTopic: workspace.selectTopic,
        findTopicByElementGuid,
        dispose: () => {
            try {
                workspace.dispose();
                components.dispose();
            } catch (e) {
                console.warn("Error disposing viewer:", e);
            }
        },
    };
}
