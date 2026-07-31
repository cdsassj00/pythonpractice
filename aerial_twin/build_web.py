"""Assemble the three.js viewer.

Two outputs from one template:

  web/index.html      dev build — three.js from a CDN import map, layout.json
                      fetched at runtime.  Serve with `python3 -m http.server`.
  dist/viewer.html    single self-contained file — three.js, the scene code,
                      the layout and the reference photo are all inlined, so it
                      runs from a file:// path or a strict-CSP host.

    python3 build_web.py                 # both
    python3 build_web.py --dev-only
"""

import argparse
import base64
import json
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
CACHE = os.path.join(HERE, ".cache")
THREE_VERSION = "0.169.0"
THREE_URL = f"https://unpkg.com/three@{THREE_VERSION}/build/three.module.min.js"


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def ensure_three():
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"three-{THREE_VERSION}.module.min.js")
    if not os.path.exists(path):
        print(f"fetching three.js {THREE_VERSION}")
        with urllib.request.urlopen(THREE_URL) as resp, open(path, "wb") as fh:
            fh.write(resp.read())
    return read(path)


def inline_three(src):
    """Turn the ESM build into a plain script that defines a THREE namespace.

    The minified bundle ends in a single `export{mangled as Public, ...}`.
    Dropping that and rebuilding the mapping as an object literal keeps every
    binding reachable without needing module resolution.
    """
    match = re.search(r"export\{([^}]*)\};?\s*$", src)
    if not match:
        raise SystemExit("unexpected three.js build: no trailing export statement")
    pairs = []
    for entry in match.group(1).split(","):
        local, _, exported = entry.partition(" as ")
        exported = (exported or local).strip()
        pairs.append(f'"{exported}":{local.strip()}')
    return src[: match.start()] + "\nconst THREE={" + ",".join(pairs) + "};\n"


def strip_exports(src):
    src = re.sub(r"^import\s*\{[^}]*\}\s*from\s*'\./[^']*';\s*$", "", src, flags=re.MULTILINE)
    src = re.sub(r"^export\s*\{[^}]*\};\s*$", "", src, flags=re.MULTILINE)
    return re.sub(r"^export\s+", "", src, flags=re.MULTILINE)


def inline_example_module(src, exports):
    """Make a three.js examples/jsm module usable without module resolution.

    Its `import {...} from 'three'` becomes a destructure of the inlined THREE
    namespace, relative imports are dropped (their modules are inlined ahead of
    it), and the whole thing is wrapped in an IIFE so the two example modules
    cannot collide over a shared helper name.
    """
    src = re.sub(r"import\s*\{([^}]*)\}\s*from\s*'three';",
                 lambda m: "const {" + m.group(1) + "} = THREE;", src, count=1)
    src = re.sub(r"^import\s*\{[^}]*\}\s*from\s*'[^']*';\s*$", "", src, flags=re.MULTILINE)
    src = re.sub(r"^export\s*\{[^}]*\};\s*$", "", src, flags=re.MULTILINE)
    src = re.sub(r"^export\s+", "", src, flags=re.MULTILINE)
    names = ", ".join(exports)
    return f"const {{ {names} }} = (() => {{\n{src}\nreturn {{ {names} }};\n}})();"


def ensure_example(name, path):
    os.makedirs(CACHE, exist_ok=True)
    local = os.path.join(CACHE, f"{name}-{THREE_VERSION}.js")
    if not os.path.exists(local):
        url = f"https://unpkg.com/three@{THREE_VERSION}/examples/jsm/{path}"
        print(f"fetching {path}")
        with urllib.request.urlopen(url) as resp, open(local, "wb") as fh:
            fh.write(resp.read())
    return read(local)


def data_uri(path, mime):
    with open(path, "rb") as fh:
        return f"data:{mime};base64," + base64.b64encode(fh.read()).decode("ascii")


def build_dev():
    body = read(WEB, "template.html")
    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>조감도 3D 트윈 · Plant Site</title>
<script type="importmap">
{{"imports": {{"three": "{THREE_URL}"}}}}
</script>
</head>
<body>
{body}
<script type="module">
import * as THREE from 'three';
import * as scene from './scene.js';
import {{ start }} from './app.js';
const data = await fetch('layout.json').then((r) => r.json());
window.__viewer = start(THREE, scene, data, '../ref/reference.jpg');
</script>
</body>
</html>
"""
    out = os.path.join(WEB, "index.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"wrote {out}")


def build_artifact(out):
    data = json.loads(read(WEB, "layout.json"))
    ref_path = os.path.join(HERE, "ref", "reference.jpg")
    ref = data_uri(ref_path, "image/jpeg") if os.path.exists(ref_path) else ""

    parts = [
        read(WEB, "template.html"),
        '<script type="module">',
        inline_three(ensure_three()),
        strip_exports(read(WEB, "orbit.js")),
        strip_exports(read(WEB, "scene.js")),
        "const scene={buildScene,attachOrbit,createViewer,toWorld};",
        strip_exports(read(WEB, "app.js")),
        "const data=" + json.dumps(data, separators=(",", ":")) + ";",
        f"const referenceSrc={json.dumps(ref)};",
        "window.__viewer = start(THREE, scene, data, referenceSrc);",
        "</script>",
    ]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print(f"wrote {out} ({os.path.getsize(out) / 1e6:.2f} MB)")


def build_glb_viewer(model_path, out):
    """Single-file viewer for a textured GLB — the mesh is inlined as base64."""
    with open(model_path, "rb") as fh:
        model_b64 = base64.b64encode(fh.read()).decode("ascii")
    ref_path = os.path.join(HERE, "ref", "reference.jpg")
    ref = data_uri(ref_path, "image/jpeg") if os.path.exists(ref_path) else ""

    decode = (
        "const b64=MODEL_B64;"
        "const bin=atob(b64);"
        "const buf=new Uint8Array(bin.length);"
        "for(let i=0;i<bin.length;i++)buf[i]=bin.charCodeAt(i);"
    )

    parts = [
        read(WEB, "glb_template.html"),
        '<script type="module">',
        inline_three(ensure_three()),
        inline_example_module(
            ensure_example("BufferGeometryUtils", "utils/BufferGeometryUtils.js"),
            ["toTrianglesDrawMode"]),
        inline_example_module(
            ensure_example("GLTFLoader", "loaders/GLTFLoader.js"), ["GLTFLoader"]),
        strip_exports(read(WEB, "orbit.js")),
        strip_exports(read(WEB, "glb_scene.js")),
        strip_exports(read(WEB, "glb_app.js")),
        "const MODEL_B64=" + json.dumps(model_b64) + ";",
        decode,
        f"const referenceSrc={json.dumps(ref)};",
        "window.__viewer = await startGlb(THREE, GLTFLoader, buf.buffer, referenceSrc);",
        "</script>",
    ]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print(f"wrote {out} ({os.path.getsize(out) / 1e6:.2f} MB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "dist", "viewer.html"))
    ap.add_argument("--glb-model", default=os.path.join(HERE, "dist",
                                                       "higgsfield_image_to_3d_web.glb"))
    ap.add_argument("--glb-out", default=os.path.join(HERE, "dist", "mesh_viewer.html"))
    ap.add_argument("--dev-only", action="store_true")
    a = ap.parse_args()
    build_dev()
    if not a.dev_only:
        build_artifact(a.out)
        if os.path.exists(a.glb_model):
            build_glb_viewer(a.glb_model, a.glb_out)
