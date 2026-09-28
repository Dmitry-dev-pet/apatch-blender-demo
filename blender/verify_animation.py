from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import bpy
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


def close(a: float, b: float, tol: float = 1e-3) -> bool:
    return abs(float(a) - float(b)) <= tol


def vector_close(actual, expected, tol: float = 1e-3) -> bool:
    return all(close(a, b, tol) for a, b in zip(actual, expected))


def angle_close(actual: float, expected: float, tol: float = 1e-3) -> bool:
    error = ((float(actual) - float(expected) + math.pi) % (2 * math.pi)) - math.pi
    return abs(error) <= tol


def check(name: str, ok: bool, actual, expected, checks: dict) -> None:
    checks[name] = {
        "pass": bool(ok),
        "actual": actual,
        "expected": expected,
    }


def object_state(obj, frame: int):
    bpy.context.scene.frame_set(frame)
    return tuple(float(v) for v in obj.location), tuple(float(v) for v in obj.rotation_euler)


def expected_rotated_location(initial) -> tuple[float, float, float]:
    x, y, z = (float(v) for v in initial)
    return (-y, x, z)


def probe_video(path: Path) -> dict:
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


def main() -> None:
    checks = {}
    scene = bpy.context.scene

    check(
        "video_contract_id",
        scene.get("video_contract_id") == VIDEO_CONTRACT_ID,
        scene.get("video_contract_id"),
        VIDEO_CONTRACT_ID,
        checks,
    )
    check(
        "frame_range",
        (scene.frame_start, scene.frame_end) == (FRAME_START, FRAME_END),
        [scene.frame_start, scene.frame_end],
        [FRAME_START, FRAME_END],
        checks,
    )
    check(
        "fps",
        scene.render.fps == FPS and close(scene.render.fps_base, 1.0),
        [scene.render.fps, scene.render.fps_base],
        [FPS, 1.0],
        checks,
    )
    check(
        "render_resolution",
        (scene.render.resolution_x, scene.render.resolution_y) == (RESOLUTION, RESOLUTION),
        [scene.render.resolution_x, scene.render.resolution_y],
        [RESOLUTION, RESOLUTION],
        checks,
    )
    check(
        "render_engine",
        scene.render.engine == "BLENDER_EEVEE",
        scene.render.engine,
        "BLENDER_EEVEE",
        checks,
    )
    check(
        "video_format",
        scene.render.image_settings.file_format == "FFMPEG"
        and scene.render.ffmpeg.format == "MPEG4"
        and scene.render.ffmpeg.codec == "H264",
        {
            "file_format": scene.render.image_settings.file_format,
            "container": scene.render.ffmpeg.format,
            "codec": scene.render.ffmpeg.codec,
        },
        {"file_format": "FFMPEG", "container": "MPEG4", "codec": "H264"},
        checks,
    )

    moving = [
        obj for obj in bpy.data.objects
        if obj.get("u_turn_member") and obj.get("kind") in {"cubie", "sticker"}
    ]
    stationary = [
        obj for obj in bpy.data.objects
        if not obj.get("u_turn_member") and obj.get("kind") in {"cubie", "sticker"}
    ]

    turn_failures = []
    for obj in moving:
        initial = tuple(float(v) for v in obj["pre_turn_location"])
        expected_final = expected_rotated_location(initial)

        loc70, rot70 = object_state(obj, TURN_START)
        loc100, rot100 = object_state(obj, TURN_END)
        loc180, rot180 = object_state(obj, FRAME_END)

        if not (
            vector_close(loc70, initial)
            and angle_close(rot70[2], 0.0)
            and vector_close(loc100, expected_final)
            and angle_close(rot100[2], math.radians(90.0))
            and vector_close(loc180, expected_final)
            and angle_close(rot180[2], math.radians(90.0))
        ):
            turn_failures.append(
                {
                    "name": obj.name,
                    "frame70_location": [round(v, 4) for v in loc70],
                    "frame70_z_deg": round(math.degrees(rot70[2]), 3),
                    "frame100_location": [round(v, 4) for v in loc100],
                    "frame100_z_deg": round(math.degrees(rot100[2]), 3),
                    "frame180_location": [round(v, 4) for v in loc180],
                    "frame180_z_deg": round(math.degrees(rot180[2]), 3),
                }
            )

    check(
        "u_turn_animation",
        not turn_failures,
        turn_failures,
        "all U-layer cubies and stickers stay solved through frame 70, reach +90° at frame 100, and hold through frame 180",
        checks,
    )

    stationary_failures = []
    for obj in stationary:
        loc1, rot1 = object_state(obj, FRAME_START)
        loc180, rot180 = object_state(obj, FRAME_END)
        if not (vector_close(loc1, loc180) and vector_close(rot1, rot180)):
            stationary_failures.append(obj.name)

    check(
        "lower_layers_frozen",
        not stationary_failures,
        stationary_failures,
        "all non-U-layer cubies and stickers unchanged between frames 1 and 180",
        checks,
    )

    camera = bpy.data.objects.get("Camera")
    camera_ok = False
    camera_actual = None
    if camera is not None:
        loc1, _ = object_state(camera, FRAME_START)
        loc180, _ = object_state(camera, FRAME_END)
        distance = (Vector(loc180) - Vector(loc1)).length
        action = camera.animation_data.action if camera.animation_data else None
        camera_ok = action is not None and distance > 5.0
        camera_actual = {
            "frame1": [round(v, 3) for v in loc1],
            "frame180": [round(v, 3) for v in loc180],
            "travel": round(distance, 3),
        }

    check(
        "camera_orbit_animation",
        camera_ok,
        camera_actual,
        "animated camera with more than 5 Blender units of travel",
        checks,
    )

    video_path = OUTPUT / "rubik-demo.mp4"
    check(
        "video_exists",
        video_path.exists() and video_path.stat().st_size > 100_000,
        {"exists": video_path.exists(), "size": video_path.stat().st_size if video_path.exists() else 0},
        "MP4 larger than 100 KB",
        checks,
    )

    if video_path.exists():
        try:
            probe = probe_video(video_path)
            stream = probe["streams"][0]
            fmt = probe["format"]
            fps_num, fps_den = stream["r_frame_rate"].split("/")
            actual_fps = float(fps_num) / float(fps_den)
            duration = float(fmt["duration"])
            size = int(fmt["size"])
            probe_ok = (
                int(stream["width"]) == RESOLUTION
                and int(stream["height"]) == RESOLUTION
                and close(actual_fps, FPS, 1e-6)
                and abs(duration - 6.0) <= 0.15
                and size > 100_000
            )
            probe_actual = {
                "width": int(stream["width"]),
                "height": int(stream["height"]),
                "fps": actual_fps,
                "duration": duration,
                "size": size,
            }
        except Exception as exc:
            probe_ok = False
            probe_actual = {"error": repr(exc)}
    else:
        probe_ok = False
        probe_actual = {"error": "video missing"}

    check(
        "video_probe",
        probe_ok,
        probe_actual,
        {"width": 1080, "height": 1080, "fps": 30, "duration_seconds": 6.0},
        checks,
    )

    passed = all(item["pass"] for item in checks.values())
    report = {
        "contract": VIDEO_CONTRACT_ID,
        "status": "PASS" if passed else "FAIL",
        "blender_version": bpy.app.version_string,
        "checks": checks,
    }
    report_path = OUTPUT / "video-verification.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

    if not passed:
        raise RuntimeError(f"{VIDEO_CONTRACT_ID} verification failed")


if __name__ == "__main__":
    main()
