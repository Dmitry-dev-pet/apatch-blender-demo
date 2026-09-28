from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
BASE_BLEND = ROOT / "sequence_output" / "sequence-animated.blend"
EDITED_BLEND = ROOT / "edit_output" / "edited-sequence.blend"
OUTPUT = ROOT / "edit_output"

CONTRACT_ID = "BLENDER-SCENE-EDIT-001"
BASE_CONTRACT_ID = "BLENDER-RUBIK-SEQUENCE-001"
CAMERA_SCALE = 0.85
RESOLUTION = 480
FPS = 30
FRAME_START = 1
FRAME_END = 180
RIM_NAME = "Edit_BlueRim"
RIM_COLOR = (0.04, 0.18, 1.0)
RIM_ENERGY = 1150.0
NIGHT_COLOR = (0.0025, 0.006, 0.018, 1.0)
NIGHT_STRENGTH = 0.10


def close(a: float, b: float, tol: float = 1e-4) -> bool:
    return abs(float(a) - float(b)) <= tol


def vector_close(actual, expected, tol: float = 1e-4) -> bool:
    return all(close(a, b, tol) for a, b in zip(actual, expected))


def q(value: float) -> float:
    return round(float(value), 6)


def vec(values):
    return [q(v) for v in values]


def mesh_fingerprint(mesh):
    return {
        "vertices": [vec(v.co) for v in mesh.vertices],
        "polygons": [list(p.vertices) for p in mesh.polygons],
    }


def curve_fingerprint(curve):
    splines = []
    for spline in curve.splines:
        item = {"type": spline.type}
        if spline.type == "BEZIER":
            item["bezier"] = [
                {
                    "co": vec(point.co),
                    "left": vec(point.handle_left),
                    "right": vec(point.handle_right),
                }
                for point in spline.bezier_points
            ]
        else:
            item["points"] = [vec(point.co) for point in spline.points]
        splines.append(item)
    return {
        "bevel_depth": q(curve.bevel_depth),
        "bevel_resolution": int(curve.bevel_resolution),
        "splines": splines,
    }


def font_fingerprint(font):
    return {
        "body": font.body,
        "size": q(font.size),
        "extrude": q(font.extrude),
        "align_x": font.align_x,
        "align_y": font.align_y,
    }


def data_fingerprint(obj):
    if obj.type == "MESH":
        return mesh_fingerprint(obj.data)
    if obj.type == "CURVE":
        return curve_fingerprint(obj.data)
    if obj.type == "FONT":
        return font_fingerprint(obj.data)
    return None


def modifiers_fingerprint(obj):
    result = []
    for modifier in obj.modifiers:
        entry = {"name": modifier.name, "type": modifier.type}
        for attr in ("width", "segments"):
            if hasattr(modifier, attr):
                value = getattr(modifier, attr)
                entry[attr] = q(value) if isinstance(value, float) else value
        result.append(entry)
    return result


def material_names(obj):
    if obj.data is None or not hasattr(obj.data, "materials"):
        return []
    return [slot.name if slot else None for slot in obj.data.materials]


def static_scene_payload():
    scene = bpy.context.scene
    scene.frame_set(FRAME_START)
    objects = {}

    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        if obj.type in {"CAMERA", "LIGHT"}:
            continue

        kind = obj.get("kind")
        dynamic = kind in {"piece_root", "graph_node"}
        entry = {
            "type": obj.type,
            "parent": obj.parent.name if obj.parent else None,
            "kind": kind,
            "data": data_fingerprint(obj),
            "materials": material_names(obj),
            "modifiers": modifiers_fingerprint(obj),
        }

        if dynamic:
            custom = {}
            for key in sorted(obj.keys()):
                if key == "_RNA_UI":
                    continue
                value = obj[key]
                if isinstance(value, (int, float, str, bool)):
                    custom[key] = value
            entry["custom"] = custom
        else:
            entry["location"] = vec(obj.location)
            entry["scale"] = vec(obj.scale)
            entry["rotation_mode"] = obj.rotation_mode
            if obj.rotation_mode == "QUATERNION":
                entry["rotation"] = vec(obj.rotation_quaternion)
            else:
                entry["rotation"] = vec(obj.rotation_euler)

        objects[obj.name] = entry

    return {
        "sequence_contract_id": scene.get("sequence_contract_id"),
        "sequence": scene.get("sequence"),
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "fps": scene.render.fps,
        "fps_base": q(scene.render.fps_base),
        "objects": objects,
    }


