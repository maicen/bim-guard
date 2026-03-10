import * as THREE from 'https://esm.sh/three';
import * as OBC from 'https://esm.sh/@thatopen/components';

const container = document.getElementById('viewer-container');

// 1. Initialize core components
const components = new OBC.Components();

// 2. Set up the World (Scene, Renderer, Camera)
const worlds = components.get(OBC.Worlds);
const world = worlds.create();

world.scene = new OBC.SimpleScene(components);
world.renderer = new OBC.SimpleRenderer(components, container);
world.camera = new OBC.SimpleCamera(components);

// 3. Initialize the viewer and default lighting/grid
components.init();
world.scene.setup();
world.camera.controls.setLookAt(5, 5, 5, 0, 0, 0);

// 4. Add a test mesh to verify the scene is working
const geometry = new THREE.BoxGeometry();
const material = new THREE.MeshNormalMaterial();
const cube = new THREE.Mesh(geometry, material);
world.scene.three.add(cube);
