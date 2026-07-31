"""Headless preview render of the GLB, for comparing against the reference.

A tiny numpy z-buffer rasteriser — no Blender, no GPU.  It is only meant for
"does the massing line up with the aerial view" checks; use render_blender.py
for a presentable image.

    python3 preview.py --out dist/preview.png
"""

import argparse
import math

import numpy as np
from PIL import Image

import meshlib
import site_layout


def look_at(eye, target, up=(0.0, 0.0, 1.0)):
    eye = np.array(eye, dtype=np.float64)
    f = np.array(target, dtype=np.float64) - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, np.array(up, dtype=np.float64))
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = r, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def render(width, height, include_forest=True, samples=2):
    W, H = width * samples, height * samples
    cam, sun_cfg = site_layout.CAMERA, site_layout.SUN

    view = look_at(cam["location"], cam["target"])
    # 36 mm sensor width -> vertical fov
    fov_y = 2 * math.atan(24.0 / (2 * cam["lens_mm"]))
    fy = (H / 2) / math.tan(fov_y / 2)
    fx = fy

    el = math.radians(sun_cfg["elevation_deg"])
    az = math.radians(sun_cfg["azimuth_deg"])
    sun = np.array([math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)])

    colour = np.zeros((H, W, 3), dtype=np.float32)
    colour[:] = np.array([0.055, 0.075, 0.085], dtype=np.float32)  # dark vignette backdrop
    depth = np.full((H, W), np.inf, dtype=np.float64)

    for prim in site_layout.layout(include_forest=include_forest):
        base_col = np.array(site_layout.MATERIALS[prim["mat"]][0][:3], dtype=np.float64)
        v, n, idx = meshlib.build(prim)
        vh = np.concatenate([v, np.ones((len(v), 1))], axis=1) @ view.T
        tris = idx.reshape(-1, 3)

        for tri in tris:
            p = vh[tri]
            if np.all(p[:, 2] > -1.0):
                continue
            z = -p[:, 2]
            if np.any(z < 0.5):
                continue
            sx = W / 2 + fx * p[:, 0] / z
            sy = H / 2 - fy * p[:, 1] / z

            x0, x1 = int(max(0, np.floor(sx.min()))), int(min(W - 1, np.ceil(sx.max())))
            y0, y1 = int(max(0, np.floor(sy.min()))), int(min(H - 1, np.ceil(sy.max())))
            if x1 < x0 or y1 < y0:
                continue

            nrm = n[tri].mean(axis=0)
            ln = np.linalg.norm(nrm)
            if ln < 1e-9:
                continue
            nrm = nrm / ln
            lam = max(0.0, float(nrm @ sun))
            sky = 0.30 + 0.30 * max(0.0, float(nrm[2]))
            shade = np.clip(base_col * (sky + 0.85 * lam), 0.0, 1.0)

            ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
            px, py = xs + 0.5, ys + 0.5
            d = ((sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0]))
            if abs(d) < 1e-12:
                continue
            w1 = ((px - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (py - sy[0])) / d
            w2 = ((sx[1] - sx[0]) * (py - sy[0]) - (px - sx[0]) * (sy[1] - sy[0])) / d
            w0 = 1.0 - w1 - w2
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not inside.any():
                continue
            zi = 1.0 / np.clip(w0 / z[0] + w1 / z[1] + w2 / z[2], 1e-9, None)
            m = inside & (zi < depth[y0:y1 + 1, x0:x1 + 1])
            if not m.any():
                continue
            depth[y0:y1 + 1, x0:x1 + 1][m] = zi[m]
            colour[y0:y1 + 1, x0:x1 + 1][m] = shade.astype(np.float32)

    # cool aerial-render grade + slight distance haze, matching the reference look
    haze = np.clip((depth - 380.0) / 900.0, 0.0, 0.55)[..., None]
    colour = colour * (1 - haze) + np.array([0.12, 0.16, 0.20], dtype=np.float32) * haze
    colour = np.clip(colour * 1.06, 0, 1) ** (1 / 2.2)

    img = Image.fromarray((colour * 255).astype(np.uint8))
    return img.resize((width, height), Image.LANCZOS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/preview.png")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=854)
    ap.add_argument("--no-forest", action="store_true")
    ap.add_argument("--samples", type=int, default=2)
    a = ap.parse_args()
    render(a.width, a.height, include_forest=not a.no_forest, samples=a.samples).save(a.out)
    print("wrote", a.out)
