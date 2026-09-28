# AGENTS.md

This repository is a deliberately small contract-driven Blender demo.

## Authority
The contract in `contracts/BLENDER-RUBIK-001.json` defines success. Do not redefine acceptance criteria to make an implementation pass.

## Mutable implementation
- `blender/build_sequence_demo.py`
- `blender/build_scene.py`
- `blender/animate_scene.py`

## Frozen judge
- `blender/verify_sequence_demo.py`
- `blender/verify_scene.py`
- `blender/verify_animation.py`

Treat the verifier as owner-controlled acceptance logic. Implementation work must not weaken, bypass, or rewrite it.

## Required evidence
A successful run must produce:
- `output/rubik.blend`
- `output/render.png`
- `output/scene-manifest.json`
- `output/verification.json`
- `output/rubik-animated.blend`
- `output/rubik-demo.mp4`
- `output/video-verification.json`

The demo is successful only when Blender exits cleanly and both `verification.json` and `video-verification.json` report `PASS`.

## Sequence demo
`contracts/BLENDER-RUBIK-SEQUENCE-001.json` governs the 480x480 R U R' U' synchronized cube + permutation graph video.
