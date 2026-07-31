"""Bake the site layout straight to .glb / .gltf — no Blender required.

    python3 build_glb.py                      # -> dist/plant_site.glb
    python3 build_glb.py --gltf               # also write .gltf + .bin
    python3 build_glb.py --no-forest          # campus only, much lighter file

One glTF primitive is emitted per material, so the result stays a single mesh
node that any viewer (three.js, model-viewer, Blender, Unreal, Higgsfield)
loads without post-processing.
"""

import argparse
import os
import struct

import numpy as np
from pygltflib import (
    GLTF2, Accessor, Asset, Buffer, BufferView, Material, Mesh, Node,
    PbrMetallicRoughness, Primitive, Scene,
)

import meshlib
import site_layout

ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963
FLOAT = 5126
UNSIGNED_INT = 5125


def collect(prims):
    """Merge every primitive into one vertex/index pool per material."""
    pools = {}
    for prim in prims:
        v, n, i = meshlib.build(prim)
        pool = pools.setdefault(prim["mat"], {"v": [], "n": [], "i": [], "base": 0})
        pool["i"].append(i + pool["base"])
        pool["v"].append(v)
        pool["n"].append(n)
        pool["base"] += len(v)
    out = {}
    for mat, pool in pools.items():
        verts = np.concatenate(pool["v"]).astype(np.float32)
        norms = np.concatenate(pool["n"]).astype(np.float32)
        idx = np.concatenate(pool["i"]).astype(np.uint32)
        # model space is Z-up; glTF is Y-up with -Z forward
        verts = np.stack([verts[:, 0], verts[:, 2], -verts[:, 1]], axis=1)
        norms = np.stack([norms[:, 0], norms[:, 2], -norms[:, 1]], axis=1)
        out[mat] = (np.ascontiguousarray(verts), np.ascontiguousarray(norms), idx)
    return out


def _pad4(blob):
    return blob + b"\x00" * (-len(blob) % 4)


def build_gltf(pools):
    gltf = GLTF2(asset=Asset(version="2.0", generator="aerial_twin/build_glb.py"))
    blob = bytearray()
    primitives = []

    for mat_name, (verts, norms, idx) in sorted(pools.items()):
        color, metallic, roughness = site_layout.MATERIALS[mat_name]
        gltf.materials.append(Material(
            name=mat_name,
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorFactor=list(color),
                metallicFactor=metallic,
                roughnessFactor=roughness,
            ),
            doubleSided=False,
        ))
        mat_index = len(gltf.materials) - 1

        acc_ids = {}
        for key, data, target, comp, atype in (
            ("POSITION", verts, ARRAY_BUFFER, FLOAT, "VEC3"),
            ("NORMAL", norms, ARRAY_BUFFER, FLOAT, "VEC3"),
            ("INDICES", idx, ELEMENT_ARRAY_BUFFER, UNSIGNED_INT, "SCALAR"),
        ):
            raw = _pad4(data.tobytes())
            offset = len(blob)
            blob += raw
            gltf.bufferViews.append(BufferView(
                buffer=0, byteOffset=offset, byteLength=data.nbytes, target=target))
            accessor = Accessor(
                bufferView=len(gltf.bufferViews) - 1,
                componentType=comp,
                count=int(data.shape[0]),
                type=atype,
            )
            if key == "POSITION":
                accessor.min = verts.min(axis=0).tolist()
                accessor.max = verts.max(axis=0).tolist()
            gltf.accessors.append(accessor)
            acc_ids[key] = len(gltf.accessors) - 1

        primitives.append(Primitive(
            attributes={"POSITION": acc_ids["POSITION"], "NORMAL": acc_ids["NORMAL"]},
            indices=acc_ids["INDICES"],
            material=mat_index,
        ))

    gltf.meshes.append(Mesh(name="plant_site", primitives=primitives))
    gltf.nodes.append(Node(name="plant_site", mesh=0))
    gltf.scenes.append(Scene(name="Scene", nodes=[0]))
    gltf.scene = 0
    gltf.buffers.append(Buffer(byteLength=len(blob)))
    gltf.set_binary_blob(bytes(blob))
    return gltf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/plant_site.glb")
    ap.add_argument("--gltf", action="store_true", help="also write .gltf + external .bin")
    ap.add_argument("--no-forest", action="store_true", help="skip the surrounding tree belt")
    args = ap.parse_args()

    prims = site_layout.layout(include_forest=not args.no_forest)
    pools = collect(prims)

    tris = sum(len(i) // 3 for _, _, i in pools.values())
    verts = sum(len(v) for v, _, _ in pools.values())
    print(f"{len(prims)} primitives -> {verts:,} vertices / {tris:,} triangles "
          f"in {len(pools)} materials")

    gltf = build_gltf(pools)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    gltf.save_binary(args.out)
    print(f"wrote {args.out} ({os.path.getsize(args.out) / 1e6:.2f} MB)")

    if args.gltf:
        gltf_path = os.path.splitext(args.out)[0] + ".gltf"
        gltf.save_json(gltf_path)
        print(f"wrote {gltf_path}")


if __name__ == "__main__":
    main()
