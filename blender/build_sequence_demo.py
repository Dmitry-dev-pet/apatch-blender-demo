from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from bpy_extras.anim_utils import animdata_get_channelbag_for_assigned_slot
from mathutils import Matrix, Quaternion, Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sequence_output"
OUTPUT.mkdir(parents=True, exist_ok=True)

CONTRACT_ID = "BLENDER-RUBIK-SEQUENCE-001"
SEQUENCE = ["R", "U", "R'", "U'"]
FPS = 30
FRAME_START = 1
FRAME_END = 180
RESOLUTION = 480

CUBIE_SIZE = 0.92
STICKER_SIZE = 0.76
STICKER_THICKNESS = 0.035
CUBE_X = -2.0
GRAPH_X = 2.05

MOVE_WINDOWS = [
    ("R", 21, 50),
    ("U", 61, 90),
    ("R'", 101, 130),
    ("U'", 141, 170),
]

FACE_ORDER = ["U", "R", "F", "D", "L", "B"]
FACE_NORMALS = {
    "U": (0, 0, 1),
    "D": (0, 0, -1),
    "F": (0, -1, 0),
    "B": (0, 1, 0),
    "R": (1, 0, 0),
    "L": (-1, 0, 0),
}
FACE_MATERIALS = {
    "U": ("Sticker_White", (0.94, 0.94, 0.94, 1.0)),
    "D": ("Sticker_Yellow", (0.98, 0.72, 0.02, 1.0)),
    "F": ("Sticker_Green", (0.02, 0.62, 0.25, 1.0)),
    "B": ("Sticker_Blue", (0.03, 0.24, 0.82, 1.0)),
    "R": ("Sticker_Red", (0.88, 0.04, 0.05, 1.0)),
    "L": ("Sticker_Orange", (0.98, 0.30, 0.02, 1.0)),
}