def animation_payload():
    dynamic = sorted(
        [
            obj
            for obj in bpy.data.objects
            if obj.get("kind") in {"piece_root", "graph_node"}
        ],
        key=lambda item: item.name,
    )

    payload = {}
    scene = bpy.context.scene
    for frame in range(FRAME_START, FRAME_END + 1):
        scene.frame_set(frame)
        frame_state = {}
        for obj in dynamic:
            state = {
                "location": vec(obj.location),
                "scale": vec(obj.scale),
                "rotation_mode": obj.rotation_mode,
            }
            if obj.rotation_mode == "QUATERNION":
                state["rotation"] = vec(obj.rotation_quaternion)
            else:
                state["rotation"] = vec(obj.rotation_euler)
            frame_state[obj.name] = state
        payload[str(frame)] = frame_state
    return payload


def existing_lights_payload(exclude_edit_light: bool):
    result = {}
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        if obj.type != "LIGHT":
            continue
        if exclude_edit_light and obj.name == RIM_NAME:
            continue
        data = obj.data
        result[obj.name] = {
            "type": data.type,
            "energy": q(data.energy),
            "color": vec(data.color),
            "location": vec(obj.location),
            "rotation": vec(obj.rotation_euler),
            "size": q(data.size) if hasattr(data, "size") else None,
        }
    return result


def camera_payload():
    scene = bpy.context.scene
    camera = scene.camera
    if camera is None:
        return None
    return {
        "name": camera.name,
        "type": camera.data.type,
        "ortho_scale": q(camera.data.ortho_scale),
        "location": vec(camera.location),
        "rotation": vec(camera.rotation_euler),
    }


def world_payload():
    scene = bpy.context.scene
    background = scene.world.node_tree.nodes.get("Background") if scene.world and scene.world.use_nodes else None
    if background is None:
        return None
    return {
        "color": vec(background.inputs["Color"].default_value),
        "strength": q(background.inputs["Strength"].default_value),
    }


