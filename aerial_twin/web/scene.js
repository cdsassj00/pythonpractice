/**
 * Builds the aerial-twin scene from the layout JSON exported by
 * export_layout_json.py.  Takes THREE as a parameter so the same module works
 * both with a CDN import map and with an inlined single-file build.
 *
 * Layout space is metres, Z-up.  Everything is parented to a root group that
 * is rotated -90 degrees about X, so three.js sees its usual Y-up world while
 * the layout numbers stay untouched.
 */

import { attachOrbit } from './orbit.js';

export { attachOrbit };

// flat ground cover — receives shadow, never casts it
const GROUND_MATERIALS = new Set(['forest', 'grass', 'lawn', 'pad', 'asphalt', 'paint']);

// layout (x, y, z) -> three.js world
export function toWorld(v) {
  return [v[0], v[2], -v[1]];
}

function gableGeometry(THREE, w, d, h) {
  const hw = w / 2, hd = d / 2;
  const p = [
    [-hw, -hd, 0], [hw, -hd, 0], [hw, hd, 0], [-hw, hd, 0],
    [0, -hd, h], [0, hd, h],
  ];
  const tris = [
    [0, 2, 1], [0, 3, 2], [0, 1, 4], [3, 5, 2],
    [1, 2, 5], [1, 5, 4], [0, 4, 5], [0, 5, 3],
  ];
  const pos = [];
  for (const t of tris) for (const i of t) pos.push(...p[i]);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.computeVertexNormals();
  return g;
}

function makeMaterials(THREE, defs, env) {
  const mats = {};
  for (const [name, d] of Object.entries(defs)) {
    const params = {
      color: new THREE.Color(d.c[0], d.c[1], d.c[2]),
      metalness: d.me,
      roughness: d.ro,
      envMap: env,
      envMapIntensity: 0.9,
    };
    if (name === 'glass') {
      params.roughness = 0.06;
      params.metalness = 0.35;
      params.envMapIntensity = 2.4;
    }
    if (name === 'metal') params.envMapIntensity = 1.4;
    // vegetation and the neighbouring plots must stay matte and dark, or the
    // sky panel washes them out and the campus loses its contrast
    if (['forest', 'conifer', 'grass', 'lawn', 'hedge', 'trunk', 'neighbor'].includes(name)) {
      params.envMapIntensity = 0.22;
    }
    mats[name] = new THREE.MeshStandardMaterial(params);
  }
  return mats;
}

/** A cheap studio environment so metal and glass have something to reflect. */
function buildEnvironment(THREE, renderer) {
  const env = new THREE.Scene();
  const panel = (color, intensity, pos, scale) => {
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity) })
    );
    m.position.set(...pos);
    m.scale.set(...scale);
    m.lookAt(0, 0, 0);
    env.add(m);
  };
  env.background = new THREE.Color(0x0b1016);
  panel(0x9fb6cc, 1.35, [0, 40, 0], [120, 120, 1]);     // sky dome
  panel(0xfff0d8, 3.0, [30, 22, -34], [50, 50, 1]);     // sun side
  panel(0x1c2630, 0.9, [-40, 6, 30], [90, 60, 1]);      // fill
  panel(0x0a120e, 1.0, [0, -30, 0], [140, 140, 1]);     // ground bounce
  const pmrem = new THREE.PMREMGenerator(renderer);
  const target = pmrem.fromScene(env, 0.04);
  pmrem.dispose();
  return target.texture;
}

