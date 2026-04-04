import * as THREE from 'https://esm.sh/three@0.160.0';
import { OrbitControls } from 'https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls';
import { IFCLoader } from 'https://esm.sh/web-ifc-three@0.0.126?deps=three@0.160.0,web-ifc@0.0.68';

export async function initViewer(containerId) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`Container #${containerId} not found.`);
        return null;
    }

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a1a);

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    // Camera
    const camera = new THREE.PerspectiveCamera(
        45,
        container.clientWidth / container.clientHeight,
        0.01,
        5000
    );
    camera.position.set(50, 50, 50);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const sun = new THREE.DirectionalLight(0xffffff, 0.8);
    sun.position.set(50, 100, 50);
    scene.add(sun);

    // Grid
    scene.add(new THREE.GridHelper(100, 20, 0x444444, 0x333333));

    // IFC loader
    const ifcLoader = new IFCLoader();
    await ifcLoader.ifcManager.setWasmPath('https://unpkg.com/web-ifc@0.0.68/');

    // Render loop
    (function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    })();

    // Resize handling
    new ResizeObserver(() => {
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    }).observe(container);

    async function loadIfc(urlOrFile) {
        let url;
        let created = false;
        if (typeof urlOrFile === 'string') {
            url = urlOrFile;
        } else {
            url = URL.createObjectURL(urlOrFile);
            created = true;
        }
        try {
            console.log('Loading IFC…');
            const model = await ifcLoader.loadAsync(url);
            scene.add(model);

            // Fit camera to model bounds
            const box = new THREE.Box3().setFromObject(model);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            camera.position.set(
                center.x + maxDim * 1.5,
                center.y + maxDim,
                center.z + maxDim * 1.5
            );
            controls.target.copy(center);
            controls.update();
            console.log('IFC loaded successfully.');
        } catch (err) {
            console.error('Error loading IFC:', err);
        } finally {
            if (created) URL.revokeObjectURL(url);
        }
    }

    return { scene, camera, renderer, controls, loadIfc };
}