def semantic_snapshot(exclude_edit_light: bool):
    static = static_scene_payload()
    animation = animation_payload()
    return {
        "static": static,
        "animation": animation,
        "lights": existing_lights_payload(exclude_edit_light),
        "camera": camera_payload(),
        "world": world_payload(),
        "static_hash": hashlib.sha256(
            json.dumps(static, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "animation_hash": hashlib.sha256(
            json.dumps(animation, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def probe_video(path: Path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def check(name: str, ok: bool, actual, expected, checks: dict) -> None:
    checks[name] = {"pass": bool(ok), "actual": actual, "expected": expected}


def main() -> None:
    checks = {}

    if Path(bpy.data.filepath).resolve() != EDITED_BLEND.resolve():
        raise RuntimeError(f"Verifier must start from edited blend: {EDITED_BLEND}")

    edited_scene = bpy.context.scene
    edited_contract = edited_scene.get("edit_contract_id")
    edited_base_contract = edited_scene.get("edit_base_contract_id")
    edited_render = {
        "resolution": [edited_scene.render.resolution_x, edited_scene.render.resolution_y],
        "fps": edited_scene.render.fps,
        "frame_range": [edited_scene.frame_start, edited_scene.frame_end],
    }
    edited = semantic_snapshot(exclude_edit_light=True)

    rim = bpy.data.objects.get(RIM_NAME)
    rim_payload = None
    if rim is not None and rim.type == "LIGHT":
        rim_payload = {
            "type": rim.data.type,
            "color": vec(rim.data.color),
            "energy": q(rim.data.energy),
            "size": q(rim.data.size),
            "location": vec(rim.location),
            "tag": rim.get("edit_contract_id"),
        }

    edited_camera = edited["camera"]
    edited_world = edited["world"]

    bpy.ops.wm.open_mainfile(filepath=str(BASE_BLEND))
    base_scene = bpy.context.scene
    base = semantic_snapshot(exclude_edit_light=False)
    base_camera = base["camera"]
    base_world = base["world"]

    check("edit_contract_id", edited_contract == CONTRACT_ID, edited_contract, CONTRACT_ID, checks)
    check(
        "base_contract_id",
        edited_base_contract == BASE_CONTRACT_ID and base_scene.get("sequence_contract_id") == BASE_CONTRACT_ID,
        [edited_base_contract, base_scene.get("sequence_contract_id")],
        [BASE_CONTRACT_ID, BASE_CONTRACT_ID],
        checks,
    )

    check(
        "static_scene_unchanged",
        edited["static_hash"] == base["static_hash"],
        edited["static_hash"],
        base["static_hash"],
        checks,
    )
    check(
        "animation_unchanged",
        edited["animation_hash"] == base["animation_hash"],
        edited["animation_hash"],
        base["animation_hash"],
        checks,
    )
    check(
        "existing_lights_unchanged",
        edited["lights"] == base["lights"],
        edited["lights"],
        base["lights"],
        checks,
    )

    camera_ok = (
        edited_camera is not None
        and base_camera is not None
        and edited_camera["name"] == base_camera["name"]
        and edited_camera["type"] == "ORTHO"
        and base_camera["type"] == "ORTHO"
        and vector_close(edited_camera["location"], base_camera["location"])
        and vector_close(edited_camera["rotation"], base_camera["rotation"])
        and close(
            edited_camera["ortho_scale"],
            base_camera["ortho_scale"] * CAMERA_SCALE,
            1e-4,
        )
    )
    check(
        "camera_framing_only",
        camera_ok,
        {"base": base_camera, "edited": edited_camera},
        f"same ORTHO camera transform with ortho_scale x {CAMERA_SCALE}",
        checks,
    )

    world_ok = (
        edited_world is not None
        and vector_close(edited_world["color"], NIGHT_COLOR, 1e-4)
        and close(edited_world["strength"], NIGHT_STRENGTH, 1e-4)
        and base_world != edited_world
    )
    check(
        "night_world",
        world_ok,
        {"base": base_world, "edited": edited_world},
        {"color": list(NIGHT_COLOR), "strength": NIGHT_STRENGTH},
        checks,
    )

    rim_ok = (
        rim_payload is not None
        and rim_payload["type"] == "AREA"
        and vector_close(rim_payload["color"], RIM_COLOR, 1e-4)
        and close(rim_payload["energy"], RIM_ENERGY, 1e-3)
        and rim_payload["tag"] == CONTRACT_ID
    )
    check(
        "blue_rim_light",
        rim_ok,
        rim_payload,
        {"type": "AREA", "color": list(RIM_COLOR), "energy": RIM_ENERGY, "tag": CONTRACT_ID},
        checks,
    )

    check(
        "render_settings",
        edited_render
        == {
            "resolution": [RESOLUTION, RESOLUTION],
            "fps": FPS,
            "frame_range": [FRAME_START, FRAME_END],
        },
        edited_render,
        {
            "resolution": [RESOLUTION, RESOLUTION],
            "fps": FPS,
            "frame_range": [FRAME_START, FRAME_END],
        },
        checks,
    )

    frame_files = sorted((OUTPUT / "frames").glob("frame_*.png"))
    check("rendered_frames", len(frame_files) == 180, len(frame_files), 180, checks)

    preview_path = OUTPUT / "edit-preview.png"
    check(
        "preview_exists",
        preview_path.exists() and preview_path.stat().st_size > 10_000,
        {
            "exists": preview_path.exists(),
            "size": preview_path.stat().st_size if preview_path.exists() else 0,
        },
        "PNG larger than 10 KB",
        checks,
    )

    video_path = OUTPUT / "edit-demo.mp4"
    if video_path.exists():
        try:
            probe = probe_video(video_path)
            stream = probe["streams"][0]
            fmt = probe["format"]
            num, den = stream["r_frame_rate"].split("/")
            actual_fps = float(num) / float(den)
            duration = float(fmt["duration"])
            size = int(fmt["size"])
            video_ok = (
                int(stream["width"]) == RESOLUTION
                and int(stream["height"]) == RESOLUTION
                and close(actual_fps, FPS, 1e-6)
                and abs(duration - 6.0) <= 0.15
                and size > 100_000
            )
            video_actual = {
                "width": int(stream["width"]),
                "height": int(stream["height"]),
                "fps": actual_fps,
                "duration": duration,
                "size": size,
            }
        except Exception as exc:
            video_ok = False
            video_actual = {"error": repr(exc)}
    else:
        video_ok = False
        video_actual = {"error": "missing"}

    check(
        "video_probe",
        video_ok,
        video_actual,
        {"width": 480, "height": 480, "fps": 30, "duration": 6.0},
        checks,
    )

    passed = all(item["pass"] for item in checks.values())
    report = {
        "contract": CONTRACT_ID,
        "status": "PASS" if passed else "FAIL",
        "blender_version": bpy.app.version_string,
        "checks": checks,
    }
    (OUTPUT / "edit-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

    if not passed:
        raise RuntimeError(f"{CONTRACT_ID} verification failed")


if __name__ == "__main__":
    main()
