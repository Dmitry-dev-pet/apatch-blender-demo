# AGENTS.md

This repository is a deliberately small contract-driven Blender demo.

## Authority
The contract in `contracts/BLENDER-RUBIK-001.json` defines success. Do not redefine acceptance criteria to make an implementation pass.

## Mutable implementation
- `blender/build_scene.py`

## Frozen judge
- `blender/verify_scene.py`

Treat the verifier as owner-controlled acceptance logic. Implementation work must not weaken, bypass, or rewrite it.

## Required evidence
A successful run must produce:
- `output/rubik.blend`
- `output/render.png`
- `output/scene-manifest.json`
- `output/verification.json`

The demo is successful only when Blender exits cleanly and `verification.json` reports `PASS`.
