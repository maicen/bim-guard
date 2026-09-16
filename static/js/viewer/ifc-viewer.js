import * as BUI from "https://esm.sh/@thatopen/ui@3.4.10";
import * as OBC from "https://esm.sh/@thatopen/components@3.4.8?external=web-ifc&deps=three@0.182.0,@thatopen/fragments@3.4.7";
import * as OBF from "https://esm.sh/@thatopen/components-front@3.4.4?external=web-ifc&deps=@thatopen/components@3.4.8,@thatopen/fragments@3.4.7,three@0.182.0";
import * as CUI from "https://esm.sh/@thatopen/ui-obc@3.4.2?external=web-ifc&deps=@thatopen/ui@3.4.10,@thatopen/components@3.4.8,three@0.182.0,@thatopen/fragments@3.4.7";
import * as THREE from "https://esm.sh/three@0.182.0";
// The very JSZip that @thatopen/components@3.4.8 bundles for its own
// BCFTopics.load (it vendors JSZip 3.10.1 rather than re-exporting it, so the
// same version has to be pulled alongside rather than reached through OBC).
import JSZip from "https://esm.sh/jszip@3.10.1";
import { filterBcfArchive, priorityRank } from "./bcf-filter.js?v=viewer-isolate-5";
import { colorGroupsFromComponentColors, styleNameForColor } from "./bcf-colors.js?v=viewer-band-colors-1";

const ERROR_HIGHLIGHT_STYLE = "bimguard-error";

// Tiny pub/sub used by every bridge namespace below (camera, grid, clipping,
// isolate, views, layers, drawings, topics) so the Svelte chrome that drives
// this engine can mirror its state reactively instead of polling. Every
// `onChange`/`onSelectionChange` returns an unsubscribe function.
function createEmitter() {
    const listeners = new Set();
    return {
        on: (cb) => {
            listeners.add(cb);
            return () => listeners.delete(cb);
        },
        emit: (payload) => {
            for (const listener of listeners) listener(payload);
        },
    };
}

