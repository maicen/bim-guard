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

    const originalGo = OBC.Viewpoint.prototype.go;
    OBC.Viewpoint.prototype.go = async function highlightingGo(config) {
        await originalGo.call(this, config);
        await highlighter.clear(ERROR_HIGHLIGHT_STYLE);
        const selectionMap = await this.getSelectionMap();
        if (!OBC.ModelIdMapUtils.isEmpty(selectionMap)) {
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
        if (maps.length > 0) {
            await highlighter.highlightByID(ERROR_HIGHLIGHT_STYLE, OBC.ModelIdMapUtils.join(maps), false, false);
        }
    }

    return { highlightTopics };
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

    const { highlightTopics } = installErrorHighlighting(components, world);

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
    container.replaceChildren(workspace.app);

    async function clearModels() {
        try {
            for (const [, model] of fragments.list) {
                if (model.object) world.scene.three.remove(model.object);
                if (model.dispose) model.dispose();
            }
            fragments.list.clear();
        } catch (e) {
            console.warn("Could not clear previous models:", e);
        }
    }

    // `replace` defaults to true so every existing single-model caller keeps
    // its "one model at a time" behaviour unchanged. The multi-model viewer
    // passes false for every model after the first, which is the only way to
    // get more than one model into the scene at once.
    // `name` overrides the model id, which otherwise derives from the
    // filename -- two uploads sharing a name would collide in `fragments.list`.
    async function loadIfc(urlOrFile, { replace = true, name = "" } = {}) {
        try {
            if (replace) await clearModels();
            const file = typeof urlOrFile === "string"
                ? await fetch(urlOrFile).then(async (response) => {
                    if (!response.ok) throw new Error(`IFC request failed (${response.status})`);
                    return new File([await response.blob()], "project.ifc");
                })
                : urlOrFile;
            const data = await file.arrayBuffer();
            const buffer = new Uint8Array(data);
            const modelId = name || file.name.replace(/\.ifc$/i, "");
            return await fragmentIfcLoader.load(buffer, true, modelId);
        } catch (error) {
            console.error("Error loading IFC file", error);
            throw error;
        }
    }

    // Toggling a model's visibility mutates the three.js scene graph directly,
    // which on-demand rendering will not notice on its own.
    async function refresh() {
        try {
            await fragments.core.update(true);
        } catch (e) {
            console.warn("Could not refresh the viewer:", e);
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

    async function loadBcf(urlOrFile, elementGuid) {
        try {
            const file = typeof urlOrFile === "string"
                ? await fetch(urlOrFile).then(async (response) => {
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

    return {
        components,
        world,
        topics: workspace.topics,
        loadBcf,
        loadIfc,
        clearModels,
        refresh,
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
