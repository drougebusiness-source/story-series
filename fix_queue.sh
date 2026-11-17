#!/usr/bin/env bash
# Quality fixes found in review on 2026-11-13, queued because Gemini credits ran out. About $2.10 in total.
# Run from story-series after topping up Gemini:   bash fix_queue.sh
set -e
PY=./.venv/Scripts/python.exe

# 1. THE LAST DRAFT ep1 shot 3: Tank's bump on Dani's arm was too subtle (new keyframe + clip, ~$0.31)
$PY cartoon.py last-draft ep1 redo 3

# 2. ROLL FOR FATE: Wren read as a young boy; she is a 23-year-old woman (new reference + all 5 shots, ~$1.47)
$PY cartoon.py roll-for-fate ep1 recast "Wren Ashby"
$PY cartoon.py roll-for-fate ep1 redo 1 2 3 4 5

# 3. DRIFTBORN ep1 shots 1-2: Kael's hair grew long and shaggy mid-shot (clips only, keyframes are fine, ~$0.49)
$PY cartoon.py driftborn ep1 redo 1 2 --video-only