EDGE_POSITIONS = [(0, 1), (1, 2), (2, 1), (1, 0)]
CORNER_POSITIONS = [(0, 0), (0, 2), (2, 2), (2, 0)]
RING_RADII = {"center": 0.52, "edge": 1.04, "corner": 1.56}


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.fonts,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def make_material(name: str, rgba, roughness: float = 0.35, emission_strength: float = 0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = rgba
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def add_box_child(root, name: str, local_location, dimensions, material, bevel: float):
    bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.parent = root
    obj.location = local_location
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    modifier = obj.modifiers.new(name="Bevel", type="BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    return obj


def sticker_local_transform(face: str):
    offset = CUBIE_SIZE / 2 + STICKER_THICKNESS / 2 + 0.008
    if face == "R":
        return (offset, 0.0, 0.0), (STICKER_THICKNESS, STICKER_SIZE, STICKER_SIZE)
    if face == "L":
        return (-offset, 0.0, 0.0), (STICKER_THICKNESS, STICKER_SIZE, STICKER_SIZE)
    if face == "F":
        return (0.0, -offset, 0.0), (STICKER_SIZE, STICKER_THICKNESS, STICKER_SIZE)
    if face == "B":
        return (0.0, offset, 0.0), (STICKER_SIZE, STICKER_THICKNESS, STICKER_SIZE)
    if face == "U":
        return (0.0, 0.0, offset), (STICKER_SIZE, STICKER_SIZE, STICKER_THICKNESS)
    if face == "D":
        return (0.0, 0.0, -offset), (STICKER_SIZE, STICKER_SIZE, STICKER_THICKNESS)
    raise ValueError(face)


def add_piece(container, coord, black, sticker_materials):
    x, y, z = coord
    root = bpy.data.objects.new(f"Piece_x{x}_y{y}_z{z}", None)
    root.empty_display_type = "PLAIN_AXES"
    root.parent = container
    root.location = (x, y, z)
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
    root["kind"] = "piece_root"
    root["initial_x"] = x
    root["initial_y"] = y
    root["initial_z"] = z
    bpy.context.collection.objects.link(root)

    body = add_box_child(
        root,
        f"Cubie_x{x}_y{y}_z{z}",
        (0.0, 0.0, 0.0),
        (CUBIE_SIZE, CUBIE_SIZE, CUBIE_SIZE),
        black,
        0.07,
    )
    body["kind"] = "cubie"

    faces = []
    if x == 1:
        faces.append("R")
    if x == -1:
        faces.append("L")
    if y == -1:
        faces.append("F")
    if y == 1:
        faces.append("B")
    if z == 1:
        faces.append("U")
    if z == -1:
        faces.append("D")

    stickers = []
    for face in faces:
        local_location, dimensions = sticker_local_transform(face)
        sticker = add_box_child(
            root,
            f"Sticker_{face}_x{x}_y{y}_z{z}",
            local_location,
            dimensions,
            sticker_materials[face],
            0.03,
        )
        sticker["kind"] = "sticker"
        sticker["face"] = face
        stickers.append(sticker)

    return root, faces, stickers


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
        ring = "center"
        ordinal = face_index
        count = 6
    elif rc in EDGE_POSITIONS:
        ring = "edge"
        ordinal = face_index * 4 + EDGE_POSITIONS.index(rc)
        count = 24
    else:
        ring = "corner"
        ordinal = face_index * 4 + CORNER_POSITIONS.index(rc)
        count = 24

    angle = math.pi / 2 - 2 * math.pi * ordinal / count
    radius = RING_RADII[ring]
    location = Vector((GRAPH_X + radius * math.cos(angle), 0.12, radius * math.sin(angle)))
    return ring, angle, location


def add_graph_ring(radius: float, material, name: str):
    bpy.ops.curve.primitive_bezier_circle_add(
        radius=radius,
        location=(GRAPH_X, 0.18, 0.0),
        rotation=(math.radians(90.0), 0.0, 0.0),
    )
    ring = bpy.context.object
    ring.name = name
    ring.data.bevel_depth = 0.018
    ring.data.bevel_resolution = 2
    ring.data.materials.append(material)
    return ring


def add_graph_node(sticker_id: str, source_face: str, coord, normal, material):
    ring, angle, location = graph_slot(normal, coord)
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=16,
        ring_count=8,
        radius=0.085,
        location=location,
    )
    node = bpy.context.object
    node.name = f"Graph_{sticker_id}"
    node.data.materials.append(material)
    node["kind"] = "graph_node"
    node["sticker_id"] = sticker_id
    node["initial_face"] = source_face
    node["initial_x"] = int(coord[0])
    node["initial_y"] = int(coord[1])
    node["initial_z"] = int(coord[2])
    node["initial_nx"] = int(normal[0])
    node["initial_ny"] = int(normal[1])
    node["initial_nz"] = int(normal[2])
    node["ring"] = ring
    node["initial_angle"] = angle
    return node


def add_text(body: str, location, size: float, material, name: str):
    bpy.ops.object.text_add(
        location=location,
        rotation=(math.radians(90.0), 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.005
    obj.data.materials.append(material)
    return obj


def point_at(obj, target=(0.0, 0.0, 0.0)) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_area_light(name: str, location, energy: float, size: float, target):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    light = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(light)
    light.location = location
    point_at(light, target)
    return light


def key_transform(obj, frame: int) -> None:
    obj.keyframe_insert(data_path="location", frame=frame)
    if obj.rotation_mode == "QUATERNION":
        obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    else:
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


def rotate_vector(vector, axis: str, angle: float):
    matrix = Matrix.Rotation(angle, 4, axis)
    return matrix @ Vector(vector)


def rotate_int(vector, axis: str, angle: float):
    rotated = rotate_vector(vector, axis, angle)
    return tuple(int(round(v)) for v in rotated)


def shortest_angle_delta(start: float, end: float) -> float:
    return (end - start + math.pi) % (2 * math.pi) - math.pi


def animate_sequence(piece_roots, graph_nodes, sticker_states):
    piece_states = {
        root.name: {
            "coord": Vector((root["initial_x"], root["initial_y"], root["initial_z"])),
            "quat": Quaternion((1.0, 0.0, 0.0, 0.0)),
        }
        for root in piece_roots
    }

    for root in piece_roots:
        key_transform(root, FRAME_START)
    for node in graph_nodes:
        node.keyframe_insert(data_path="location", frame=FRAME_START)

    for move, start, end in MOVE_WINDOWS:
        axis, angle, selector = move_spec(move)
        axis_vector = (1.0, 0.0, 0.0) if axis == "X" else (0.0, 0.0, 1.0)

        for root in piece_roots:
            state = piece_states[root.name]
            root.location = state["coord"]
            root.rotation_quaternion = state["quat"]
            key_transform(root, start)

            if selector(state["coord"]):
                base_coord = state["coord"].copy()
                base_quat = state["quat"].copy()
                for fraction in (0.25, 0.5, 0.75, 1.0):
                    frame = round(start + (end - start) * fraction)
                    partial = angle * fraction
                    root.location = rotate_vector(base_coord, axis, partial)
                    root.rotation_quaternion = Quaternion(axis_vector, partial) @ base_quat
                    key_transform(root, frame)

                state["coord"] = Vector(rotate_int(base_coord, axis, angle))
                state["quat"] = Quaternion(axis_vector, angle) @ base_quat
            else:
                key_transform(root, end)

        for node in graph_nodes:
            state = sticker_states[node.name]
            node.keyframe_insert(data_path="location", frame=start)
            if selector(state["coord"]):
                _, start_angle, _ = graph_slot(state["normal"], state["coord"])
                final_coord = rotate_int(state["coord"], axis, angle)
                final_normal = rotate_int(state["normal"], axis, angle)
                ring, end_angle, _ = graph_slot(final_normal, final_coord)
                radius = RING_RADII[ring]
                delta = shortest_angle_delta(start_angle, end_angle)

                for fraction in (0.25, 0.5, 0.75, 1.0):
                    frame = round(start + (end - start) * fraction)
                    a = start_angle + delta * fraction
                    node.location = (
                        GRAPH_X + radius * math.cos(a),
                        0.12,
                        radius * math.sin(a),
                    )
                    node.keyframe_insert(data_path="location", frame=frame)

                state["coord"] = final_coord
                state["normal"] = final_normal
            else:
                node.keyframe_insert(data_path="location", frame=end)

    for root in piece_roots:
        state = piece_states[root.name]
        root.location = state["coord"]
        root.rotation_quaternion = state["quat"]
        key_transform(root, FRAME_END)
        tune_action(root)

    for node in graph_nodes:
        node.keyframe_insert(data_path="location", frame=FRAME_END)
        tune_action(node)


def main() -> None:
    clear_scene()

    black = make_material("Sequence_Cubie_Black", (0.012, 0.014, 0.018, 1.0), roughness=0.28)
    ring_mat = make_material("Sequence_Rings", (0.22, 0.27, 0.34, 1.0), roughness=0.45, emission_strength=0.3)
    text_mat = make_material("Sequence_Text", (0.78, 0.84, 0.92, 1.0), roughness=0.4, emission_strength=0.15)
    sticker_materials = {
        face: make_material(f"Sequence_{name}", rgba, roughness=0.22)
        for face, (name, rgba) in FACE_MATERIALS.items()
    }

    cube_container = bpy.data.objects.new("CubeContainer", None)
    cube_container.location = (CUBE_X, 0.0, -0.05)
    cube_container.rotation_euler = (
        math.radians(18.0),
        0.0,
        math.radians(-24.0),
    )
    bpy.context.collection.objects.link(cube_container)

    piece_roots = []
    graph_nodes = []
    sticker_states = {}

    for radius, label in (
        (RING_RADII["center"], "CenterRing"),
        (RING_RADII["edge"], "EdgeRing"),
        (RING_RADII["corner"], "CornerRing"),
    ):
        add_graph_ring(radius, ring_mat, label)

    for z in (-1, 0, 1):
        for y in (-1, 0, 1):
            for x in (-1, 0, 1):
                root, faces, _ = add_piece(
                    cube_container,
                    (x, y, z),
                    black,
                    sticker_materials,
                )
                piece_roots.append(root)

                for face in faces:
                    sticker_id = f"{face}_x{x}_y{y}_z{z}"
                    normal = FACE_NORMALS[face]
                    node = add_graph_node(
                        sticker_id,
                        face,
                        (x, y, z),
                        normal,
                        sticker_materials[face],
                    )
                    graph_nodes.append(node)
                    sticker_states[node.name] = {
                        "coord": (x, y, z),
                        "normal": normal,
                    }

    add_text("R  U  R'  U'", (0.0, 0.05, 3.05), 0.36, text_mat, "SequenceTitle")
    add_text("3D", (CUBE_X, 0.05, -2.35), 0.23, text_mat, "CubeLabel")
    add_text("PERMUTATION GRAPH", (GRAPH_X, 0.05, -2.35), 0.20, text_mat, "GraphLabel")

    camera_data = bpy.data.cameras.new("Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 7.8
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (0.0, -14.0, 0.0)
    point_at(camera, (0.0, 0.0, 0.0))
    bpy.context.scene.camera = camera

    add_area_light("Key", (-3.0, -5.0, 5.0), 850, 4.0, (CUBE_X, 0.0, 0.0))
    add_area_light("Fill", (1.0, -4.0, 2.0), 450, 3.0, (CUBE_X, 0.0, 0.0))
    add_area_light("Rim", (-1.0, 2.0, 5.0), 600, 3.0, (CUBE_X, 0.0, 0.0))

    animate_sequence(piece_roots, graph_nodes, sticker_states)

    scene = bpy.context.scene
    scene["sequence_contract_id"] = CONTRACT_ID
    scene["sequence"] = " ".join(SEQUENCE)
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.render.resolution_x = RESOLUTION
    scene.render.resolution_y = RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.engine = "BLENDER_EEVEE"
    if scene.eevee is not None:
        scene.eevee.taa_render_samples = 1

    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.012, 0.016, 0.026, 1.0)
        background.inputs["Strength"].default_value = 0.32

    manifest = {
        "contract": CONTRACT_ID,
        "sequence": SEQUENCE,
        "blender_version": bpy.app.version_string,
        "resolution": [RESOLUTION, RESOLUTION],
        "fps": FPS,
        "frame_range": [FRAME_START, FRAME_END],
        "piece_roots": len(piece_roots),
        "graph_nodes": len(graph_nodes),
        "graph_rings": RING_RADII,
        "move_windows": [
            {"move": move, "start": start, "end": end}
            for move, start, end in MOVE_WINDOWS
        ],
    }
    (OUTPUT / "sequence-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    scene.frame_set(FRAME_START)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(OUTPUT / "sequence-preview.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "sequence-animated.blend"))
    bpy.ops.render.render(write_still=True)

    frames = OUTPUT / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(frames / "frame_")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "sequence-animated.blend"))

    print(
        f"Built {CONTRACT_ID}: {len(piece_roots)} pieces, "
        f"{len(graph_nodes)} graph nodes, sequence {' '.join(SEQUENCE)}"
    )


if __name__ == "__main__":
    main()
