"""Primitive -> triangle soup helpers.

Model space is Z-up, metres, +X east / +Y north.  glTF export converts to its
Y-up convention at write time; nothing here needs to know about that.
"""

import math

import numpy as np


def _rotz(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _place(verts, normals, pos, rot):
    if rot:
        m = _rotz(rot)
        verts = verts @ m.T
        normals = normals @ m.T
    return verts + np.asarray(pos, dtype=np.float64), normals


# --- primitives -------------------------------------------------------------

_BOX_FACES = (
    # (normal, four corners as (sx, sy, sz) signs in unit box space)
    ((0, 0, 1), ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))),
    ((0, 0, -1), ((-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1))),
    ((0, -1, 0), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))),
    ((0, 1, 0), ((1, 1, -1), (-1, 1, -1), (-1, 1, 1), (1, 1, 1))),
    ((-1, 0, 0), ((-1, 1, -1), (-1, -1, -1), (-1, -1, 1), (-1, 1, 1))),
    ((1, 0, 0), ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1))),
)


def box(pos, size, rot=0.0):
    """Axis box whose *pos* is the centre of its footprint, sitting on pos.z."""
    w, d, h = (v / 2.0 for v in size)
    verts, normals, idx = [], [], []
    for n, corners in _BOX_FACES:
        base = len(verts)
        for sx, sy, sz in corners:
            verts.append((sx * w, sy * d, sz * h))
            normals.append(n)
        idx += [base, base + 1, base + 2, base, base + 2, base + 3]
    verts = np.array(verts, dtype=np.float64)
    normals = np.array(normals, dtype=np.float64)
    # lift so the box rests on pos.z rather than straddling it
    verts[:, 2] += h
    verts, normals = _place(verts, normals, pos, rot)
    return verts, normals, np.array(idx, dtype=np.uint32)


def cylinder(pos, radius, height, seg=24, rot=0.0, top_radius=None):
    top_radius = radius if top_radius is None else top_radius
    verts, normals, idx = [], [], []
    ring = [(math.cos(2 * math.pi * i / seg), math.sin(2 * math.pi * i / seg)) for i in range(seg)]

    for i in range(seg):
        c0, s0 = ring[i]
        c1, s1 = ring[(i + 1) % seg]
        base = len(verts)
        verts += [
            (c0 * radius, s0 * radius, 0.0),
            (c1 * radius, s1 * radius, 0.0),
            (c1 * top_radius, s1 * top_radius, height),
            (c0 * top_radius, s0 * top_radius, height),
        ]
        # slanted side normal (correct for cones as well as cylinders)
        dr = radius - top_radius
        nz = dr / math.hypot(dr, height) if height else 1.0
        nr = height / math.hypot(dr, height) if height else 0.0
        normals += [
            (c0 * nr, s0 * nr, nz),
            (c1 * nr, s1 * nr, nz),
            (c1 * nr, s1 * nr, nz),
            (c0 * nr, s0 * nr, nz),
        ]
        idx += [base, base + 1, base + 2, base, base + 2, base + 3]

    for z, r, n, flip in ((0.0, radius, (0, 0, -1), True), (height, top_radius, (0, 0, 1), False)):
        if r <= 1e-6:
            continue
        centre = len(verts)
        verts.append((0.0, 0.0, z))
        normals.append(n)
        for c, s in ring:
            verts.append((c * r, s * r, z))
            normals.append(n)
        for i in range(seg):
            a, b = centre + 1 + i, centre + 1 + (i + 1) % seg
            idx += [centre, b, a] if flip else [centre, a, b]

    verts = np.array(verts, dtype=np.float64)
    normals = np.array(normals, dtype=np.float64)
    verts, normals = _place(verts, normals, pos, rot)
    return verts, normals, np.array(idx, dtype=np.uint32)


def cone(pos, radius, height, seg=8, rot=0.0):
    return cylinder(pos, radius, height, seg=seg, rot=rot, top_radius=0.0)


def gable(pos, size, rot=0.0, ridge_ratio=0.0):
    """Prism with a pitched roof: *size* is (width, depth, ridge height).

    ridge_ratio 0.0 puts the ridge at the centre; the roof runs along +Y.
    """
    w, d, h = size[0] / 2.0, size[1] / 2.0, size[2]
    rx = ridge_ratio * w
    p = [
        (-w, -d, 0.0), (w, -d, 0.0), (w, d, 0.0), (-w, d, 0.0),  # 0-3 floor
        (rx, -d, h), (rx, d, h),                                  # 4-5 ridge
    ]
    tris = [
        (0, 2, 1), (0, 3, 2),           # floor
        (0, 1, 4),                      # front gable
        (3, 5, 2),                      # back gable
        (1, 2, 5), (1, 5, 4),           # +X pitch
        (0, 4, 5), (0, 5, 3),           # -X pitch
    ]
    verts, normals, idx = [], [], []
    for tri in tris:
        a, b, c = (np.array(p[i], dtype=np.float64) for i in tri)
        n = np.cross(b - a, c - a)
        ln = np.linalg.norm(n)
        n = n / ln if ln else np.array([0.0, 0.0, 1.0])
        base = len(verts)
        verts += [a, b, c]
        normals += [n, n, n]
        idx += [base, base + 1, base + 2]
    verts = np.array(verts, dtype=np.float64)
    normals = np.array(normals, dtype=np.float64)
    verts, normals = _place(verts, normals, pos, rot)
    return verts, normals, np.array(idx, dtype=np.uint32)


BUILDERS = {"box": box, "cyl": cylinder, "cone": cone, "gable": gable}

# keys that describe the primitive rather than its geometry
_META_KEYS = frozenset(("type", "mat", "name", "tree"))


def build(prim):
    """Turn a layout dict into (verts, normals, indices)."""
    kind = prim["type"]
    args = {k: v for k, v in prim.items() if k not in _META_KEYS}
    return BUILDERS[kind](**args)
