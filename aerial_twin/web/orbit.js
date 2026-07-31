/**
 * Minimal orbit controller shared by both viewers — drag to orbit, wheel to
 * dolly, right-drag to pan. Kept out of the scene modules so the GLB viewer
 * does not have to pull in the parametric layout.
 */

/** Minimal orbit controller — drag to orbit, wheel to dolly, right-drag to pan. */
export function attachOrbit(THREE, camera, dom, target) {
  const state = {
    target: target.clone(),
    radius: camera.position.distanceTo(target),
    theta: 0,
    phi: 0,
    dragging: null,
  };
  const off = camera.position.clone().sub(target);
  state.radius = off.length();
  state.theta = Math.atan2(off.x, off.z);
  state.phi = Math.acos(THREE.MathUtils.clamp(off.y / state.radius, -1, 1));

  const apply = () => {
    const sinPhi = Math.sin(state.phi);
    camera.position.set(
      state.target.x + state.radius * sinPhi * Math.sin(state.theta),
      state.target.y + state.radius * Math.cos(state.phi),
      state.target.z + state.radius * sinPhi * Math.cos(state.theta)
    );
    camera.lookAt(state.target);
  };

  let px = 0, py = 0;
  dom.addEventListener('pointerdown', (e) => {
    state.dragging = e.button === 2 ? 'pan' : 'orbit';
    px = e.clientX; py = e.clientY;
    dom.setPointerCapture(e.pointerId);
  });
  dom.addEventListener('pointerup', (e) => {
    state.dragging = null;
    dom.releasePointerCapture(e.pointerId);
  });
  dom.addEventListener('contextmenu', (e) => e.preventDefault());
  dom.addEventListener('pointermove', (e) => {
    if (!state.dragging) return;
    const dx = e.clientX - px, dy = e.clientY - py;
    px = e.clientX; py = e.clientY;
    if (state.dragging === 'orbit') {
      state.theta -= dx * 0.005;
      state.phi = THREE.MathUtils.clamp(state.phi - dy * 0.005, 0.06, Math.PI / 2 - 0.02);
    } else {
      const scale = state.radius * 0.0016;
      const right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0);
      const up = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
      state.target.addScaledVector(right, -dx * scale);
      state.target.addScaledVector(up, dy * scale);
    }
    apply();
  });
  dom.addEventListener('wheel', (e) => {
    e.preventDefault();
    state.radius = THREE.MathUtils.clamp(state.radius * (1 + Math.sign(e.deltaY) * 0.09), 60, 3000);
    apply();
  }, { passive: false });

  apply();
  return {
    state,
    apply,
    moveTo(position, lookAt) {
      state.target.copy(lookAt);
      const o = position.clone().sub(lookAt);
      state.radius = o.length();
      state.theta = Math.atan2(o.x, o.z);
      state.phi = Math.acos(THREE.MathUtils.clamp(o.y / state.radius, -1, 1));
      apply();
    },
  };
}
