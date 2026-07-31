"""Rebuild the same layout inside Blender, then render and/or export GLB.

Run headless:

    blender --background --python build_blender.py -- --glb dist/plant_site_blender.glb
    blender --background --python build_blender.py -- --render dist/render.png --res 1920 1280

Or open Blender, load this file in the Scripting workspace and press Run — the
scene is built with real Cycles materials and the aerial camera already framed,
so it is the file to hand-tune when you want to push the match further.
"""

import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import site_layout  # noqa: E402


def argv():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(flag, default=None):
    a = argv()
    return a[a.index(flag) + 1] if flag in a else default


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def make_materials():
    mats = {}
    for name, (color, metallic, roughness) in site_layout.MATERIALS.items():
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if name == "glass":
            bsdf.inputs["Roughness"].default_value = 0.08
        mats[name] = mat
    return mats


def add_primitive(prim, mats):
    kind, pos = prim["type"], prim["pos"]
    if kind == "box":
        w, d, h = prim["size"]
        bpy.ops.mesh.primitive_cube_add(size=1, location=(pos[0], pos[1], pos[2] + h / 2))
        obj = bpy.context.active_object
        obj.scale = (w, d, h)
    elif kind == "cyl":
        h = prim["height"]
        bpy.ops.mesh.primitive_cylinder_add(
            radius=prim["radius"], depth=h, vertices=prim.get("seg", 24),
            location=(pos[0], pos[1], pos[2] + h / 2))
        obj = bpy.context.active_object
    elif kind == "cone":
        h = prim["height"]
        bpy.ops.mesh.primitive_cone_add(
            radius1=prim["radius"], radius2=0.0, depth=h, vertices=prim.get("seg", 8),
            location=(pos[0], pos[1], pos[2] + h / 2))
        obj = bpy.context.active_object
    elif kind == "gable":
        # a cube squashed into a ridge: build from a cone with 4 sides instead
        w, d, h = prim["size"]
        bpy.ops.mesh.primitive_cube_add(size=1, location=(pos[0], pos[1], pos[2] + h / 2))
        obj = bpy.context.active_object
        obj.scale = (w, d, h)
        mesh = obj.data
        top = sorted(mesh.vertices, key=lambda v: -v.co.z)[:4]
        for v in top:
            v.co.x = 0.0
    else:
        raise ValueError(kind)

    obj.name = prim.get("name", kind)
    if prim.get("rot"):
        obj.rotation_euler[2] = math.radians(prim["rot"])
    obj.data.materials.append(mats[prim["mat"]])
    return obj


def setup_camera_and_light():
    cam_cfg, sun_cfg = site_layout.CAMERA, site_layout.SUN

    cam_data = bpy.data.cameras.new("AerialCam")
    cam_data.lens = cam_cfg["lens_mm"]
    cam = bpy.data.objects.new("AerialCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = Vector(cam_cfg["location"])
    direction = Vector(cam_cfg["target"]) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    sun_data = bpy.data.lights.new("Sun", type="SUN")
    sun_data.energy = sun_cfg["strength"]
    sun_data.angle = math.radians(1.5)
    sun = bpy.data.objects.new("Sun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    el, az = math.radians(sun_cfg["elevation_deg"]), math.radians(sun_cfg["azimuth_deg"])
    sun.rotation_euler = Vector((
        math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)
    )).to_track_quat("Z", "Y").to_euler()

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.07, 0.09, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.1


def build(include_forest=True):
    clear_scene()
    mats = make_materials()
    groups = {}
    for prim in site_layout.layout(include_forest=include_forest):
        obj = add_primitive(prim, mats)
        key = prim.get("name", "misc").split("_")[0]
        groups.setdefault(key, []).append(obj)
    setup_camera_and_light()
    print(f"built {sum(len(v) for v in groups.values())} objects")


def main():
    a = argv()
    build(include_forest="--no-forest" not in a)

    glb = opt("--glb")
    if glb:
        os.makedirs(os.path.dirname(os.path.abspath(glb)), exist_ok=True)
        bpy.ops.export_scene.gltf(
            filepath=glb, export_format="GLB", export_apply=True,
            export_cameras=True, export_lights=True)
        print("exported", glb)

    png = opt("--render")
    if png:
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.samples = int(opt("--samples", 128))
        scene.render.resolution_x = int(opt("--res", 1920))
        scene.render.resolution_y = int(opt("--resy", 1280))
        scene.render.filepath = os.path.abspath(png)
        os.makedirs(os.path.dirname(scene.render.filepath), exist_ok=True)
        bpy.ops.render.render(write_still=True)
        print("rendered", png)


if __name__ == "__main__":
    main()
