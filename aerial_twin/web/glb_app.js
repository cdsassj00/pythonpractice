/** Wires the panel to the GLB viewer. */

import { attachOrbit } from './orbit.js';
import { createGlbViewer, frameCamera } from './glb_scene.js';

export async function startGlb(THREE, GLTFLoader, buffer, referenceSrc) {
  const $ = (id) => document.getElementById(id);
  const viewer = createGlbViewer(THREE, GLTFLoader, buffer, $('view'));
  await viewer.ready;

  const box = viewer.state.box;
  // The relief faces the camera the source render was made from: looking back
  // down +Z with a slight lift reproduces the original framing.
  const VIEWS = {
    source: [0.0, 0.56, 1.0],
    oblique: [-0.85, 0.75, 0.95],
    plan: [0.0, 1.0, 0.001],
  };

  const apply = (name) => {
    const { centre } = frameCamera(THREE, viewer.camera, box, VIEWS[name], 0.9);
    orbit.moveTo(viewer.camera.position.clone(), centre);
  };

  const { centre } = frameCamera(THREE, viewer.camera, box, VIEWS.source, 0.9);
  const orbit = attachOrbit(THREE, viewer.camera, $('view'), centre);

  const buttons = [...$('views').querySelectorAll('button')];
  let currentView = 'source';
  buttons.forEach((b) => {
    b.addEventListener('click', () => {
      currentView = b.dataset.view;
      buttons.forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
      apply(currentView);
      syncOverlay();
    });
  });

  // --- readout -------------------------------------------------------------
  let verts = 0;
  let tris = 0;
  let texSize = '—';
  viewer.state.model.traverse((o) => {
    if (!o.isMesh) return;
    const g = o.geometry;
    verts += g.attributes.position.count;
    tris += (g.index ? g.index.count : g.attributes.position.count) / 3;
    const img = o.material.emissiveMap?.image;
    if (img) texSize = `${img.width}²`;
  });
  const fmt = (n) => Math.round(n).toLocaleString('en-US');
  $('r-verts').textContent = fmt(verts);
  $('r-tris').textContent = fmt(tris);
  $('r-tex').textContent = texSize;
  $('subtitle').textContent = `image_to_3d · ${fmt(tris)} 삼각형 · 텍스처 ${texSize}`;

  // --- controls ------------------------------------------------------------
  $('light').addEventListener('input', (e) => {
    const t = +e.target.value / 100;
    viewer.setLight(t);
    $('light-out').textContent = `${e.target.value}%`;
  });
  viewer.setLight(0);

  $('t-wire').addEventListener('change', (e) => viewer.setWireframe(e.target.checked));
  $('t-tex').addEventListener('change', (e) => viewer.setTexture(e.target.checked));

  const img = $('overlay-img');
  const syncOverlay = () => {
    if (!referenceSrc) return;
    img.style.opacity = currentView === 'source' ? +$('ref').value / 100 : 0;
  };
  if (referenceSrc) {
    img.src = referenceSrc;
    $('ref-group').hidden = false;
    $('ref').addEventListener('input', () => {
      $('ref-out').textContent = `${$('ref').value}%`;
      syncOverlay();
    });
  }

  const l = $('loading');
  l.style.opacity = '0';
  setTimeout(() => { l.hidden = true; }, 500);

  return viewer;
}
