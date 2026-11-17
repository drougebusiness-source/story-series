# Quality: how every episode is rendered and checked

The owner's rule (2026-11-16): fixes must stay fixed. "I say it one time and then we render the videos again and
it's not fixed." So nobody renders by hand. One command does every step and ends with the same checks every time:

    .venv\Scripts\python render.py <series> [ep1]

An episode is finished only when the gate says **PASS** (`out/qa/<series>-<ep>/PASS.json`). A failed episode is
renamed `*.QA-FAILED.mp4` and its problems are listed in `out/qa/<series>-<ep>/REPORT.md`. Fix those shots
(`cartoon.py <series> <ep> redo <n> --video-only`), then run render.py again. Never send or post a video without a
PASS. Posting automation must check PASS.json.

## What the gate checks (qa.py)
| Owner rule | Check |
|---|---|
| Nobody teleports or pops around | frame-jump detector on every shot; `continues:` shots must start on the last frame of the shot before; Gemini watches every shot |
| Smooth, clear, professional movement, no slop | Gemini animation-supervisor review of every shot: morphing, size changes, extra limbs, text, unclear or jittery action, the scripted action not happening |
| Mouths match the words | talking shots are lip-synced (the video model speaks the line, ElevenLabs swaps in the cast voice); every line is transcribed and compared with the script |
| No clicks or static | click/static/dead-air scan of the finished file; Gemini listens to every line |
| Nobody talks over anyone | no two lines overlap (voice.timeline lengthens shots to fit their lines) |
| Nobody randomly louder or softer | every line is set to the same loudness; the gate fails a line more than 3 dB off, a loudness spike, or an episode far from -15 LUFS |
| Nobody yells without a reason | lines speak at a calm volume unless the shot says `shout: true`; Gemini flags yelling |

## What else is automatic
- **Mood:** `<series>/cartoon/tone.md` goes into every set, picture and animation prompt (horror is dark with one
  light; comedy has big silly acting).
- **Sounds:** a sound the story needs (a clang, a hum) goes in the shot's `sfx:` and `<series>/cartoon/sfx.yaml`.
- **Design notes:** `<series>/cartoon/cast.yaml` holds what must hold in every picture (age, size, outfit). The
  review gets them too, so a designed feature isn't called a glitch.
- **Voices:** `<series>/cartoon/voices.yaml`. Characters on screen use ElevenLabs (`eleven:`), the narrator uses Gemini.