function getCssHex(varName, fallbackHex) {
    if (typeof window === "undefined" || typeof document === "undefined") return fallbackHex;
    try {
        const val = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
        if (!val) return fallbackHex;
        const rgbMatch = val.match(/rgba?\((\d+)[,\s]+(\d+)[,\s]+(\d+)/);
        if (rgbMatch) {
            return (parseInt(rgbMatch[1], 10) << 16) | (parseInt(rgbMatch[2], 10) << 8) | parseInt(rgbMatch[3], 10);
        }
        if (val.startsWith("#")) {
            return parseInt(val.slice(1), 16);
        }
    } catch {
        // Fallback
    }
    return fallbackHex;
}

function getThemeConfig() {
    const isLight = typeof document !== "undefined" && document.documentElement.classList.contains("light");
    return {
        isLight,
        // Match --color-surface-canvas
        canvasHex: getCssHex("--color-surface-canvas", isLight ? 0xf8fafc : 0x020617),
        // Grid lines matching --color-border-default / --color-border-subtle
        gridColor: getCssHex("--color-border-default", isLight ? 0xcbd5e1 : 0x334155),
        gridSecondaryColor: getCssHex("--color-border-subtle", isLight ? 0xe2e8f0 : 0x1e293b),
        // Error highlighting matching --color-critical
        errorHex: getCssHex("--color-critical", isLight ? 0xbe123c : 0xf43f5e),
    };
}
// Camera framing. The viewport used to open at a hardcoded setLookAt() pose
// tuned for one sample model, so anything with different bounds — or with IFC
// coordinates surveyed far from the origin, which is the norm — rendered as a
// speck or off screen entirely. The pose below is derived from the loaded
// geometry instead.
const FIT_VIEW_DIRECTION = new THREE.Vector3(1, 0.6, 1).normalize();
const FIT_PADDING = 1.2; // slight zoom-out so the model clears the viewport edges
const MIN_FIT_RADIUS = 0.05; // only catches a degenerate (zero-size) box, which would otherwise
                            // put the camera on top of the model, inside its own near plane

/** Stage log for the findings deep link — demo evidence, deliberately kept. */
const LOG = "[bimguard-3d]";
const since = (t0) => Math.round(performance.now() - t0);

/** Mounts of this module in one page session; see initViewer. */
let mountCount = 0;

// ─── Viewpoint.go() patch — installed ONCE per module, not per mount ────────
//
// The BCF viewpoints the corrosion engine generates carry the failing
// element's GUID in their selection (see bcf_generator._viewpoint_xml), but
// Viewpoint.go() only moves the camera and applies visibility — it never
// colors the linked component. Patching go() means every way a viewpoint can
// be shown (the topic list's row click below, and the native eye-icon button
// ui-obc renders per viewpoint) highlights the offending element in red
// instead of just zooming to it.
//
// This used to be patched inside installErrorHighlighting, which runs per
// mount — so the second mount captured the first mount's wrapper as its
// "original" and wrapped it again. Navigating to the viewer twice in one SPA
// session produced nested highlightingGo frames (two on the second mount,
// three on the third), and the innermost one still pointed at the first
// mount's highlighter, whose Components had been disposed. That surfaced as
// "FragmentsManager not initialized. Call init() first." and no red element on
// every mount after the first.
//
// So: patch once, and route through a mutable reference that each mount
// replaces. Only the live mount's highlighter is ever touched.
let activeHighlighting = null;
let goPatched = false;

function patchViewpointGo() {
    if (goPatched) return;
    goPatched = true;
    const originalGo = OBC.Viewpoint.prototype.go;
    OBC.Viewpoint.prototype.go = async function highlightingGo(config) {
        await originalGo.call(this, config);
        // Read at call time, never captured: a viewpoint created by one mount
        // can outlive it, and must colour through whoever is live now.
        const active = activeHighlighting;
        if (!active) return;
        await active.applyViewpointSelection(this);
    };
}

function installErrorHighlighting(components, world) {
    components.get(OBC.Raycasters).get(world);
    const highlighter = components.get(OBF.Highlighter);
    highlighter.setup({ world, selectEnabled: false, autoHighlightOnClick: false });
    const initialTheme = getThemeConfig();
    highlighter.styles.set(ERROR_HIGHLIGHT_STYLE, {
        color: new THREE.Color(initialTheme.errorHex),
        opacity: 1,
        transparent: false,
        renderedFaces: 0,
    });

    const hider = components.get(OBC.Hider);

    // Tracks the ModelIdMap behind whatever is currently highlighted (a single
    // topic's viewpoint selection, or the joined selection of a multi-select),
    // so the "Isolate" ribbon button knows what to show/hide without having
    // to recompute it, and so isolate mode can follow the selection as it changes.
    let currentSelectionMap = null;
    let isolateActive = false;
    const selectionListeners = new Set();

    // Set by the Layers module once it exists (see initViewer) so that
    // isolating a BCF topic's selection composes with whatever categories the
    // user has hidden, instead of one silently overriding the other.
    let getHiddenMap = () => null;

    async function applyIsolation(map) {
        if (map) {
            let effective = map;
            const hidden = getHiddenMap();
            if (hidden) {
                effective = OBC.ModelIdMapUtils.clone(map);
                OBC.ModelIdMapUtils.remove(effective, hidden);
            }
            await hider.isolate(effective);
        } else {
            await hider.set(true);
            const hidden = getHiddenMap();
            if (hidden) await hider.set(false, hidden);
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
        applyIsolation(null);
    }

    /**
     * Highlighter style names created from BCF colours so far, so each one is
     * cleared before the next viewpoint paints and registered only once.
     */
    const bcfColorStyles = new Set();

    /** Drop every BCF-colour highlight, leaving the fixed error style alone. */
    async function clearBcfColorStyles() {
        for (const name of bcfColorStyles) await highlighter.clear(name);
    }

    /**
     * Paint a viewpoint's Coloring block, one highlighter style per colour.
     *
     * The colours are the exporter's, not the viewer's: bcf_generator gives the
     * subject its risk band's colour (Critical FFC00000, High FFC05000, Medium
     * FFFF8C00, Low FF107C10) and the implicated partners a contrasting
     * FF0070C0. Returns false when the archive carries no usable colours, so
     * the caller can fall back to the single error style rather than leaving
     * the element unpainted.
     */
    async function applyViewpointColors(viewpoint) {
        const groups = colorGroupsFromComponentColors(viewpoint?.componentColors);
        if (groups.length === 0) return false;
        const fragments = components.get(OBC.FragmentsManager);
        let painted = false;
        for (const { hex, guids } of groups) {
            let map;
            try {
                map = await fragments.guidsToModelIdMap(guids);
            } catch (err) {
                console.warn(`${LOG} colour lookup failed for ${hex}:`, err);
                continue;
            }
            if (!map || OBC.ModelIdMapUtils.isEmpty(map)) continue;
            const styleName = styleNameForColor(hex);
            if (!bcfColorStyles.has(styleName)) {
                highlighter.styles.set(styleName, {
                    color: new THREE.Color(`#${hex}`),
                    opacity: 1,
                    transparent: false,
                    renderedFaces: 0,
                });
                bcfColorStyles.add(styleName);
            }
            await highlighter.highlightByID(styleName, map, false, false);
            painted = true;
        }
        return painted;
    }

    // What the patched go() calls back into, for this mount only.
    async function applyViewpointSelection(viewpoint) {
        await highlighter.clear(ERROR_HIGHLIGHT_STYLE);
        await clearBcfColorStyles();
        const selectionMap = await viewpoint.getSelectionMap();
        const map = OBC.ModelIdMapUtils.isEmpty(selectionMap) ? null : selectionMap;
        // Isolate and framing follow the whole selection, however it is painted.
        setSelectionMap(map);
        // Band colours first; the fixed red is the fallback for an archive with
        // no Coloring block (or one whose guids match nothing loaded).
        const painted = await applyViewpointColors(viewpoint);
        if (map && !painted) {
            await highlighter.highlightByID(ERROR_HIGHLIGHT_STYLE, selectionMap, false, false);
        }
    }

    patchViewpointGo();
    activeHighlighting = { applyViewpointSelection };

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
        // A multi-select spans topics of different bands, so one colour per
        // element would be arbitrary: the joined selection takes the single
        // error style, and any band colours from a previous single-topic
        // viewpoint are cleared rather than left painted underneath.
        await clearBcfColorStyles();
        const joined = maps.length > 0 ? OBC.ModelIdMapUtils.join(maps) : null;
        setSelectionMap(joined);
        if (joined) {
            await highlighter.highlightByID(ERROR_HIGHLIGHT_STYLE, joined, false, false);
        }
    }

    // Generic version of highlightTopics's clear/highlight/track sequence, for
    // callers that already have a ModelIdMap of their own (e.g. a direct
    // GlobalId lookup) rather than a set of BCF topics.
    async function highlightMap(map) {
        await highlighter.clear(ERROR_HIGHLIGHT_STYLE);
        // No viewpoint here, so no band colours to read: clear any left over
        // from one, or they stay painted under this highlight.
        await clearBcfColorStyles();
        setSelectionMap(map);
        if (map) await highlighter.highlightByID(ERROR_HIGHLIGHT_STYLE, map, false, false);
    }

    return {
        highlightTopics,
        highlightMap,
        hider,
        highlighter,
        isolate: {
            toggle: toggleIsolate,
            reset: resetIsolate,
            isActive: () => isolateActive,
            hasSelection: () => currentSelectionMap !== null,
            onSelectionChange: (cb) => {
                selectionListeners.add(cb);
                return () => selectionListeners.delete(cb);
            },
            setHiddenMapProvider: (fn) => {
                getHiddenMap = fn;
            },
            // The map behind the current highlight, for callers that need to
            // frame it rather than just show/hide it (see fitToSelection).
            getSelectionMap: () => currentSelectionMap,
        },
        // Detach this mount from the shared go() patch, but only if a later
        // mount has not already taken over — dispose can arrive after the next
        // mount has installed itself.
        disposeHighlighting: () => {
            if (activeHighlighting && activeHighlighting.applyViewpointSelection === applyViewpointSelection) {
                activeHighlighting = null;
            }
            selectionListeners.clear();
            currentSelectionMap = null;
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
    // Never throws.
    //
    // The sections rendered here resolve ids through the live managers —
    // topicRelations maps the topic's RelatedTopic guids through topics.list
    // and reads .guid off each result — so anything the archive references but
    // does not contain surfaces as a TypeError inside lit's synchronous render.
    // That used to propagate out through selectTopic and abort the whole
    // selection, costing the red element over a panel that nobody had looked at
    // yet. The panel is the least important thing on screen here; it must never
    // be able to take the highlight down with it.
    const updateTopicPanel = ({ topic } = {}) => {
        if (topic) selectedTopic = topic;
        try {
            topicPanel.replaceChildren(renderTopicPanel(selectedTopic));
        } catch (error) {
            console.warn(`${LOG} panel update failed:`, error);
        }
    };
    updateTopicPanel();

    topics.list.onItemUpdated.add(() => updateTopicPanel());
    return [topicPanel, updateTopicPanel];
}

// Builds the BCF topics list + detail-panel DOM (raw CUI/BUI web components)
// and exposes an imperative + subscribable bridge over it. No layout/grid
// responsibility here any more — the Svelte side decides how/where these
// two DOM fragments (topicsPanel, topicPanel) are mounted.
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
    // Debounced to a single pending timer, and cancellable.
    //
    // This fires from topics.list.onItemSet, i.e. once per imported topic, so
    // the unfiltered 1,384-topic archive used to queue 1,384 separate timers,
    // each rebuilding the whole table. They also outlived dispose, waking up
    // to touch a detached table after the viewer was gone.
    let refreshTimer = null;
    const refreshTopicsList = () => {
        if (refreshTimer !== null) window.clearTimeout(refreshTimer);
        refreshTimer = window.setTimeout(() => {
            refreshTimer = null;
            topicsList.data = [...topicsList.data];
            topicsList.requestUpdate();
        }, 150);
    };
    topics.list.onItemSet.add(refreshTopicsList);
    topics.list.onItemUpdated.add(refreshTopicsList);

    const [topicPanel, updateTopicPanel] = createTopicPanel(components, topics, world);

    let selectedTopic = null;
    const selectionListeners = new Set();
    // Geometry first, panel second — deliberately, and in that order.
    //
    // viewpoint.go() is what colours the element, publishes the selection map
    // the ISOLATE button reads, and lets the caller frame it. The panel is
    // commentary. Rendering the panel first meant a single unresolvable id in
    // it aborted the selection before any of that ran, which is exactly what
    // happened to the topics whose RelatedTopic references the archive filter
    // had pruned away. updateTopicPanel swallows its own errors too; the
    // ordering is the belt to that braces.
    const selectTopic = async (topic) => {
        selectedTopic = topic;
        for (const listener of selectionListeners) listener(topic);
        const viewpointGuid = topic.viewpoints.values().next().value;
        const viewpoint = viewpointGuid ? viewpoints.list.get(viewpointGuid) : null;
        if (!viewpoint) {
            updateTopicPanel({ topic });
            return;
        }

        viewpoint.world = world;
        await viewpoint.go({ transition: true, applyVisibility: true });
        updateTopicPanel({ topic });
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

    async function download() {
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
    }

    const topicsPanel = BUI.Component.create(() => {
        const searchTopics = (event) => {
            topicsList.queryString = event.target.value;
        };
        return BUI.html`
            <bim-panel>
                <bim-panel-section label="BCF topics" icon="material-symbols:task-outline" fixed>
                    <bim-text-input
                        @input=${searchTopics}
                        placeholder="Search topics..."
                        debounce="100">
                    </bim-text-input>
                    ${topicsList}
                </bim-panel-section>
            </bim-panel>
        `;
    });

    return {
        topics,
        topicsPanel,
        topicPanel,
        topicsModal,
        refreshTopicsList,
        selectTopic,
        getSelectedTopic: () => selectedTopic,
        onSelectionChange: (cb) => {
            selectionListeners.add(cb);
            return () => selectionListeners.delete(cb);
        },
        openCreateModal: () => topicsModal.showModal(),
        download,
        dispose: () => {
            if (refreshTimer !== null) {
                window.clearTimeout(refreshTimer);
                refreshTimer = null;
            }
            // Appended to document.body, so it is not removed by clearing the
            // viewer's own container and would otherwise accumulate one dialog
            // per mount.
            topicsModal.remove();
        },
    };
}

// Camera projection/nav mode, grid visibility, section-clipping planes and
// fullscreen — plain imperative bridge functions. This used to be a
// floating BUI toolbar built as hand-rolled DOM; that chrome now lives in
// ViewerRibbon.svelte, which just calls these.
function createSceneControls(components, world, viewport, grids) {
    const clipper = components.get(OBC.Clipper);
    clipper.enabled = false;

    let clippingActive = false;
    let clippingVisible = true;
    let gridVisible = true;

    // Double-click on the viewport to create a clipping plane at the clicked
    // surface, while clipping mode is active.
    viewport.addEventListener("dblclick", () => {
        if (!clippingActive) return;
        clipper.create(world);
    });

    const camera = {
        getProjection: () => world.camera.projection?.current ?? "Perspective",
        setProjection: (mode) => world.camera.projection.set(mode),
        getNavMode: () => world.camera.mode?.id ?? "Orbit",
        setNavMode: (mode) => world.camera.set(mode),
        fit: async () => {
            const meshes = [];
            for (const [, model] of components.get(OBC.FragmentsManager).list) {
                if (model.object) meshes.push(model.object);
            }
            if (meshes.length > 0) await world.camera.fit(meshes, 0.5);
        },
    };

    const grid = {
        isVisible: () => gridVisible,
        toggle: (visible) => {
            gridVisible = visible;
            for (const [, g] of grids.list) g.three.visible = visible;
        },
    };

    const clipping = {
        isModeActive: () => clippingActive,
        toggleMode: (active) => {
            clippingActive = active;
            clipper.enabled = active;
        },
        isVisible: () => clippingVisible,
        toggleVisibility: (visible) => {
            clippingVisible = visible;
            clipper.visible = visible;
        },
        clearAll: () => {
            clipper.deleteAll();
            clipper.enabled = false;
            clippingActive = false;
        },
    };

    const fullscreen = {
        toggle: () => {
            const container = viewport.closest(".bimguard-viewer-root") || viewport.parentElement;
            if (!document.fullscreenElement) {
                (container || viewport).requestFullscreen().catch(() => {});
            } else {
                document.exitFullscreen();
            }
        },
    };

    return { camera, grid, clipping, fullscreen };
}

// ItemsFinder-backed category visibility ("layers" in the linked docs'
// vocabulary — not to be confused with DrawingLayers, which organizes a
// TechnicalDrawing's own projection geometry, see createDrawingsModule).
function createLayersModule(components, hider) {
    const finder = components.get(OBC.ItemsFinder);
    const emitter = createEmitter();
    const visibility = new Map();
    let hiddenMap = null;

    async function recomputeHiddenMap() {
        const maps = [];
        for (const [name, query] of finder.list) {
            if (visibility.get(name) === false) maps.push(await query.test());
        }
        hiddenMap = maps.length ? OBC.ModelIdMapUtils.join(maps) : null;
    }

    async function populateFromModel() {
        try {
            const names = await finder.addFromCategories();
            for (const name of names) {
                if (!visibility.has(name)) visibility.set(name, true);
            }
        } catch (e) {
            console.warn("Could not populate category layers:", e);
        }
        emitter.emit();
    }

    function reset() {
        visibility.clear();
        hiddenMap = null;
        emitter.emit();
    }

    function list() {
        return [...finder.list.keys()].map((name) => ({
            name,
            visible: visibility.get(name) !== false,
        }));
    }

    async function toggle(name, visible) {
        visibility.set(name, visible);
        const query = finder.list.get(name);
        if (query) {
            const map = await query.test();
            await hider.set(visible, map);
        }
        await recomputeHiddenMap();
        emitter.emit();
    }

    async function showAll() {
        for (const name of visibility.keys()) visibility.set(name, true);
        await hider.set(true);
        hiddenMap = null;
        emitter.emit();
    }

    async function hideAll() {
        for (const name of finder.list.keys()) visibility.set(name, false);
        await hider.set(false);
        await recomputeHiddenMap();
        emitter.emit();
    }

    // The ModelIdMap of everything currently visible, honoring per-category
    // toggles — used by the Drawings module to decide what to project, so a
    // generated drawing reflects what the user chose to see, not the whole
    // model. Returns null only when no categories are registered yet.
    async function getProjectableItemsMap() {
        const maps = [];
        for (const [name, query] of finder.list) {
            if (visibility.get(name) === false) continue;
            maps.push(await query.test());
        }
        return maps.length ? OBC.ModelIdMapUtils.join(maps) : null;
    }

    return {
        populateFromModel,
        reset,
        list,
        toggle,
        showAll,
        hideAll,
        onChange: emitter.on,
        getHiddenMap: () => hiddenMap,
        getProjectableItemsMap,
    };
}

// Plan / elevation / section Views, and saving the currently open one as a
// BCF viewpoint on the selected topic (or opening the create-topic modal
// first if nothing is selected yet).
function createViewsModule(components, world, viewport, topicsWorkspace) {
    const views = components.get(OBC.Views);
    views.world = world;
    const emitter = createEmitter();

    let storeyViewsReady = false;
    let elevationViewsReady = false;
    let sectionModeActive = false;
    const planIds = new Set();
    const elevationIds = new Set();
    const sectionIds = new Set();

    async function ensurePlans() {
        if (storeyViewsReady) return;
        storeyViewsReady = true;
        try {
            const created = await views.createFromIfcStoreys({});
            for (const v of created) planIds.add(v.id);
        } catch (e) {
            console.warn("Could not create plan views:", e);
        }
        emitter.emit();
    }

    function ensureElevations() {
        if (elevationViewsReady) return;
        elevationViewsReady = true;
        try {
            const created = views.createElevations({ combine: true });
            for (const v of created) elevationIds.add(v.id);
        } catch (e) {
            console.warn("Could not create elevation views:", e);
        }
        emitter.emit();
    }

    async function plan(id) {
        await ensurePlans();
        const targetId = id || [...planIds][0];
        if (targetId) views.open(targetId);
        emitter.emit();
    }

    function elevation(id) {
        ensureElevations();
        const targetId = id || [...elevationIds][0];
        if (targetId) views.open(targetId);
        emitter.emit();
    }

    function enterSectionMode() {
        sectionModeActive = true;
        emitter.emit();
    }
    function exitSectionMode() {
        sectionModeActive = false;
        emitter.emit();
    }

    viewport.addEventListener("dblclick", async () => {
        if (!sectionModeActive) return;
        try {
            const raycaster = components.get(OBC.Raycasters).get(world);
            const result = await raycaster.castRay();
            if (!result || !result.face) return;
            const normal = result.face.normal
                .clone()
                .transformDirection(result.object.matrixWorld)
                .normalize();
            const view = views.create(normal, result.point, {
                id: `Section ${views.list.size + 1}`,
                world,
            });
            sectionIds.add(view.id);
            views.open(view.id);
        } catch (e) {
            console.warn("Could not create section view:", e);
        } finally {
            sectionModeActive = false;
            emitter.emit();
        }
    });

    function back() {
        views.close();
        emitter.emit();
    }

    function listPlans() {
        return [...planIds].map((id) => ({ id, label: id }));
    }
    function listElevations() {
        return [...elevationIds].map((id) => ({ id, label: id }));
    }
    function activeViewId() {
        for (const [id, v] of views.list) if (v.open) return id;
        return null;
    }
    function activeView() {
        const id = activeViewId();
        return id ? views.list.get(id) : null;
    }

    async function saveAsBcfViewpoint() {
        const view = activeView();
        if (!view) return;
        const topic = topicsWorkspace.getSelectedTopic();
        if (!topic) {
            // No topic selected to attach to — let the user create one first,
            // then try again.
            topicsWorkspace.openCreateModal();
            return;
        }
        const viewpoints = components.get(OBC.Viewpoints);
        const viewpoint = viewpoints.create();
        viewpoint.world = world;
        topic.viewpoints.add(viewpoint.guid);
        topicsWorkspace.refreshTopicsList();
        emitter.emit();
    }

    function resetForNewModel() {
        views.close();
        for (const id of new Set([...planIds, ...elevationIds, ...sectionIds])) {
            views.list.get(id)?.dispose();
        }
        planIds.clear();
        elevationIds.clear();
        sectionIds.clear();
        storeyViewsReady = false;
        elevationViewsReady = false;
        sectionModeActive = false;
        emitter.emit();
    }

    return {
        plan,
        elevation,
        enterSectionMode,
        exitSectionMode,
        isSectionModeActive: () => sectionModeActive,
        back,
        hasOpenViews: () => views.hasOpenViews,
        listPlans,
        listElevations,
        activeViewId,
        activeView,
        saveAsBcfViewpoint,
        resetForNewModel,
        onChange: emitter.on,
    };
}

// Generates an annotated 2D TechnicalDrawing from the currently open View,
// organizes its projection geometry into DrawingLayers, hosts a
// `bim-sheet-board` (paper-space) widget for laying it out and exporting
// DXF, and can attach that DXF to the selected BCF topic as a native BCF
// document reference (so it round-trips through the existing "Download
// BCF" export like any other attachment).
function createDrawingsModule(components, world, viewsModule, layersModule, topicsWorkspace, sheetBoardHost) {
    const techDrawings = components.get(OBC.TechnicalDrawings);
    const dxfManager = components.get(OBC.DxfManager);
    const emitter = createEmitter();

    const entries = new Map(); // drawingId -> { drawing, viewport, label }
    let activeId = null;
    let paper = null;
    let sheetBoard = null;

    function downloadDxf(dxf) {
        const href = URL.createObjectURL(new File([dxf], "bimguard-drawing.dxf"));
        const link = document.createElement("a");
        link.href = href;
        link.download = "bimguard-drawing.dxf";
        link.click();
        URL.revokeObjectURL(href);
    }

    function ensureSheetBoard() {
        if (sheetBoard) return sheetBoard;
        sheetBoard = document.createElement("bim-sheet-board");
        sheetBoard.components = components;
        sheetBoard.style.cssText = "width:100%;height:100%;display:block;";

        paper = document.createElement("bim-paper-space");
        paper.label = "Sheet 1";
        paper.sheetNumber = "A-01";
        paper.size = "A3";
        paper.orientation = "landscape";
        sheetBoard.appendChild(paper);

        sheetBoard.addEventListener("viewportdxfexport", (event) => downloadDxf(event.detail.dxf));
        sheetBoard.addEventListener("paperdxfexport", (event) => downloadDxf(event.detail.dxf));

        if (sheetBoardHost) sheetBoardHost.replaceChildren(sheetBoard);
        return sheetBoard;
    }

    async function createFromOpenView() {
        const view = viewsModule.activeView();
        if (!view) return;

        let drawing;
        try {
            const board = ensureSheetBoard();

            drawing = techDrawings.create(world);
            drawing.orientTo(view.plane.normal);
            drawing.three.position.copy(view.plane.coplanarPoint(new THREE.Vector3()));

            drawing.layers.create("visible", {
                material: new THREE.LineBasicMaterial({ color: 0x1a1a1a }),
            });
            drawing.layers.create("hidden", {
                material: new THREE.LineDashedMaterial({ color: 0x9ca3af, dashSize: 0.2, gapSize: 0.1 }),
            });

            const itemsMap = await layersModule.getProjectableItemsMap();
            if (itemsMap) {
                await drawing.addProjectionFromItems(itemsMap, {
                    layers: { visible: "visible", hidden: "hidden" },
                });
            }

            const range = view.range || 10;
            const vp = drawing.viewports.create({
                left: -range,
                right: range,
                top: range,
                bottom: -range,
            });

            const label = `Drawing ${entries.size + 1}`;
            board.addViewport(paper, drawing.id, vp.uuid, { x: 10, y: 10 });
            entries.set(drawing.id, { drawing, viewport: vp, label });
            activeId = drawing.id;
        } catch (e) {
            console.warn("Could not create technical drawing (retrying usually recovers from a cold-start glitch in the sheet-board widget):", e);
            drawing?.dispose();
        } finally {
            emitter.emit();
        }
    }

    function list() {
        return [...entries.entries()].map(([id, entry]) => ({ id, label: entry.label }));
    }
    function setActive(id) {
        if (!entries.has(id)) return;
        activeId = id;
        emitter.emit();
    }
    function activeEntry() {
        return activeId ? entries.get(activeId) : null;
    }
    function activeLayers() {
        const entry = activeEntry();
        if (!entry) return [];
        return [...entry.drawing.layers].map(([name, layer]) => ({
            name,
            visible: layer.visible,
            color: `#${layer.material.color.getHexString()}`,
        }));
    }
    function toggleActiveLayer(name, visible) {
        activeEntry()?.drawing.layers.setVisibility(name, visible);
        emitter.emit();
    }
    function setActiveLayerColor(name, colorHex) {
        activeEntry()?.drawing.layers.setColor(name, colorHex);
        emitter.emit();
    }

    async function attachActiveToBcfTopic() {
        const entry = activeEntry();
        const topic = topicsWorkspace.getSelectedTopic();
        if (!entry || !topic) return;

        const dxf = dxfManager.exporter.export([
            { drawing: entry.drawing, viewports: [{ viewport: entry.viewport }] },
        ]);
        const bytes = new TextEncoder().encode(dxf);
        const guid = crypto.randomUUID();
        topicsWorkspace.topics.documents.set(guid, {
            type: "internal",
            fileName: `${entry.label}.dxf`,
            data: bytes,
        });
        topic.document_references = topic.document_references || [];
        topic.document_references.push({
            guid: crypto.randomUUID(),
            document_guid: guid,
            description: `Technical drawing: ${entry.label}`,
        });
        topicsWorkspace.refreshTopicsList();
        emitter.emit();
    }

    function dispose() {
        for (const { drawing } of entries.values()) drawing.dispose();
        entries.clear();
        activeId = null;
        emitter.emit();
    }

    return {
        list,
        activeId: () => activeId,
        setActive,
        activeLayers,
        toggleActiveLayer,
        setActiveLayerColor,
        createFromOpenView,
        attachActiveToBcfTopic,
        onChange: emitter.on,
        dispose,
    };
}

export async function initViewer(mounts) {
    const viewportHost = mounts?.viewport;
    const detailsHost = mounts?.details;
    const drawingsHost = mounts?.drawings;
    if (!viewportHost) {
        console.error("initViewer: a viewport mount element is required", mounts);
        return null;
    }

    BUI.Manager.init();
    if (CUI.Manager?.init) CUI.Manager.init();

    // Every mount of this module in one page session gets a number, so a
    // console transcript shows whether a failure came from a fresh viewer or
    // from one that had already been mounted and torn down.
    mountCount += 1;
    const mountId = mountCount;
    let disposed = false;
    /** In-flight filter worker, terminated on dispose so it cannot outlive us. */
    let activeFilterWorker = null;
    console.info(`${LOG} viewer mount #${mountId}`);

    const viewport = document.createElement("bim-viewport");
    viewport.className = "bimguard-viewport";
    viewport.style.cssText = "width:100%;height:100%;display:block;";
    const components = new OBC.Components();

    const worlds = components.get(OBC.Worlds);
    const world = worlds.create();

    world.scene = new OBC.SimpleScene(components);
    world.renderer = new OBC.SimpleRenderer(components, viewport);
    world.camera = new OBC.OrthoPerspectiveCamera(components);

    world.scene.setup();
    world.camera.controls.setLookAt(74, 16, 0.2, 30, -4, 27);
    components.init();

    const grids = components.get(OBC.Grids);
    grids.create(world);

    const { highlightTopics, hider, isolate, highlighter, disposeHighlighting } =
        installErrorHighlighting(components, world);

    function applyTheme() {
        const theme = getThemeConfig();
        if (world.scene && world.scene.three) {
            world.scene.three.background = new THREE.Color(theme.canvasHex);
        }
        for (const [, g] of grids.list) {
            if (g && g.three) {
                if (g.three.material) {
                    if (Array.isArray(g.three.material)) {
                        g.three.material.forEach((m) => {
                            if (m && m.color) m.color.setHex(theme.gridColor);
                        });
                    } else if (g.three.material.color) {
                        g.three.material.color.setHex(theme.gridColor);
                    }
                }
            }
        }
        try {
            const errorStyle = highlighter?.styles?.get(ERROR_HIGHLIGHT_STYLE);
            if (errorStyle && errorStyle.color) {
                errorStyle.color.setHex(theme.errorHex);
            }
        } catch {}
    }

    applyTheme();

    let themeObserver = null;
    if (typeof MutationObserver !== "undefined" && typeof document !== "undefined") {
        themeObserver = new MutationObserver(() => {
            applyTheme();
        });
        themeObserver.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["class", "data-theme"],
        });
    }

    const workspace = createTopicsWorkspace(components, world, viewport, highlightTopics);
    const sceneControls = createSceneControls(components, world, viewport, grids);
    const layers = createLayersModule(components, hider);
    isolate.setHiddenMapProvider(layers.getHiddenMap);
    const views = createViewsModule(components, world, viewport, workspace);
    const drawings = createDrawingsModule(components, world, views, layers, workspace, drawingsHost);

    const fragments = components.get(OBC.FragmentsManager);
    const workerUrl = await OBC.FragmentsManager.getWorker();
    fragments.init(workerUrl);

    world.camera.controls.addEventListener("update", () => fragments.core.update());
    fragments.list.onItemSet.add(async ({ value: model }) => {
        model.useCamera(world.camera.three);
        world.scene.three.add(model.object);
        await fragments.core.update(true);
        await layers.populateFromModel();
    });

    const fragmentIfcLoader = components.get(OBC.IfcLoader);
    await fragmentIfcLoader.setup({
        autoSetWasm: false,
        wasm: {
            path: "https://unpkg.com/web-ifc@0.0.77/",
            absolute: true,
        },
    });

    // bim-viewport drives this from its own internal ResizeObserver, which can
    // still fire once after the element is detached — and after dispose,
    // SimpleWorld's `renderer`/`camera` are getters that THROW ("No camera
    // initialized!") rather than return undefined, so a truthiness guard alone
    // is not enough. Hence the disposed flag, the try, and removing the
    // listener in dispose so the observer has nothing left to call.
    const onViewportResize = () => {
        if (disposed) return;
        try {
            if (world.renderer) world.renderer.resize();
            if (world.camera) world.camera.updateAspect();
        } catch {
            // World torn down between the observer firing and this running.
        }
    };
    viewport.addEventListener("resize", onViewportResize);

    viewportHost.replaceChildren(viewport);
    if (detailsHost) detailsHost.replaceChildren(workspace.topicsPanel, workspace.topicPanel);
    // The Layers dock's content is plain Svelte (LayersPanel.svelte) driven
    // entirely through the `layers` bridge returned below — no engine DOM to
    // mount for it.

    function isFiniteBox(box) {
        return [box.min, box.max].every(
            (v) => Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z),
        );
    }

    // Union of every loaded model's bounds, or null when nothing measurable is
    // loaded. FragmentsModel.box maps its cached local bbox through the
    // object's world matrix, and auto-coordination shifts that object after
    // setup, so the matrix has to be refreshed before reading it.
    function getModelsBoundingBox() {
        const box = new THREE.Box3().makeEmpty();
        for (const [, model] of fragments.list) {
            if (!model.object) continue;
            model.object.updateMatrixWorld(true);
            const modelBox = model.box;
            // A model whose geometry failed to stream reports an empty or
            // non-finite box; unioning that would poison the whole result.
            if (!modelBox || modelBox.isEmpty() || !isFiniteBox(modelBox)) continue;
            box.union(modelBox);
        }
        return box.isEmpty() ? null : box;
    }

    // Both of the library's default cameras clip at 1000 units (perspective
    // also starts at 1), which cuts a site model off at the far plane and
    // slices a small assembly open at the near one. Scale both planes to the
    // model so the fit below is actually visible.
    function updateClippingPlanes(radius) {
        for (const camera of [world.camera.threePersp, world.camera.threeOrtho]) {
            if (!camera) continue;
            camera.near = Math.max(radius / 1000, 0.01);
            camera.far = Math.max(radius * 100, 1000);
            camera.updateProjectionMatrix();
        }
    }

    // Frames the loaded geometry. fitToSphere works out the distance for
    // whichever projection is active (perspective FOV, ortho zoom) but only
    // moves the camera along its current view direction, so the camera is
    // aimed from a fixed isometric angle first — otherwise the framing
    // inherits whatever angle was left over from the previous model.
    async function fitToModel({ transition = false } = {}) {
        const box = getModelsBoundingBox();
        if (!box) return false;

        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        // Half the box diagonal is the true bounding sphere, so every corner
        // is guaranteed inside the view once fitToSphere has framed it.
        const boundingRadius = size.length() / 2;
        const radius = Math.max(boundingRadius, MIN_FIT_RADIUS) * FIT_PADDING;

        updateClippingPlanes(radius);

        const eye = center.clone().addScaledVector(FIT_VIEW_DIRECTION, radius * 2);
        const controls = world.camera.controls;
        await controls.setLookAt(eye.x, eye.y, eye.z, center.x, center.y, center.z, false);
        await controls.fitToSphere(new THREE.Sphere(center, radius), transition);
        await fragments.core.update(true);
        return true;
    }

    async function clearModels() {
        try {
            isolate.reset();
            views.resetForNewModel();
            drawings.dispose();
            layers.reset();
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
    // `getHeaders` is a live callback (not a pre-computed headers object):
    // the host page's Supabase session can still be settling when this
    // module's first fetch goes out (e.g. a direct deep link straight into
    // the viewer), so a snapshot taken at call time can be stale before the
    // token exists. Re-reading it on a 401 and retrying once picks up a
    // token that has since landed instead of leaving the model unloadable.
    async function fetchWithAuthRetry(url, getHeaders) {
        const initial = typeof getHeaders === "function" ? getHeaders() : getHeaders;
        const response = await fetch(url, { headers: initial });
        if (response.status === 401 && typeof getHeaders === "function") {
            const retry = getHeaders();
            if (retry && retry.Authorization && retry.Authorization !== initial?.Authorization) {
                return fetch(url, { headers: retry });
            }
        }
        return response;
    }

    let activeLoad = Promise.resolve();
    async function loadIfc(urlOrFile, getHeaders) {
        const previous = activeLoad;
        let release;
        activeLoad = new Promise((resolve) => { release = resolve; });
        try {
            await previous;
            await clearModels();
            const file = typeof urlOrFile === "string"
                ? await fetchWithAuthRetry(urlOrFile, getHeaders).then(async (response) => {
                    if (!response.ok) throw new Error(`IFC request failed (${response.status})`);
                    return new File([await response.blob()], "project.ifc");
                })
                : urlOrFile;
            const data = await file.arrayBuffer();
            const buffer = new Uint8Array(data);
            await fragmentIfcLoader.load(buffer, true, file.name.replace(/\.ifc$/i, ""));
            // load() only resolves once the model's bounding box is final, so
            // the camera can be framed straight away — no need to wait for the
            // remaining geometry to stream in.
            await fitToModel();
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
    //
    // Two archive shapes reach this viewer and they label that line
    // differently, so both spellings are tried, most specific first:
    //   "ElementGUID: <guid>"  — persisted artifacts, from
    //     pipeline_services._to_bcf_topic
    //   "GUID: <guid>"         — the /analyze/export?fmt=bcf archive, whose
    //     description is built by phase_6e_export._description under an
    //     "ELEMENT" heading
    // Both needles are anchored on the label, so neither can match a GUID
    // that merely appears somewhere else in the text.
    //
    // One element usually carries several findings (the demo's clicked fitting
    // has four: one MC critical and three normal), so a match is rarely
    // unique. The deep link names the element, not the finding, so the most
    // severe topic is the one to show — it is the row someone is most likely
    // to have clicked, and it is at least deterministic, where "first one the
    // archive happened to yield" is not. The vocabulary is the exporter's own
    // Critical/Major/Normal/Minor (phase_6e_export, RiskBand -> priority), and
    // priorityRank is shared with the archive filter so both agree.
    function findTopicByElementGuid(elementGuid) {
        if (!elementGuid) return null;
        const needles = [`ElementGUID: ${elementGuid}`, `GUID: ${elementGuid}`];
        for (const needle of needles) {
            const matches = [];
            for (const topic of workspace.topics.list.values()) {
                if ((topic.description || "").includes(needle)) matches.push(topic);
            }
            if (matches.length === 0) continue;
            matches.sort((a, b) => priorityRank(a.priority) - priorityRank(b.priority));
            return matches[0];
        }
        return null;
    }

    /** Total ids across a ModelIdMap, for the select log line. */
    function countSelection(map) {
        if (!map) return 0;
        let n = 0;
        for (const ids of Object.values(map)) {
            n += ids instanceof Set ? ids.size : (ids?.length ?? 0);
        }
        return n;
    }

    // Frames whatever is currently highlighted. Returns false when nothing is
    // selected, or when the selection resolved to no geometry in the loaded
    // model, so the caller can tell the user rather than leave the camera
    // parked somewhere unrelated with no explanation.
    //
    // SimpleCamera.fitToItems (inherited by OrthoPerspectiveCamera) takes a
    // ModelIdMap straight off, going through BoundingBoxer.addFromModelIdMap
    // and controls.fitToSphere internally — so there is no box to assemble
    // here. Note fitToBox does not exist on this build's controls.
    async function fitToSelection() {
        const map = isolate.getSelectionMap();
        if (!map || OBC.ModelIdMapUtils.isEmpty(map)) return false;
        try {
            await world.camera.fitToItems(map);
            return true;
        } catch (e) {
            console.warn("Could not fit camera to selection:", e);
            return false;
        }
    }

    // `autoSelectTopic` false loads the archive and selects nothing, leaving
    // the caller to find its own topic. A deep link for one specific element
    // needs that: the fall-back below picks the archive's first topic when the
    // GUID misses, which for a download is a reasonable "show me something"
    // and for a deep link would silently highlight the wrong element.
    async function loadBcf(urlOrFile, elementGuid, getHeaders, options = {}) {
        const { autoSelectTopic = true } = options;
        try {
            const file = typeof urlOrFile === "string"
                ? await fetchWithAuthRetry(urlOrFile, getHeaders).then(async (response) => {
                    if (!response.ok) throw new Error(`BCF request failed (${response.status})`);
                    return new File([await response.blob()], "report.bcf");
                })
                : urlOrFile;
            const imported = await workspace.topics.load(new Uint8Array(await file.arrayBuffer()));
            const importedViewpoints = Array.from(imported.viewpoints);
            for (const viewpoint of importedViewpoints) viewpoint.world = world;
            workspace.refreshTopicsList();

            if (autoSelectTopic) {
                const targetTopic = findTopicByElementGuid(elementGuid)
                    || workspace.topics.list.values().next().value;
                if (targetTopic) await workspace.selectTopic(targetTopic);
            }
            return imported;
        } catch (error) {
            console.error("Error loading BCF file", error);
            throw error;
        }
    }

    /**
     * Filter the archive, off the main thread when the browser allows it.
     *
     * JSZip pumps each inflate through setImmediate, which in a browser is a
     * postMessage task competing with rendering — 2,764 entries cost 58.6 s on
     * the main thread here against 365 ms in Node. The worker gets that queue
     * to itself and the page stays interactive meanwhile.
     *
     * The archive is CLONED to the worker rather than transferred. Transfer
     * would save a copy of ~5 MB, but it detaches the buffer here, and the
     * inline fallback below then has nothing left to work on if the worker
     * turns out to be unusable. A few milliseconds of copy buys a fallback
     * that actually works; the result comes back transferred, which is free.
     */
    function runFilter(buffer, elementGuid) {
        let worker;
        try {
            worker = new Worker(
                new URL("./bcf-filter.worker.js?v=viewer-isolate-5", import.meta.url),
                { type: "module" },
            );
        } catch (error) {
            console.warn(`${LOG} worker unavailable, filtering on main thread:`, error);
            return filterBcfArchive(JSZip, buffer, elementGuid);
        }

        activeFilterWorker = worker;
        return new Promise((resolve, reject) => {
            const finish = (fn, value) => {
                worker.terminate();
                if (activeFilterWorker === worker) activeFilterWorker = null;
                fn(value);
            };
            worker.onmessage = (event) => {
                const { ok, result, error } = event.data || {};
                if (ok) finish(resolve, result);
                else finish(reject, new Error(error || "filter worker failed"));
            };
            worker.onerror = (event) => {
                // A worker that fails to start (import blocked, syntax) must
                // not strand the caller — run it inline instead.
                console.warn(`${LOG} worker error, filtering on main thread:`, event.message || event);
                worker.terminate();
                if (activeFilterWorker === worker) activeFilterWorker = null;
                filterBcfArchive(JSZip, buffer, elementGuid).then(resolve, reject);
            };
            worker.postMessage({ buffer, elementGuid });
        });
    }

    /**
     * The findings deep-link path: fetch an archive, cut it down to the one
     * element, then load, select and frame it.
     *
     * The whole-archive route this replaces was correct but unusable — the
     * hospital demo's export is 1,384 topics and 5.1 MB, and BCFTopics.load
     * parses every topic, instantiates every viewpoint, and re-renders the
     * topics table once per row, so the selection could not run for minutes.
     * Filtering the bytes first (see bcf-filter.js) leaves a handful of
     * entries, and everything downstream is then trivially fast.
     *
     * `sources` is tried in order, as {label, url}; the first that fetches wins.
     * Returns {ok, reason}. Never throws: every failure is a reason string, so
     * the host page can show a notice and clear its spinner on one code path.
     */
    async function loadBcfForElement(sources, elementGuid, getHeaders) {
        if (!elementGuid) return { ok: false, reason: "no element guid" };

        // ── fetch ────────────────────────────────────────────────────────
        let buffer = null;
        for (const { label, url } of sources) {
            const t0 = performance.now();
            try {
                const response = await fetchWithAuthRetry(url, getHeaders);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                buffer = await response.arrayBuffer();
                console.info(`${LOG} source=${label} bytes=${buffer.byteLength} ms=${since(t0)}`);
                break;
            } catch (error) {
                console.warn(`${LOG} fetch failed: ${label} ${error?.message || error}`);
            }
        }
        if (!buffer) return { ok: false, reason: "no BCF archive available" };

        // ── filter ───────────────────────────────────────────────────────
        let filtered;
        const tFilter = performance.now();
        try {
            filtered = await runFilter(buffer, elementGuid);
        } catch (error) {
            console.warn(`${LOG} filter failed:`, error);
            return { ok: false, reason: "could not read the BCF archive" };
        }
        console.info(`${LOG} archive entries=${filtered.entries} topics=${filtered.topics}`);
        console.info(
            `${LOG} filter guid=${elementGuid} kept=${filtered.kept} ` +
            `pruned_relations=${filtered.strippedRelations ?? 0} ms=${since(tFilter)}`,
        );
        if (!filtered.data) {
            console.warn(`${LOG} filter failed: no topic references ${elementGuid}`);
            return { ok: false, reason: "no BCF topic references this element" };
        }

        // ── load ─────────────────────────────────────────────────────────
        const tLoad = performance.now();
        try {
            const imported = await workspace.topics.load(filtered.data);
            for (const viewpoint of Array.from(imported.viewpoints)) viewpoint.world = world;
            workspace.refreshTopicsList();
            const loadedCount = workspace.topics.list.size ?? filtered.kept;
            console.info(`${LOG} bcf loaded topics=${loadedCount} ms=${since(tLoad)}`);
        } catch (error) {
            console.warn(`${LOG} load failed: ${error?.message || error}`);
            return { ok: false, reason: "could not load the filtered BCF archive" };
        }

        // ── select ───────────────────────────────────────────────────────
        const topic = findTopicByElementGuid(elementGuid);
        if (!topic) {
            console.warn(`${LOG} select failed: no loaded topic matched ${elementGuid}`);
            return { ok: false, reason: "no BCF topic matched this element" };
        }
        try {
            await workspace.selectTopic(topic);
        } catch (error) {
            // The object, not its message: the stack is what identified the
            // nested go() wrappers behind the remount bug.
            console.warn(`${LOG} select failed:`, error);
            return { ok: false, reason: "could not select the element's topic" };
        }
        const items = countSelection(isolate.getSelectionMap());
        console.info(
            `${LOG} select topic=${topic.title || topic.guid} ` +
            `priority=${topic.priority || "-"} selection_items=${items}`,
        );
        if (items === 0) {
            console.warn(`${LOG} select failed: topic resolved to no geometry in this model`);
            return { ok: false, reason: "the element is not in the loaded model" };
        }

        // ── fit ──────────────────────────────────────────────────────────
        const fitted = await fitToSelection();
        console.info(`${LOG} fit ok=${fitted}`);
        if (!fitted) {
            console.warn(`${LOG} fit failed: no bounding geometry for the selection`);
            return { ok: false, reason: "could not frame the element" };
        }
        return { ok: true, reason: null };
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
        loadBcf,
        loadIfc,
        getCameraState,
        setCameraState,
        fitToModel,
        setupFileLoader,
        selectTopic: workspace.selectTopic,
        findTopicByElementGuid,
        fitToSelection,
        loadBcfForElement,
        topics: {
            getSelected: workspace.getSelectedTopic,
            onSelectionChange: workspace.onSelectionChange,
            openCreateModal: workspace.openCreateModal,
            download: workspace.download,
        },
        camera: sceneControls.camera,
        grid: sceneControls.grid,
        clipping: sceneControls.clipping,
        fullscreen: sceneControls.fullscreen,
        isolate,
        views,
        layers,
        drawings,
        setTheme: applyTheme,
        dispose: () => {
            // Flag first: everything below can trigger a resize or a pending
            // callback, and those must see a torn-down viewer, not race it.
            disposed = true;
            console.info(`${LOG} viewer dispose #${mountId}`);
            try {
                if (themeObserver) themeObserver.disconnect();
                drawings.dispose();
                viewport.removeEventListener("resize", onViewportResize);
                if (activeFilterWorker) {
                    activeFilterWorker.terminate();
                    activeFilterWorker = null;
                }
                disposeHighlighting();
                workspace.dispose();
                components.dispose();
            } catch (e) {
                console.warn(`${LOG} dispose #${mountId} failed:`, e);
            }
        },
    };
}
