"""Render any .glb with the software rasteriser, auto-framing the model.

Handy for eyeballing meshes that did not come from site_layout.py — e.g. the
Higgsfield image_to_3d output.

    python3 glb_preview.py dist/higgsfield_image_to_3d.glb --out dist/hf.png
"""

import argparse
import math

import numpy as np
from PIL import Image
from pygltflib import GLTF2

import preview as sw

_DTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16,
          5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def read_accessor(gltf, blob, index):
    acc = gltf.accessors[index]
    bv = gltf.bufferViews[acc.bufferView]
    dtype = _DTYPE[acc.componentType]
    ncomp = _NCOMP[acc.type]
    start = (bv.byteOffset or 0) + (acc.byteOffset or 0)
    stride = bv.byteStride or np.dtype(dtype).itemsize * ncomp
    natural = np.dtype(dtype).itemsize * ncomp
    if stride == natural:
        data = np.frombuffer(blob, dtype=dtype, count=acc.count * ncomp, offset=start)
        return data.reshape(acc.count, ncomp)
    rows = np.frombuffer(blob, dtype=np.uint8, count=acc.count * stride, offset=start)
    rows = rows.reshape(acc.count, stride)[:, :natural].copy()
    return rows.view(dtype).reshape(acc.count, ncomp)


def load(path):
    gltf = GLTF2().load(path)
    blob = gltf.binary_blob()
    tris = []
    for mesh in gltf.meshes:
        for prim in mesh.primitives:
            pos = read_accessor(gltf, blob, prim.attributes.POSITION).astype(np.float64)
            if prim.indices is None:
                idx = np.arange(len(pos), dtype=np.uint32)
            else:
                idx = read_accessor(gltf, blob, prim.indices).ravel().astype(np.uint32)
            if prim.attributes.NORMAL is not None:
                nrm = read_accessor(gltf, blob, prim.attributes.NORMAL).astype(np.float64)
            else:
                nrm = None
            tris.append((pos, nrm, idx.reshape(-1, 3)))
    return tris


def render(path, width, height, samples=2, elev=38.0, azim=225.0):
    parts = load(path)
    allpos = np.concatenate([p for p, _, _ in parts])
    centre = (allpos.min(axis=0) + allpos.max(axis=0)) / 2.0
    radius = float(np.linalg.norm(allpos.max(axis=0) - allpos.min(axis=0))) / 2.0

    e, a = math.radians(elev), math.radians(azim)
    eye = centre + radius * 2.6 * np.array(
        [math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)])
    # glTF is Y-up; treat its Y as our Z so the site lies flat under the camera
    view = sw.look_at(eye, centre, up=(0.0, 0.0, 1.0))

    W, H = width * samples, height * samples
    fy = (H / 2) / math.tan(math.radians(22.0))
    fx = fy
    sun = np.array([math.cos(math.radians(45)) * math.sin(math.radians(130)),
                    math.cos(math.radians(45)) * math.cos(math.radians(130)),
                    math.sin(math.radians(45))])

    colour = np.full((H, W, 3), 0.06, dtype=np.float32)
    depth = np.full((H, W), np.inf)

    for pos, nrm, tris in parts:
        # glTF Y-up -> our Z-up
        p3 = np.stack([pos[:, 0], -pos[:, 2], pos[:, 1]], axis=1)
        vh = np.concatenate([p3, np.ones((len(p3), 1))], axis=1) @ view.T
        for tri in tris:
            q = vh[tri]
            z = -q[:, 2]
            if np.any(z < 1e-3):
                continue
            sx = W / 2 + fx * q[:, 0] / z
            sy = H / 2 - fy * q[:, 1] / z
            x0, x1 = int(max(0, np.floor(sx.min()))), int(min(W - 1, np.ceil(sx.max())))
            y0, y1 = int(max(0, np.floor(sy.min()))), int(min(H - 1, np.ceil(sy.max())))
            if x1 < x0 or y1 < y0:
                continue
            a3 = p3[tri]
            n = np.cross(a3[1] - a3[0], a3[2] - a3[0])
            ln = np.linalg.norm(n)
            if ln < 1e-12:
                continue
            n /= ln
            shade = 0.28 + 0.72 * abs(float(n @ sun))
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
            colour[y0:y1 + 1, x0:x1 + 1][m] = np.float32(shade * 0.82)

    img = Image.fromarray((np.clip(colour, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))
    return img.resize((width, height), Image.LANCZOS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", default="dist/glb_preview.png")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=640)
    ap.add_argument("--elev", type=float, default=38.0)
    ap.add_argument("--azim", type=float, default=225.0)
    a = ap.parse_args()
    render(a.path, a.width, a.height, elev=a.elev, azim=a.azim).save(a.out)
    print("wrote", a.out)
