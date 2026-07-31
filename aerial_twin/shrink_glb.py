"""Re-encode a GLB's embedded textures so the model can be inlined in a page.

The Higgsfield mesh ships a 2048x2048 JPEG that is 4.5 MB of the 6.2 MB file.
At the scale this model is viewed the extra resolution buys nothing, so this
resamples every embedded image and rewrites the buffer.

    python3 shrink_glb.py dist/higgsfield_image_to_3d.glb --size 1024 --quality 82
"""

import argparse
import io
import os

from PIL import Image
from pygltflib import GLTF2


def shrink(path, out, size, quality):
    gltf = GLTF2().load(path)
    blob = bytearray(gltf.binary_blob())

    # rebuild the buffer so replaced images do not leave holes
    pieces = []          # (bufferView index, bytes)
    replaced = {}
    for i, image in enumerate(gltf.images):
        if image.bufferView is None:
            continue
        bv = gltf.bufferViews[image.bufferView]
        start = bv.byteOffset or 0
        raw = bytes(blob[start:start + bv.byteLength])
        pil = Image.open(io.BytesIO(raw)).convert("RGB")
        if max(pil.size) > size:
            pil = pil.resize((size, size), Image.LANCZOS)
        out_buf = io.BytesIO()
        pil.save(out_buf, format="JPEG", quality=quality, optimize=True, progressive=True)
        replaced[image.bufferView] = out_buf.getvalue()
        image.mimeType = "image/jpeg"
        print(f"  image{i}: {bv.byteLength / 1e6:.2f} MB -> "
              f"{len(replaced[image.bufferView]) / 1e6:.2f} MB ({pil.size[0]}px)")

    new_blob = bytearray()
    for idx, bv in enumerate(gltf.bufferViews):
        data = replaced.get(idx)
        if data is None:
            start = bv.byteOffset or 0
            data = bytes(blob[start:start + bv.byteLength])
        pad = (-len(new_blob)) % 4
        new_blob += b"\x00" * pad
        bv.byteOffset = len(new_blob)
        bv.byteLength = len(data)
        new_blob += data
        pieces.append(idx)

    gltf.buffers[0].byteLength = len(new_blob)
    gltf.set_binary_blob(bytes(new_blob))
    gltf.save_binary(out)
    print(f"{os.path.getsize(path) / 1e6:.2f} MB -> {os.path.getsize(out) / 1e6:.2f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--quality", type=int, default=82)
    a = ap.parse_args()
    out = a.out or a.path.replace(".glb", "_web.glb")
    shrink(a.path, out, a.size, a.quality)
