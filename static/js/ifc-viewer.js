import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.175.0/+esm';
import * as OBC from 'https://cdn.jsdelivr.net/npm/@thatopen/components@3.3.3/+esm';

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
    world.scene.three.background = null; // transparent background

    // Set camera LookAt like in useBIMViewer
    world.camera.controls.setLookAt(74, 16, 0.2, 30, -4, 27);
    
    // 4. Add Grids
    const grids = components.get(OBC.Grids);
    grids.create(world);

    // 5. Setup Fragments and IFC Loader
    const fragments = components.get(OBC.FragmentsManager);
    const workerFile = await fetch("https://thatopen.github.io/engine_fragment/resources/worker.mjs");
    const workerBlob = await workerFile.blob();
    const workerUrl = URL.createObjectURL(workerBlob);
    fragments.init(workerUrl);

    const fragmentIfcLoader = components.get(OBC.IfcLoader);
    await fragmentIfcLoader.setup();

    fragmentIfcLoader.settings.wasm = {
        path: "https://cdn.jsdelivr.net/npm/web-ifc@0.0.75/",
        absolute: true
    };

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
            
            // Generate fragments
            const model = await fragmentIfcLoader.load(buffer);
            world.scene.three.add(model);
            console.log("IFC Model loaded successfully", model);
        } catch (error) {
            console.error("Error loading IFC File", error);
        }
    }

    // 8. Global listener setup for file inputs
    function setupFileLoader(inputId) {
        const input = document.getElementById(inputId);
        if (input) {
            input.addEventListener('change', async (event) => {
                const file = event.target.files[0];
                if (file) {
                    await loadIfc(file);
                }
            });
        }
    }

    return {
        components,
        world,
        loadIfc,
        setupFileLoader
    };
}
