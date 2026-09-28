from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sequence_output"

CONTRACT_ID = "BLENDER-RUBIK-SEQUENCE-001"
SEQUENCE = ["R", "U", "R'", "U'"]
FPS = 30
FRAME_START = 1
FRAME_END = 180
RESOLUTION = 480
GRAPH_X = 2.05

MOVE_WINDOWS = [
    ("R", 21, 50),
    ("U", 61, 90),
    ("R'", 101, 130),
    ("U'", 141, 170),
]
CHECKPOINTS = [50, 90, 130, 170]

FACE_ORDER = ["U", "R", "F", "D", "L", "B"]
EDGE_POSITIONS = [(0, 1), (1, 2), (2, 1), (1, 0)]
CORNER_POSITIONS = [(0, 0), (0, 2), (2, 2), (2, 0)]
RING_RADII = {"center": 0.52, "edge": 1.04, "corner": 1.56}


def close(a: float, b: float, tol: float = 1e-3) -> bool:
    return abs(float(a) - float(b)) <= tol


def vector_close(actual, expected, tol: float = 1e-3) -> bool:
    return all(close(a, b, tol) for a, b in zip(actual, expected))


def quat_close(actual: Quaternion, expected: Quaternion, tol: float = 1e-3) -> bool:
    return 1.0 - abs(float(actual.normalized().dot(expected.normalized()))) <= tol


def check(name: str, ok: bool, actual, expected, checks: dict) -> None:
    checks[name] = {"pass": bool(ok), "actual": actual, "expected": expected}


def move_spec(move: str):
    if move == "R":
        return "X", -math.pi / 2, lambda c: int(round(c[0])) == 1
    if move == "R'":
        return "X", math.pi / 2, lambda c: int(round(c[0])) == 1
    if move == "U":
        return "Z", -math.pi / 2, lambda c: int(round(c[2])) == 1
    if move == "U'":
        return "Z", math.pi / 2, lambda c: int(round(c[2])) == 1
    raise ValueError(move)


def rotate_int(vector, axis: str, angle: float):
    rotated = Matrix.Rotation(angle, 4, axis) @ Vector(vector)
    return tuple(int(round(v)) for v in rotated)


def face_row_col(normal, coord):
    x, y, z = (int(v) for v in coord)
    n = tuple(int(v) for v in normal)
    if n == (0, 0, 1):
        return "U", y + 1, x + 1
    if n == (0, 0, -1):
        return "D", 1 - y, x + 1
    if n == (1, 0, 0):
        return "R", 1 - z, y + 1
    if n == (-1, 0, 0):
        return "L", 1 - z, 1 - y
    if n == (0, -1, 0):
        return "F", 1 - z, x + 1
    if n == (0, 1, 0):
        return "B", 1 - z, 1 - x
    raise ValueError((normal, coord))


def graph_slot(normal, coord):
    face, row, col = face_row_col(normal, coord)
    face_index = FACE_ORDER.index(face)
    rc = (row, col)

    if rc == (1, 1):
        radius = RING_RADII["center"]
        ordinal = face_index
        count = 6
    elif rc in EDGE_POSITIONS:
        radius = RING_RADII["edge"]
        ordinal = face_index * 4 + EDGE_POSITIONS.index(rc)
        count = 24
    else:
        radius = RING_RADII["corner"]
        ordinal = face_index * 4 + CORNER_POSITIONS.index(rc)
        count = 24

    angle = math.pi / 2 - 2 * math.pi * ordinal / count
    return (
        GRAPH_X + radius * math.cos(angle),
        0.12,
        radius * math.sin(angle),
    )


def simulate_piece(initial_coord, prefix):
    coord = tuple(initial_coord)
    quat = Quaternion((1.0, 0.0, 0.0, 0.0))
    for move in prefix:
        axis, angle, selector = move_spec(move)
        if selector(coord):
            axis_vector = (1.0, 0.0, 0.0) if axis == "X" else (0.0, 0.0, 1.0)
            coord = rotate_int(coord, axis, angle)
            quat = Quaternion(axis_vector, angle) @ quat
    return coord, quat


def simulate_sticker(initial_coord, initial_normal, prefix):
    coord = tuple(initial_coord)
    normal = tuple(initial_normal)
    for move in prefix:
        axis, angle, selector = move_spec(move)
        if selector(coord):
            coord = rotate_int(coord, axis, angle)
            normal = rotate_int(normal, axis, angle)
    return coord, normal


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


