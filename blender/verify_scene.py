from __future__ import annotations

import json
import math
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
CONTRACT_ID = "BLENDER-RUBIK-001"

EXPECTED_MATERIALS = {
    "U": "Sticker_White",
    "D": "Sticker_Yellow",
    "F": "Sticker_Green",
    "B": "Sticker_Blue",
    "R": "Sticker_Red",
    "L": "Sticker_Orange",
}


def close(a: float, b: float, tol: float = 1e-4) -> bool:
    return abs(float(a) - float(b)) <= tol


def vector_close(actual, expected, tol: float = 1e-4) -> bool:
    return all(close(a, b, tol) for a, b in zip(actual, expected))


def check(name: str, ok: bool, actual, expected, checks: dict) -> None:
    checks[name] = {
        "pass": bool(ok),
        "actual": actual,
        "expected": expected,
    }


def main() -> None:
    checks = {}
    scene = bpy.context.scene

    cubies = sorted(
        [obj for obj in bpy.data.objects if obj.get("kind") == "cubie"],
        key=lambda obj: obj.name,
    )
    stickers = sorted(
        [obj for obj in bpy.data.objects if obj.get("kind") == "sticker"],
        key=lambda obj: obj.name,
    )

    check("contract_id", scene.get("contract_id") == CONTRACT_ID, scene.get("contract_id"), CONTRACT_ID, checks)
    check("cubie_count", len(cubies) == 27, len(cubies), 27, checks)
    check("sticker_count", len(stickers) == 54, len(stickers), 54, checks)

    bad_dimensions = []
    bad_positions = []
    bad_turns = []

    for obj in cubies:
        dims = tuple(round(float(v), 5) for v in obj.dimensions)
        if not vector_close(dims, (0.94, 0.94, 0.94), 1e-4):
            bad_dimensions.append({"name": obj.name, "dimensions": dims})

        x = float(obj.get("grid_x"))
        y = float(obj.get("grid_y"))
        z = float(obj.get("grid_z"))
        if int(z) == 1:
            expected_location = (-y, x, z)
            expected_rotation = math.radians(90.0)
        else:
            expected_location = (x, y, z)
            expected_rotation = 0.0

        if not vector_close(tuple(obj.location), expected_location, 1e-4):
            bad_positions.append(
                {
                    "name": obj.name,
                    "location": [round(float(v), 5) for v in obj.location],
                    "expected": list(expected_location),
                }
            )

        actual_z = float(obj.rotation_euler.z)
        angle_error = ((actual_z - expected_rotation + math.pi) % (2 * math.pi)) - math.pi
        if abs(angle_error) > 1e-4:
            bad_turns.append(
                {
                    "name": obj.name,
                    "rotation_z_deg": round(math.degrees(actual_z), 5),
                    "expected_deg": round(math.degrees(expected_rotation), 5),
                }
            )

    check("cubie_dimensions", not bad_dimensions, bad_dimensions, "all 0.94 x 0.94 x 0.94", checks)
    check("u_turn_positions", not bad_positions, bad_positions, "top layer rotated +90° around Z; lower layers unchanged", checks)
    check("u_turn_rotations", not bad_turns, bad_turns, "top layer +90° Z rotation; lower layers 0°", checks)

    face_counts = {face: 0 for face in EXPECTED_MATERIALS}
    bad_materials = []
    for sticker in stickers:
        face = sticker.get("face")
        if face in face_counts:
            face_counts[face] += 1
        material_name = sticker.data.materials[0].name if sticker.data.materials else None
        expected_material = EXPECTED_MATERIALS.get(face)
        if material_name != expected_material:
            bad_materials.append(
                {"name": sticker.name, "face": face, "material": material_name, "expected": expected_material}
            )

    check("face_sticker_counts", all(count == 9 for count in face_counts.values()), face_counts, {face: 9 for face in face_counts}, checks)
    check("sticker_materials", not bad_materials, bad_materials, EXPECTED_MATERIALS, checks)

    camera = bpy.data.objects.get("Camera")
    check("camera_present", camera is not None and scene.camera == camera, camera.name if camera else None, "Camera", checks)
    check(
        "render_resolution",
        (scene.render.resolution_x, scene.render.resolution_y) == (768, 768),
        [scene.render.resolution_x, scene.render.resolution_y],
        [768, 768],
        checks,
    )
    check("render_engine", scene.render.engine == "BLENDER_EEVEE", scene.render.engine, "BLENDER_EEVEE", checks)
    check("render_png_exists", (OUTPUT / "render.png").exists(), str(OUTPUT / "render.png"), "existing PNG", checks)
    check("manifest_exists", (OUTPUT / "scene-manifest.json").exists(), str(OUTPUT / "scene-manifest.json"), "existing JSON", checks)

    passed = all(item["pass"] for item in checks.values())
    report = {
        "contract": CONTRACT_ID,
        "status": "PASS" if passed else "FAIL",
        "blender_version": bpy.app.version_string,
        "checks": checks,
    }
    (OUTPUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps(report, indent=2))
    if not passed:
        raise RuntimeError(f"{CONTRACT_ID} verification failed")


if __name__ == "__main__":
    main()
