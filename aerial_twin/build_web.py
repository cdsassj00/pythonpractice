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
    return re.sub(r"^export\s+", "", src, flags=re.MULTILINE)


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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "dist", "viewer.html"))
    ap.add_argument("--dev-only", action="store_true")
    a = ap.parse_args()
    build_dev()
    if not a.dev_only:
        build_artifact(a.out)