def main() -> None:
    scene = bpy.context.scene
    checks = {}

    check(
        "contract_id",
        scene.get("sequence_contract_id") == CONTRACT_ID,
        scene.get("sequence_contract_id"),
        CONTRACT_ID,
        checks,
    )
    check(
        "sequence",
        scene.get("sequence") == " ".join(SEQUENCE),
        scene.get("sequence"),
        " ".join(SEQUENCE),
        checks,
    )
    check(
        "resolution",
        (scene.render.resolution_x, scene.render.resolution_y) == (RESOLUTION, RESOLUTION),
        [scene.render.resolution_x, scene.render.resolution_y],
        [RESOLUTION, RESOLUTION],
        checks,
    )
    check(
        "timing",
        scene.frame_start == FRAME_START
        and scene.frame_end == FRAME_END
        and scene.render.fps == FPS
        and close(scene.render.fps_base, 1.0),
        [scene.frame_start, scene.frame_end, scene.render.fps, scene.render.fps_base],
        [FRAME_START, FRAME_END, FPS, 1.0],
        checks,
    )

    roots = sorted(
        [obj for obj in bpy.data.objects if obj.get("kind") == "piece_root"],
        key=lambda obj: obj.name,
    )
    nodes = sorted(
        [obj for obj in bpy.data.objects if obj.get("kind") == "graph_node"],
        key=lambda obj: obj.name,
    )
    check("piece_count", len(roots) == 27, len(roots), 27, checks)
    check("graph_node_count", len(nodes) == 54, len(nodes), 54, checks)

    piece_failures = []
    graph_failures = []

    for checkpoint_index, frame in enumerate(CHECKPOINTS, start=1):
        prefix = SEQUENCE[:checkpoint_index]
        scene.frame_set(frame)

        for root in roots:
            initial = (root["initial_x"], root["initial_y"], root["initial_z"])
            expected_coord, expected_quat = simulate_piece(initial, prefix)
            if not vector_close(tuple(root.location), expected_coord) or not quat_close(
                root.rotation_quaternion, expected_quat
            ):
                piece_failures.append(
                    {
                        "frame": frame,
                        "piece": root.name,
                        "location": [round(float(v), 4) for v in root.location],
                        "expected_location": list(expected_coord),
                    }
                )

        for node in nodes:
            initial_coord = (node["initial_x"], node["initial_y"], node["initial_z"])
            initial_normal = (node["initial_nx"], node["initial_ny"], node["initial_nz"])
            coord, normal = simulate_sticker(initial_coord, initial_normal, prefix)
            expected = graph_slot(normal, coord)
            if not vector_close(tuple(node.location), expected, 2e-3):
                graph_failures.append(
                    {
                        "frame": frame,
                        "node": node.name,
                        "location": [round(float(v), 4) for v in node.location],
                        "expected": [round(float(v), 4) for v in expected],
                    }
                )

    check(
        "piece_sequence_states",
        not piece_failures,
        piece_failures[:20],
        "all 27 piece roots match R U R' U' checkpoints",
        checks,
    )
    check(
        "graph_sequence_states",
        not graph_failures,
        graph_failures[:20],
        "all 54 graph nodes match sticker permutation checkpoints",
        checks,
    )

    frame_files = sorted((OUTPUT / "frames").glob("frame_*.png"))
    check("rendered_frames", len(frame_files) == 180, len(frame_files), 180, checks)

    video_path = OUTPUT / "sequence-demo.mp4"
    check(
        "video_exists",
        video_path.exists() and video_path.stat().st_size > 100_000,
        {
            "exists": video_path.exists(),
            "size": video_path.stat().st_size if video_path.exists() else 0,
        },
        "MP4 larger than 100 KB",
        checks,
    )

    if video_path.exists():
        try:
            probe = probe_video(video_path)
            stream = probe["streams"][0]
            fmt = probe["format"]
            num, den = stream["r_frame_rate"].split("/")
            actual_fps = float(num) / float(den)
            duration = float(fmt["duration"])
            size = int(fmt["size"])
            ok = (
                int(stream["width"]) == RESOLUTION
                and int(stream["height"]) == RESOLUTION
                and close(actual_fps, FPS, 1e-6)
                and abs(duration - 6.0) <= 0.15
                and size > 100_000
            )
            actual = {
                "width": int(stream["width"]),
                "height": int(stream["height"]),
                "fps": actual_fps,
                "duration": duration,
                "size": size,
            }
        except Exception as exc:
            ok = False
            actual = {"error": repr(exc)}
    else:
        ok = False
        actual = {"error": "missing"}

    check(
        "video_probe",
        ok,
        actual,
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
    (OUTPUT / "sequence-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

    if not passed:
        raise RuntimeError(f"{CONTRACT_ID} verification failed")


if __name__ == "__main__":
    main()
