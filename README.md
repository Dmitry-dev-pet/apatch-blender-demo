# APatch Blender Demo

A minimal reference demo for **contract-driven Blender automation**.

The point is not merely to let an AI agent execute arbitrary `bpy` code. The scene has an explicit acceptance contract and a separate frozen verifier. The implementation builds a real Blender scene; the verifier independently inspects the resulting `.blend` file.

## Demo contract

`BLENDER-RUBIK-001` requires:

- a 3x3x3 Rubik cube made from 27 cubies;
- 54 colored stickers, 9 on each face;
- cubies sized exactly 0.94 x 0.94 x 0.94 Blender units;
- a real +90 degree U-layer turn around Z;
- a 768 x 768 Eevee render;
- independent verification before the result is accepted.

## Run locally

Requires Blender 5.2.x:

```bash
blender --background --factory-startup \
  --python-exit-code 1 \
  --python blender/build_scene.py

blender output/rubik.blend --background \
  --python-exit-code 1 \
  --python blender/verify_scene.py
```

Outputs:

- `output/rubik.blend`
- `output/render.png`
- `output/scene-manifest.json`
- `output/verification.json`

GitHub Actions runs the same pipeline using pinned Blender 5.2.2 LTS and publishes the full output as a workflow artifact. The pipeline also creates a 6-second, 30 fps, 1080x1080 MP4 with a camera orbit and a contract-verified +90 degree U-layer turn. The latest validated still preview and verification JSON are committed under `generated/`.

## Why this exists

Typical Blender-agent integrations expose a broad Python execution surface. This demo tests a different model:

```text
human intent
   |
contract + frozen judge
   |
agent implementation
   |
Blender headless
   |
independent scene verification
   |
render + evidence
```

The next step is to wire this same pattern through APatch's governed execution and evidence model.


## 480x480 sequence demo

`BLENDER-RUBIK-SEQUENCE-001` renders a six-second 480x480 video of `R U R' U'`.

The left side is a real 3D Rubik cube. The right side is a 54-node sticker permutation graph on three concentric rings:

- center stickers stay on the center ring;
- edge stickers stay on the edge ring;
- corner stickers stay on the corner ring;
- every move animates graph nodes along their ring to the new facelet slot.

The workflow renders six 30-frame shards in parallel, merges all 180 frames, encodes H.264 MP4, and runs an independent frozen verifier against the cube and graph checkpoints.


## Bounded scene editing

`BLENDER-SCENE-EDIT-001` demonstrates editing an existing `.blend` under an explicit contract instead of rebuilding a new scene ad hoc.

The example permits only:

- a darker night world/background;
- 15% tighter orthographic camera framing;
- one new blue rim light;
- new render output paths.

The frozen verifier independently rebuilds/loads the base scene and compares protected static scene content plus all piece-root and graph-node transforms across all 180 animation frames. The edited result is accepted only if those semantic hashes remain identical while the requested visual changes are present.
