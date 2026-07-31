/** Wires the instrument panel to the viewer. */

export function start(THREE, scene, data, referenceSrc) {
  const $ = (id) => document.getElementById(id);
  const viewer = scene.createViewer(THREE, data, $('view'));
  const { toWorld } = scene;

  // --- readout -------------------------------------------------------------
  let tris = 0;
  viewer.scene.traverse((o) => {
    if (!o.isMesh) return;
    const index = o.geometry.index;
    const count = index ? index.count : o.geometry.attributes.position.count;
    tris += (count / 3) * (o.isInstancedMesh ? o.count : 1);
  });
  const fmt = (n) => n.toLocaleString('en-US');
  $('r-prims').textContent = fmt(data.prims.length);
  $('r-trees').textContent = fmt(data.trees.length);
  $('r-tris').textContent = fmt(Math.round(tris));
  $('subtitle').textContent =
    `부지 ${data.site.w} × ${data.site.d} m · 실시간 재구성 · ${fmt(data.prims.length + data.trees.length)} 오브젝트`;

  // --- view presets --------------------------------------------------------
  const home = {
    position: new THREE.Vector3(...toWorld(data.camera.location)),
    target: new THREE.Vector3(...toWorld(data.camera.target)),
  };
  const presets = {
    aerial: home,
    south: {
      position: new THREE.Vector3(...toWorld([10, -560, 120])),
      target: new THREE.Vector3(...toWorld([10, 20, 26])),
    },
    plan: {
      position: new THREE.Vector3(...toWorld([0, 2, 720])),
      target: new THREE.Vector3(...toWorld([0, 2, 0])),
    },
  };
  const buttons = [...$('views').querySelectorAll('button')];
  let currentView = 'aerial';
  buttons.forEach((b) => {
    b.addEventListener('click', () => {
      currentView = b.dataset.view;
      buttons.forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
      const p = presets[currentView];
      viewer.orbit.moveTo(p.position, p.target);
      syncOverlay();
    });
  });

  // --- sun -----------------------------------------------------------------
  const placeSun = () => {
    const el = (+$('elev').value * Math.PI) / 180;
    const az = (+$('azim').value * Math.PI) / 180;
    const d = toWorld([
      Math.cos(el) * Math.sin(az),
      Math.cos(el) * Math.cos(az),
      Math.sin(el),
    ]);
    viewer.sun.position.set(d[0] * 700, d[1] * 700, d[2] * 700);
    // warmer and weaker as the sun drops, the way the reference render sits
    const t = Math.max(0, Math.min(1, (+$('elev').value - 6) / 60));
    viewer.sun.intensity = data.sun.strength * (0.35 + 0.65 * t);
    viewer.sun.color.setHSL(0.09 - 0.03 * t, 0.55 - 0.4 * t, 0.62 + 0.1 * t);
    $('elev-out').textContent = `${$('elev').value}°`;
    $('azim-out').textContent = `${$('azim').value}°`;
  };
  $('elev').addEventListener('input', placeSun);
  $('azim').addEventListener('input', placeSun);
  placeSun();

  $('expo').addEventListener('input', (e) => {
    viewer.renderer.toneMappingExposure = +e.target.value;
    $('expo-out').textContent = (+e.target.value).toFixed(2);
  });

  // --- display toggles -----------------------------------------------------
  $('t-forest').addEventListener('change', (e) => {
    viewer.forest.visible = e.target.checked;
  });
  $('t-shadow').addEventListener('change', (e) => {
    viewer.renderer.shadowMap.enabled = e.target.checked;
    viewer.scene.traverse((o) => {
      if (o.isMesh) o.material.needsUpdate = true;
    });
  });
  const fog = viewer.scene.fog;
  $('t-fog').addEventListener('change', (e) => {
    viewer.scene.fog = e.target.checked ? fog : null;
    viewer.scene.traverse((o) => {
      if (o.isMesh) o.material.needsUpdate = true;
    });
  });

  // --- reference overlay ---------------------------------------------------
  const img = $('overlay-img');
  const syncOverlay = () => {
    if (!referenceSrc) return;
    img.style.opacity = currentView === 'aerial' ? +$('ref').value / 100 : 0;
  };
  if (referenceSrc) {
    img.src = referenceSrc;
    $('ref-group').hidden = false;
    $('ref').addEventListener('input', () => {
      $('ref-out').textContent = `${$('ref').value}%`;
      syncOverlay();
    });
  }

  // any manual camera move drops the overlay back out of the way
  $('view').addEventListener('pointerdown', () => {
    if (currentView === 'aerial' && referenceSrc) img.style.opacity = 0;
  });
  $('view').addEventListener('pointerup', syncOverlay);

  requestAnimationFrame(() => {
    const l = $('loading');
    l.style.opacity = '0';
    setTimeout(() => { l.hidden = true; }, 500);
  });

  return viewer;
}
