from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)

CONTRACT_ID = "BLENDER-RUBIK-001"
CUBIE_SIZE = 0.94
GRID_STEP = 1.0
STICKER_SIZE = 0.78
STICKER_THICKNESS = 0.035
TOP_TURN_DEG = 90.0

FACE_MATERIALS = {
    "U": ("Sticker_White", (0.92, 0.92, 0.92, 1.0)),
    "D": ("Sticker_Yellow", (0.95, 0.72, 0.03, 1.0)),
    "F": ("Sticker_Green", (0.03, 0.58, 0.24, 1.0)),
    "B": ("Sticker_Blue", (0.03, 0.22, 0.75, 1.0)),
    "R": ("Sticker_Red", (0.82, 0.04, 0.05, 1.0)),
    "L": ("Sticker_Orange", (0.95, 0.28, 0.02, 1.0)),
}


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def make_material(name: str, rgba: tuple[float, float, float, float], roughness: float = 0.38, metallic: float = 0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    return mat


def add_box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    material,
    bevel: float,
):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    modifier = obj.modifiers.new(name="Bevel", type="BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    return obj


def add_sticker(
    face: str,
    grid: tuple[int, int, int],
    cubie_location: tuple[float, float, float],
    material,
):
    x, y, z = grid
    cx, cy, cz = cubie_location
    offset = CUBIE_SIZE / 2 + STICKER_THICKNESS / 2 + 0.008

    if face == "R":
        loc = (cx + offset, cy, cz)
        dims = (STICKER_THICKNESS, STICKER_SIZE, STICKER_SIZE)
    elif face == "L":
        loc = (cx - offset, cy, cz)
        dims = (STICKER_THICKNESS, STICKER_SIZE, STICKER_SIZE)
    elif face == "F":
        loc = (cx, cy - offset, cz)
        dims = (STICKER_SIZE, STICKER_THICKNESS, STICKER_SIZE)
    elif face == "B":
        loc = (cx, cy + offset, cz)
        dims = (STICKER_SIZE, STICKER_THICKNESS, STICKER_SIZE)
    elif face == "U":
        loc = (cx, cy, cz + offset)
        dims = (STICKER_SIZE, STICKER_SIZE, STICKER_THICKNESS)
    elif face == "D":
        loc = (cx, cy, cz - offset)
        dims = (STICKER_SIZE, STICKER_SIZE, STICKER_THICKNESS)
    else:
        raise ValueError(face)

    obj = add_box(
        f"Sticker_{face}_x{x}_y{y}_z{z}",
        loc,
        dims,
        material,
        bevel=0.035,
    )
    obj["kind"] = "sticker"
    obj["face"] = face
    obj["grid_x"] = x
    obj["grid_y"] = y
    obj["grid_z"] = z
    obj["pre_turn_location"] = list(loc)
    obj["u_turn_member"] = bool(z == 1)
    return obj


def rotate_about_z_90(obj) -> None:
    x, y, z = obj.location
    obj.location = (-y, x, z)
    obj.rotation_euler.rotate_axis("Z", math.radians(TOP_TURN_DEG))
    obj["applied_turn_deg"] = TOP_TURN_DEG


def point_at(obj, target=(0.0, 0.0, 0.0)) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_area_light(name: str, location, energy: float, size: float, target=(0.0, 0.0, 0.0)):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    light = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(light)
    light.location = location
    point_at(light, target)
    return light


def main() -> None:
    clear_scene()

    black = make_material("Cubie_Black", (0.012, 0.014, 0.018, 1.0), roughness=0.3)
    floor_mat = make_material("Floor", (0.08, 0.095, 0.12, 1.0), roughness=0.52)
    sticker_materials = {
        face: make_material(name, rgba, roughness=0.26)
        for face, (name, rgba) in FACE_MATERIALS.items()
    }

    cubies = []
    stickers = []

    for z in (-1, 0, 1):
        for y in (-1, 0, 1):
            for x in (-1, 0, 1):
                loc = (x * GRID_STEP, y * GRID_STEP, z * GRID_STEP)
                cubie = add_box(
                    f"Cubie_x{x}_y{y}_z{z}",
                    loc,
                    (CUBIE_SIZE, CUBIE_SIZE, CUBIE_SIZE),
                    black,
                    bevel=0.075,
                )
                cubie["kind"] = "cubie"
                cubie["grid_x"] = x
                cubie["grid_y"] = y
                cubie["grid_z"] = z
                cubie["pre_turn_location"] = list(loc)
                cubie["u_turn_member"] = bool(z == 1)
                cubies.append(cubie)

                if x == 1:
                    stickers.append(add_sticker("R", (x, y, z), loc, sticker_materials["R"]))
                if x == -1:
                    stickers.append(add_sticker("L", (x, y, z), loc, sticker_materials["L"]))
                if y == -1:
                    stickers.append(add_sticker("F", (x, y, z), loc, sticker_materials["F"]))
                if y == 1:
                    stickers.append(add_sticker("B", (x, y, z), loc, sticker_materials["B"]))
                if z == 1:
                    stickers.append(add_sticker("U", (x, y, z), loc, sticker_materials["U"]))
                if z == -1:
                    stickers.append(add_sticker("D", (x, y, z), loc, sticker_materials["D"]))

    for obj in [*cubies, *stickers]:
        if obj.get("u_turn_member"):
            rotate_about_z_90(obj)

    # Ground.
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0.0, 0.0, -1.53))
    floor = bpy.context.object
    floor.name = "Ground"
    floor.data.materials.append(floor_mat)

    # Camera.
    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (6.9, -8.7, 6.2)
    camera.data.lens = 58
    point_at(camera, (0.0, 0.0, -0.05))
    bpy.context.scene.camera = camera

    # Lighting.
    add_area_light("Key", (4.5, -4.0, 7.5), 1050, 5.0)
    add_area_light("Fill", (-4.5, -2.0, 4.5), 650, 4.0)
    add_area_light("Rim", (1.0, 5.5, 6.0), 900, 3.5)

    scene = bpy.context.scene
    scene["contract_id"] = CONTRACT_ID
    scene["top_turn_deg"] = TOP_TURN_DEG
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 768
    scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(OUTPUT / "render.png")

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg is not None:
        bg.inputs["Color"].default_value = (0.018, 0.024, 0.035, 1.0)
        bg.inputs["Strength"].default_value = 0.42

    manifest = {
        "contract": CONTRACT_ID,
        "blender_version": bpy.app.version_string,
        "cubies": len(cubies),
        "stickers": len(stickers),
        "grid": [3, 3, 3],
        "cubie_size": CUBIE_SIZE,
        "grid_step": GRID_STEP,
        "top_turn_deg": TOP_TURN_DEG,
        "camera_location": [round(float(v), 4) for v in camera.location],
        "render": {
            "engine": scene.render.engine,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        },
    }
    (OUTPUT / "scene-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "rubik.blend"))
    bpy.ops.render.render(write_still=True)
    print(f"Built {CONTRACT_ID}: {len(cubies)} cubies, {len(stickers)} stickers")


if __name__ == "__main__":
    main()
