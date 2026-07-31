"""Dump the layout as compact JSON for the three.js viewer.

Trees are pulled out of the primitive list and emitted as instance transforms,
which keeps the payload small (a few hundred kB instead of megabytes) and lets
the viewer draw 2,400 conifers in two draw calls.

    python3 export_layout_json.py --out web/layout.json
"""

import argparse
import json
import os

import site_layout


def export(include_forest=True):
    prims, trees, seen = [], [], set()
    for p in site_layout.layout(include_forest=include_forest):
        tag = p.get("tree")
        if tag is not None:
            key = (round(tag[0], 3), round(tag[1], 3), round(tag[2], 4))
            if key not in seen:
                seen.add(key)
                trees.append([round(tag[0], 2), round(tag[1], 2), round(tag[2], 3)])
            continue
        item = {"t": p["type"], "m": p["mat"], "p": [round(v, 3) for v in p["pos"]]}
        if p["type"] in ("box", "gable"):
            item["s"] = [round(v, 3) for v in p["size"]]
        else:
            item["r"] = round(p["radius"], 3)
            item["h"] = round(p["height"], 3)
            item["g"] = p.get("seg", 24)
        if p.get("rot"):
            item["a"] = round(p["rot"], 3)
        prims.append(item)

    return {
        "materials": {k: {"c": list(v[0]), "me": v[1], "ro": v[2]}
                      for k, v in site_layout.MATERIALS.items()},
        "camera": site_layout.CAMERA,
        "sun": site_layout.SUN,
        "site": {"w": site_layout.SITE_W, "d": site_layout.SITE_D,
                 "ground": site_layout.GROUND},
        "tree": site_layout.TREE,
        "prims": prims,
        "trees": trees,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="web/layout.json")
    ap.add_argument("--no-forest", action="store_true")
    a = ap.parse_args()
    data = export(include_forest=not a.no_forest)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
    print(f"{len(data['prims'])} primitives + {len(data['trees'])} trees "
          f"-> {a.out} ({os.path.getsize(a.out) / 1024:.0f} kB)")
