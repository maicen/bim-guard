import * as THREE from 'https://esm.sh/three@0.175.0';
import * as OBC from 'https://esm.sh/@thatopen/components@3.3.3?deps=three@0.175.0,web-ifc@0.0.74,@thatopen/fragments@3.3.0';

export async function initViewer(containerId) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`Container with id ${containerId} not found.`);
        return null;
    }

    // 1. Initialize core components
    const components = new OBC.Components();

    // 2. Set up the World (Scene, Renderer, Camera)
    const worlds = components.get(OBC.Worlds);
    const world = worlds.create();

    world.scene = new OBC.SimpleScene(components);
    world.renderer = new OBC.SimpleRenderer(components, container);
    world.camera = new OBC.SimpleCamera(components);

    // 3. Initialize the viewer
    components.init();
    world.scene.setup();
    world.scene.three.background = null;

    world.camera.controls.setLookAt(74, 16, 0.2, 30, -4, 27);

    // 4. Add Grids
    const grids = components.get(OBC.Grids);
    grids.create(world);

    // 5. Setup Fragments and IFC Loader
    const fragments = components.get(OBC.FragmentsManager);
    const workerBlob = await fetch("https://unpkg.com/@thatopen/fragments@3.3.0/dist/Worker/worker.mjs").then(r => r.blob());
    fragments.init(URL.createObjectURL(workerBlob));

    const fragmentIfcLoader = components.get(OBC.IfcLoader);
    await fragmentIfcLoader.setup({
        autoSetWasm: false,
        wasm: {
            path: "https://unpkg.com/web-ifc@0.0.74/",
            absolute: true,
        },
    });

    // 6. Connect auto-resize
    const resizeObserver = new ResizeObserver(() => {
        if (world.renderer) world.renderer.resize();
        if (world.camera) world.camera.updateAspect();
    });
    resizeObserver.observe(container);

    // 7. Handle File Loading
    async function loadIfc(file) {
        try {
            console.log("Loading IFC file:", file.name, "...");
            const data = await file.arrayBuffer();
            const buffer = new Uint8Array(data);
            const model = await fragmentIfcLoader.load(buffer);
            world.scene.three.add(model);
            console.log("IFC Model loaded successfully", model);
        } catch (error) {
            console.error("Error loading IFC File", error);
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

    return { components, world, loadIfc, setupFileLoader };
}
