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

GitHub Actions runs the same pipeline using pinned Blender 5.2.2 LTS and publishes the full output as a workflow artifact. The latest validated preview is also committed to `generated/render.png`.

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