export function buildScene(THREE, data, renderer) {
  const scene = new THREE.Scene();
  const env = buildEnvironment(THREE, renderer);
  scene.environment = env;
  scene.background = new THREE.Color(0x0d1418);
  scene.fog = new THREE.FogExp2(0x0e161c, 0.00088);

  const mats = makeMaterials(THREE, data.materials, env);

  const root = new THREE.Group();
  root.rotation.x = -Math.PI / 2;   // layout Z-up -> three.js Y-up
  scene.add(root);

  // --- static primitives ---------------------------------------------------
  const boxGeo = new THREE.BoxGeometry(1, 1, 1);
  const cylCache = new Map();
  const cylinder = (seg, cone) => {
    const key = `${seg}:${cone ? 1 : 0}`;
    if (!cylCache.has(key)) {
      const g = cone
        ? new THREE.ConeGeometry(1, 1, seg)
        : new THREE.CylinderGeometry(1, 1, 1, seg);
      g.rotateX(Math.PI / 2);        // axis Y -> Z
      g.translate(0, 0, 0.5);        // base at z = 0
      cylCache.set(key, g);
    }
    return cylCache.get(key);
  };

  for (const item of data.prims) {
    const mat = mats[item.m];
    let mesh;
    if (item.t === 'box') {
      mesh = new THREE.Mesh(boxGeo, mat);
      mesh.scale.set(item.s[0], item.s[1], item.s[2]);
      mesh.position.set(item.p[0], item.p[1], item.p[2] + item.s[2] / 2);
    } else if (item.t === 'gable') {
      mesh = new THREE.Mesh(gableGeometry(THREE, item.s[0], item.s[1], item.s[2]), mat);
      mesh.position.set(item.p[0], item.p[1], item.p[2]);
    } else {
      mesh = new THREE.Mesh(cylinder(item.g, item.t === 'cone'), mat);
      mesh.scale.set(item.r, item.r, item.h);
      mesh.position.set(item.p[0], item.p[1], item.p[2]);
    }
    if (item.a) mesh.rotation.z = (item.a * Math.PI) / 180;
    // Ground slabs only receive. Letting a 1.4 km terrain box cast means its
    // own top face occludes everything sitting on it and the whole site reads
    // as uniformly shadowed.
    mesh.castShadow = !GROUND_MATERIALS.has(item.m);
    mesh.receiveShadow = true;
    root.add(mesh);
  }

  // --- instanced conifers --------------------------------------------------
  const T = data.tree;
  const trunkH = T.height * T.trunk_frac;
  const canopyH = T.height * T.canopy_frac;
  const canopyBase = T.height * T.canopy_base;
  const trunkGeo = new THREE.CylinderGeometry(T.trunk_radius, T.trunk_radius * 1.15, trunkH, 6);
  trunkGeo.rotateX(Math.PI / 2);
  trunkGeo.translate(0, 0, trunkH / 2);
  const canopyGeo = new THREE.ConeGeometry(T.radius, canopyH, 7);
  canopyGeo.rotateX(Math.PI / 2);
  canopyGeo.translate(0, 0, canopyBase + canopyH / 2);

  const forest = new THREE.Group();
  const n = data.trees.length;
  const trunks = new THREE.InstancedMesh(trunkGeo, mats.trunk, n);
  const canopies = new THREE.InstancedMesh(canopyGeo, mats.conifer, n);
  const m4 = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const pos = new THREE.Vector3();
  const scl = new THREE.Vector3();
  data.trees.forEach(([x, y, s], i) => {
    pos.set(x, y, -1.0);
    q.setFromAxisAngle(new THREE.Vector3(0, 0, 1), (i * 2.399) % (Math.PI * 2));
    scl.set(s, s, s);
    m4.compose(pos, q, scl);
    trunks.setMatrixAt(i, m4);
    canopies.setMatrixAt(i, m4);
  });
  trunks.castShadow = canopies.castShadow = true;
  canopies.receiveShadow = true;
  forest.add(trunks, canopies);
  root.add(forest);

  // --- lighting ------------------------------------------------------------
  const sun = new THREE.DirectionalLight(0xfff2dd, data.sun.strength);
  const el = (data.sun.elevation_deg * Math.PI) / 180;
  const az = (data.sun.azimuth_deg * Math.PI) / 180;
  const dir = toWorld([
    Math.cos(el) * Math.sin(az),
    Math.cos(el) * Math.cos(az),
    Math.sin(el),
  ]);
  sun.position.set(dir[0] * 700, dir[1] * 700, dir[2] * 700);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  // Frame the shadow camera on the campus, not the whole terrain: a tight
  // near/far keeps depth precision high enough that no bias hack is needed.
  const s = 330;
  Object.assign(sun.shadow.camera, { left: -s, right: s, top: s, bottom: -s, near: 380, far: 1150 });
  sun.shadow.camera.updateProjectionMatrix();   // Object.assign alone never rebuilds it
  sun.shadow.bias = 0.0;
  sun.shadow.normalBias = 0.8;
  scene.add(sun);
  scene.add(sun.target);

  scene.add(new THREE.HemisphereLight(0x8fa9bf, 0x0d140f, 0.24));
  scene.add(new THREE.AmbientLight(0x2b3a46, 0.06));

  return { scene, root, forest, sun, materials: mats };
}

export function createViewer(THREE, data, canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const built = buildScene(THREE, data, renderer);
  const camera = new THREE.PerspectiveCamera(
    2 * Math.atan(12 / data.camera.lens_mm) * (180 / Math.PI), 1, 1, 6000);
  const camPos = new THREE.Vector3(...toWorld(data.camera.location));
  const camTgt = new THREE.Vector3(...toWorld(data.camera.target));
  camera.position.copy(camPos);
  camera.lookAt(camTgt);

  const orbit = attachOrbit(THREE, camera, canvas, camTgt);

  const resize = () => {
    const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  resize();
  addEventListener('resize', resize);

  let raf = 0;
  const tick = () => {
    renderer.render(built.scene, camera);
    raf = requestAnimationFrame(tick);
  };
  tick();

  return {
    ...built, renderer, camera, orbit, resize,
    home: () => orbit.moveTo(camPos, camTgt),
    stop: () => cancelAnimationFrame(raf),
  };
}
