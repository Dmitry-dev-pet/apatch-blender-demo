from __future__ import annotations

import json
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "edit_output"
OUTPUT.mkdir(parents=True, exist_ok=True)

CONTRACT_ID = "BLENDER-SCENE-EDIT-001"
BASE_CONTRACT_ID = "BLENDER-RUBIK-SEQUENCE-001"
CAMERA_SCALE = 0.85
PREVIEW_FRAME = 80

NIGHT_COLOR = (0.0025, 0.006, 0.018, 1.0)
NIGHT_STRENGTH = 0.10

RIM_NAME = "Edit_BlueRim"
RIM_COLOR = (0.04, 0.18, 1.0)
RIM_ENERGY = 1150.0
RIM_SIZE = 2.6
RIM_LOCATION = (-4.8, 2.6, 4.4)
RIM_TARGET = (-2.0, 0.0, 0.0)


def point_at(obj, target) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_night_world(scene) -> None:
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    if background is None:
        raise RuntimeError("World Background node is missing")
    background.inputs["Color"].default_value = NIGHT_COLOR
    background.inputs["Strength"].default_value = NIGHT_STRENGTH


def tighten_camera(scene) -> tuple[float, float]:
    camera = scene.camera
    if camera is None:
        raise RuntimeError("Scene camera is missing")
    if camera.data.type != "ORTHO":
        raise RuntimeError("BLENDER-SCENE-EDIT-001 expects the base camera to remain ORTHO")

    before = float(camera.data.ortho_scale)
    after = before * CAMERA_SCALE
    camera.data.ortho_scale = after
    return before, after


def add_blue_rim() -> None:
    existing = bpy.data.objects.get(RIM_NAME)
    if existing is not None:
        bpy.data.objects.remove(existing, do_unlink=True)

    data = bpy.data.lights.new(name=RIM_NAME, type="AREA")
    data.energy = RIM_ENERGY
    data.color = RIM_COLOR
    data.shape = "DISK"
    data.size = RIM_SIZE

    light = bpy.data.objects.new(RIM_NAME, data)
    bpy.context.collection.objects.link(light)
    light.location = RIM_LOCATION
    point_at(light, RIM_TARGET)
    light["edit_contract_id"] = CONTRACT_ID
    light["allowed_effect"] = "blue_rim_light"


def main() -> None:
    scene = bpy.context.scene
    if scene.get("sequence_contract_id") != BASE_CONTRACT_ID:
        raise RuntimeError(
            f"Unexpected base scene contract: {scene.get('sequence_contract_id')!r}"
        )

    configure_night_world(scene)
    camera_before, camera_after = tighten_camera(scene)
    add_blue_rim()

    scene["edit_contract_id"] = CONTRACT_ID
    scene["edit_base_contract_id"] = BASE_CONTRACT_ID
    scene["edit_camera_scale"] = CAMERA_SCALE

    scene.render.resolution_x = 480
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    frames_dir = OUTPUT / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "contract": CONTRACT_ID,
        "base_contract": BASE_CONTRACT_ID,
        "allowed_changes": [
            "world.background",
            "camera.ortho_scale",
            "new light Edit_BlueRim",
            "render output paths",
        ],
        "applied": {
            "night_color": list(NIGHT_COLOR),
            "night_strength": NIGHT_STRENGTH,
            "camera_ortho_scale_before": camera_before,
            "camera_ortho_scale_after": camera_after,
            "camera_scale_factor": CAMERA_SCALE,
            "blue_rim": {
                "name": RIM_NAME,
                "color": list(RIM_COLOR),
                "energy": RIM_ENERGY,
                "size": RIM_SIZE,
                "location": list(RIM_LOCATION),
            },
        },
        "render": {
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "fps": scene.render.fps,
            "frame_range": [scene.frame_start, scene.frame_end],
        },
    }
    (OUTPUT / "edit-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    edited_path = OUTPUT / "edited-sequence.blend"
    scene.frame_set(PREVIEW_FRAME)
    scene.render.filepath = str(OUTPUT / "edit-preview.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(edited_path))
    bpy.ops.render.render(write_still=True)

    scene.render.filepath = str(frames_dir / "frame_")
    bpy.ops.wm.save_as_mainfile(filepath=str(edited_path))

    print(
        f"Applied {CONTRACT_ID}: world->night, "
        f"camera ortho_scale {camera_before:.4f}->{camera_after:.4f}, "
        f"added {RIM_NAME}"
    )


if __name__ == "__main__":
    main()
