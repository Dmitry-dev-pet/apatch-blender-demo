from __future__ import annotations

import math
from pathlib import Path

import bpy
from bpy_extras.anim_utils import animdata_get_channelbag_for_assigned_slot
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
VIDEO_CONTRACT_ID = "BLENDER-RUBIK-VIDEO-001"

FRAME_START = 1
TURN_START = 70
TURN_END = 100
FRAME_END = 180
FPS = 30
RESOLUTION = 1080


def point_at(obj, target=(0.0, 0.0, 0.0)) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def insert_transform_key(obj, frame: int) -> None:
    obj.keyframe_insert(data_path="location", frame=frame)
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def tune_action(obj) -> None:
    anim = obj.animation_data
    if anim is None or anim.action is None:
        return

    channelbag = animdata_get_channelbag_for_assigned_slot(anim)
    if channelbag is None:
        return

    for fcurve in channelbag.fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"


def animate_u_turn() -> int:
    moving = [
        obj for obj in bpy.data.objects
        if obj.get("u_turn_member") and obj.get("kind") in {"cubie", "sticker"}
    ]

    for obj in moving:
        final_location = obj.location.copy()
        final_rotation = obj.rotation_euler.copy()
        initial_location = Vector(tuple(float(v) for v in obj["pre_turn_location"]))

        obj.location = initial_location
        obj.rotation_euler = (0.0, 0.0, 0.0)
        insert_transform_key(obj, FRAME_START)
        insert_transform_key(obj, TURN_START)

        obj.location = final_location
        obj.rotation_euler = final_rotation
        insert_transform_key(obj, TURN_END)
        insert_transform_key(obj, FRAME_END)

        tune_action(obj)

    return len(moving)


def animate_camera() -> None:
    camera = bpy.data.objects["Camera"]
    target = (0.0, 0.0, -0.05)

    keyframes = [
        (FRAME_START, (6.9, -8.7, 6.2)),
        (90, (8.5, 1.0, 5.8)),
        (FRAME_END, (2.8, 8.6, 5.4)),
    ]

    for frame, location in keyframes:
        camera.location = location
        point_at(camera, target)
        insert_transform_key(camera, frame)

    tune_action(camera)


def configure_render() -> None:
    scene = bpy.context.scene
    scene["video_contract_id"] = VIDEO_CONTRACT_ID
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.render.resolution_x = RESOLUTION
    scene.render.resolution_y = RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.engine = "BLENDER_EEVEE"

    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = str(OUTPUT / "rubik-demo")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    moving_count = animate_u_turn()
    animate_camera()
    configure_render()

    bpy.context.scene.frame_set(FRAME_START)
    target = OUTPUT / "rubik-animated.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    print(
        f"Prepared {VIDEO_CONTRACT_ID}: "
        f"{moving_count} U-layer objects, "
        f"{FRAME_END - FRAME_START + 1} frames at {FPS} fps"
    )


if __name__ == "__main__":
    main()
