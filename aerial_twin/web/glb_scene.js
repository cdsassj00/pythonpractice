/**
 * Viewer for a photogrammetric GLB — the mesh Higgsfield lifted straight out
 * of the aerial render.
 *
 * Its texture already carries the original render's lighting, so the default
 * look is deliberately flat: the base colour is piped through emissive and the
 * sun is dialled to zero, which reproduces the source image exactly. Turning
 * the light up re-shades the relief for inspection.
 */

/**
 * Fit the box in frame from a given direction.
 *
 * A bounding sphere badly over-frames a wide flat slab seen obliquely, so this
 * projects the eight corners and rescales the distance until they fill
 * `margin` of the smaller screen axis. Three passes is plenty to converge.
 */
export function frameCamera(THREE, camera, box, dirLocal, margin = 0.92) {
  const centre = box.getCenter(new THREE.Vector3());
  const radius = box.getSize(new THREE.Vector3()).length() / 2;
  const dir = new THREE.Vector3(...dirLocal).normalize();

  const corners = [];
  for (let i = 0; i < 8; i++) {
    corners.push(new THREE.Vector3(
      i & 1 ? box.max.x : box.min.x,
      i & 2 ? box.max.y : box.min.y,
      i & 4 ? box.max.z : box.min.z
    ));
  }

  let dist = radius * 2.2;
  const p = new THREE.Vector3();
  for (let pass = 0; pass < 3; pass++) {
    camera.position.copy(centre).addScaledVector(dir, dist);
    camera.near = Math.max(dist / 500, 0.001);
    camera.far = dist + radius * 4;
    camera.updateProjectionMatrix();
    camera.lookAt(centre);
    camera.updateMatrixWorld();

    let worst = 0;
    for (const c of corners) {
      p.copy(c).project(camera);
      worst = Math.max(worst, Math.abs(p.x), Math.abs(p.y));
    }
    if (!isFinite(worst) || worst <= 0) break;
    dist *= worst / margin;
  }

  camera.position.copy(centre).addScaledVector(dir, dist);
  camera.near = Math.max(dist / 500, 0.001);
  camera.far = dist + radius * 4;
  camera.updateProjectionMatrix();
  camera.lookAt(centre);
  return { centre, radius, dist };
}

export function createGlbViewer(THREE, GLTFLoader, buffer, canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a1014);

  const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 100);
  const sun = new THREE.DirectionalLight(0xfff4e2, 0.0);
  sun.position.set(0.6, 1.0, 0.5);
  scene.add(sun);
  const ambient = new THREE.AmbientLight(0xffffff, 1.0);
  scene.add(ambient);

  const state = { model: null, materials: [], box: null, centre: null, radius: 1 };

  const loader = new GLTFLoader();
  const ready = new Promise((resolve, reject) => {
    loader.parse(buffer, '', (gltf) => {
      const model = gltf.scene;
      model.traverse((o) => {
        if (!o.isMesh) return;
        const m = o.material;
        m.side = THREE.DoubleSide;
        // baked-in lighting: route colour through emissive so it can be shown
        // unlit, and keep the map for when the light is turned up
        m.emissiveMap = m.map;
        m.emissive = new THREE.Color(0xffffff);
        m.emissiveIntensity = 1.0;
        m.roughness = 0.85;
        m.metalness = 0.0;
        m.needsUpdate = true;
        state.materials.push(m);
      });
      scene.add(model);
      state.model = model;
      state.box = new THREE.Box3().setFromObject(model);
      resolve(model);
    }, reject);
  });

  const resize = () => {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  resize();
  addEventListener('resize', resize);

  let raf = 0;
  const tick = () => {
    renderer.render(scene, camera);
    raf = requestAnimationFrame(tick);
  };
  tick();

  return {
    renderer, scene, camera, sun, ambient, state, ready, resize,
    /** 0 = exactly the source render, 1 = fully re-lit relief */
    setLight(t) {
      for (const m of state.materials) {
        m.emissiveIntensity = 1 - t;
        m.needsUpdate = true;
      }
      sun.intensity = t * 2.6;
      ambient.intensity = 1 - t * 0.75;
    },
    setWireframe(on) {
      for (const m of state.materials) {
        m.wireframe = on;
        m.needsUpdate = true;
      }
    },
    setTexture(on) {
      for (const m of state.materials) {
        m.map = on ? m.emissiveMap : null;
        m.color.set(on ? 0xffffff : 0x9aa8b2);
        m.emissive.set(on ? 0xffffff : 0x000000);
        m.needsUpdate = true;
      }
    },
    stop: () => cancelAnimationFrame(raf),
  };
}
