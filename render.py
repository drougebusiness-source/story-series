"""THE way to render an episode. Same steps and the same quality gate every time, so a fix the owner asked for once
stays fixed (owner, 2026-11-16: "I say it one time and then we render again and it's not fixed").
    python render.py <series> [ep1]
1. pictures (keys)  2. animation (video, lip-synced talking shots)  3. soundtrack (voiced)
4. teaser/recap (final, when the episode has them)  5. quality gate (qa.py): the episode is only finished on PASS.
Only shots and pictures that don't exist yet cost money; everything already made is reused.
Needs GEMINI_API_KEY and ELEVENLABS_API_KEY (user environment variables; read from the registry if the shell lacks them).
"""
import os
import sys

import cartoon
import qa
import voice


def _env(name: str):
    if os.environ.get(name):
        return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            os.environ[name] = winreg.QueryValueEx(k, name)[0]
    except OSError:
        pass


def main(slug: str, ep: str = "ep1"):
    for n in ("GEMINI_API_KEY", "ELEVENLABS_API_KEY"):
        _env(n)
    e = cartoon.Episode(slug, ep)
    out = cartoon.ROOT / "out" / "cartoon"                # a fresh render replaces every old finished file
    for old in out.glob(f"{slug}-{ep}-*.mp4"):
        old.unlink()
    (cartoon.ROOT / "out" / "qa" / f"{slug}-{ep}" / "PASS.json").unlink(missing_ok=True)
    e.keys()
    e.video()
    voice.voiced(slug, ep)
    if e.ep.get("teaser") or e.ep.get("recap"):
        e.final()
    ok = qa.gate(slug, ep)
    print(f"\n{slug} {ep}: {'PASSED the quality gate' if ok else 'FAILED the quality gate: see out/qa/' + slug + '-' + ep + '/REPORT.md'}"
          f"  (spent ~${e.spent:.2f})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(*sys.argv[1:]) else 1)
