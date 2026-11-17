"""The quality gate. Every render ends here (render.py runs it), so the owner's rules are checked every single time,
not remembered by whoever renders. An episode that fails is renamed *.QA-FAILED.mp4 and must not be sent or posted.
    python qa.py <series> [ep1] [--no-ai]   -> out/qa/<series>-<ep>/REPORT.md (+ PASS.json when it passes)

Owner rules (2026-11-13 / 11-16) and the check for each:
  nobody teleports / jumps            V1 sudden picture jumps inside a shot; V2 a `continues:` shot starts on the last frame
  smooth, clear, professional motion  AI1 Gemini watches every shot (morphing, size changes, glitches, the action happens)
  mouths match the words              W1 every line transcribed and compared with the script
  no clicks or static in the voices   A1 click/static/dead-air scan of the finished file (voice.audio_check)
  nobody talks over anyone            A2 no two lines overlap
  nobody randomly too loud or soft    A3 every line within 3 dB of the others; A4 no loudness spikes, sane overall level
  nobody yells without a reason       AI2 Gemini listens to every line (yelling, distortion, static, mumbling)
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

ROOT = Path(__file__).parent
WHISPER_PY = ROOT.parent / "agent-office" / "reels" / ".venv" / "Scripts" / "python.exe"   # free local transcriber


def frames(clip: Path, w=90, h=160) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo",
                          "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def jumps(f: np.ndarray, fps: float = 24.0) -> list[str]:
    """V1: a frame that changes far more than the frames around it is a pop/teleport (steady fast action is fine)."""
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    out = []
    for k in range(len(d)):
        near = np.r_[d[max(0, k - 6):k], d[k + 1:k + 7]]
        local = float(np.median(near)) if len(near) else 0.0
        if d[k] > 6.0 and d[k] > 4 * max(local, 0.5):
            out.append(f"sudden jump at {(k + 1) / fps:.2f}s (change {d[k]:.1f}, around it {local:.1f})")
    return out


def overlaps(lines: list[dict], gap: float = 0.15) -> list[str]:
    """A2: lines sorted by start must each end before the next begins (with a small breath between)."""
    out, ls = [], sorted(lines, key=lambda x: x["start"])
    for a, b in zip(ls, ls[1:]):
        if a["end"] + gap > b["start"]:
            out.append(f"{a['who']} (shot {a['shot']}) runs into {b['who']} (shot {b['shot']}) at {b['start']:.2f}s")
    return out


def loudness(speech: np.ndarray, lines: list[dict], rate: int, tol: float = 3.0) -> list[str]:
    """A3: every line's speech loudness within tol dB of the episode's median line."""
    import voice
    lv = [(ln, voice.speech_db(speech[int(ln["start"] * rate):int(ln["end"] * rate)], rate)) for ln in lines]
    if not lv:
        return []
    med = float(np.median([v for _, v in lv]))
    return [f"{ln['who']} (shot {ln['shot']}) is {v - med:+.1f} dB from the other lines" for ln, v in lv
            if abs(v - med) > tol]


def spikes(path: Path) -> list[str]:
    """A4: overall level near -15 LUFS, short-term loudness never jumps far above it, peaks under -0.5 dBFS."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"S:\s*(-?[\d.]+)", r) if float(x) > -70]
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)
    pk = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)
    out = []
    if i:
        level = float(i[-1])
        if not -18.0 <= level <= -12.0:
            out.append(f"overall loudness {level:.1f} LUFS (should be about -15)")
        if st and max(st) - level > 6.0:
            out.append(f"a loud moment {max(st) - level:.1f} LU above the episode level")
    if pk and float(pk[-1]) > -0.5:
        out.append(f"peaks reach {float(pk[-1]):.1f} dBFS (risk of distortion)")
    return out


def words(qa_dir: Path) -> tuple[list[str], list[str]]:
    """W1: transcribe each line from the voice track and compare with the script (free, local faster-whisper)."""
    if not WHISPER_PY.exists():
        return [], ["word check skipped: no local transcriber found"]
    r = subprocess.run([str(WHISPER_PY), str(ROOT / "check_lines.py"), "--qa", str(qa_dir)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    bad = [l.strip() for l in r.stdout.splitlines() if l.startswith("BAD")]
    return bad, ([] if r.returncode in (0, 1) else [f"word check crashed: {r.stderr[-300:]}"])


def _gemini(parts: list[dict]) -> dict:
    from stories import gemini
    model = gemini.text_model()
    out = gemini._post(f"{gemini.API}/models/{model}:generateContent", {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}})
    txt = "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"])
    return json.loads(re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip())


SHOT_REVIEW = """You are the animation supervisor on a professional adult animated series. Be strict: the owner rejects
anything that looks like cheap AI video. The image is one shot, left to right and top to bottom, 4 frames a second.
The script for this shot says: {motion}
{who}
Check: (1) anyone or anything teleporting or popping to a new place; (2) a character, creature or prop changing size
or being the wrong size for what it is; (3) faces, hair, bodies or outfits morphing or changing; (4) extra or missing
limbs, melted hands, warped faces; (5) text, letters or captions drawn into the picture; (6) the scripted action does
not happen or is unclear; (7) jittery, stiff or confusing movement; (8) the background changing.
Answer JSON: {{"problems": [{{"severity": "severe"|"minor", "what": "<one plain sentence>"}}]}}. Severe means a viewer
would notice it at normal speed. Empty list if the shot is clean."""

LINE_REVIEW = """You are the sound supervisor on a professional animated series. Listen to this one line of dialogue.
Script: {who} says "{text}". {shout}
Report only real problems a viewer would notice: (1) shouting or yelling when the script doesn't call for it;
(2) clicks, pops, static, hiss, crackle or distortion; (3) words cut off, mumbled or different from the script;
(4) the voice suddenly much louder or softer inside the line; (5) robotic or glitchy voice.
Answer JSON: {{"problems": [{{"severity": "severe"|"minor", "what": "<one plain sentence>"}}]}}. Empty list if clean."""


def ai_shots(shots: list[dict], src: Path, qa_dir: Path, notes: dict | None = None) -> tuple[list[str], list[str]]:
    """notes: cast.yaml design notes, so designed features (a white feather) aren't reported as glitches."""
    severe, minor = [], []
    notes = notes or {}
    for i, shot in enumerate(shots, 1):
        sheet = qa_dir / f"shot{i}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src / f"shot{i}.mp4"), "-vf",
                        "fps=4,scale=180:-1,tile=8x3", "-frames:v", "1", "-q:v", "4", str(sheet)], check=True)
        who = f"On screen: {', '.join(shot.get('cast', []))}." if shot.get("cast") else "No characters in the script."
        who += "".join(f" Design of {c} (correct, not a glitch): {' '.join(str(notes[c]).split())}" for c in
                       shot.get("cast", []) if c in notes)
        try:
            res = _gemini([{"text": SHOT_REVIEW.format(motion=shot.get("motion", ""), who=who)},
                           {"inline_data": {"mime_type": "image/jpeg",
                                            "data": base64.b64encode(sheet.read_bytes()).decode()}}])
        except Exception as e:                          # a review that can't run is a failure, never a silent pass
            severe.append(f"shot {i}: picture review could not run ({e})")
            continue
        for p in res.get("problems", []):
            (severe if p.get("severity") == "severe" else minor).append(f"shot {i}: {p.get('what')}")
    return severe, minor


def ai_lines(speech: np.ndarray, rate: int, lines: list[dict], qa_dir: Path) -> tuple[list[str], list[str]]:
    severe, minor = [], []
    for ln in lines:
        f = qa_dir / f"line{ln['shot']}.wav"
        sf.write(f, speech[int(ln["start"] * rate):int(ln["end"] * rate)], rate)
        try:
            res = _gemini([{"text": LINE_REVIEW.format(who=ln["who"], text=ln["text"],
                                                       shout="The script says they shout." if ln.get("shout") else
                                                       "They should speak at a normal volume.")},
                           {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(f.read_bytes()).decode()}}])
        except Exception as e:
            severe.append(f"shot {ln['shot']} line: sound review could not run ({e})")
            continue
        for p in res.get("problems", []):
            (severe if p.get("severity") == "severe" else minor).append(f"shot {ln['shot']} ({ln['who']}): {p.get('what')}")
    return severe, minor


def gate(slug: str, ep: str = "ep1", ai: bool = True) -> bool:
    import voice
    shots = yaml.safe_load((ROOT / slug / "cartoon" / f"{ep}.yaml").read_text(encoding="utf-8"))["shots"]
    src = ROOT / "out" / "cartoon" / f"{slug}-{ep}"
    qa_dir = ROOT / "out" / "qa" / f"{slug}-{ep}"
    out_dir = ROOT / "out" / "cartoon"
    final = next((p for p in (out_dir / f"{slug}-{ep}-final.mp4", out_dir / f"{slug}-{ep}-voiced.mp4") if p.exists()), None)
    if not final or not (qa_dir / "lines.json").exists():
        print("nothing to check: render the episode first (python render.py)")
        return False
    (qa_dir / "PASS.json").unlink(missing_ok=True)
    fail, warn = [], []
    # pictures
    prev_last = None
    for i, shot in enumerate(shots, 1):
        f = frames(src / f"shot{i}.mp4")
        fail += [f"shot {i}: {p}" for p in jumps(f)]
        if shot.get("continues") and prev_last is not None:
            d = float(np.abs(f[0] - prev_last).mean())
            if d > 8.0:
                fail.append(f"shot {i} doesn't start where shot {i - 1} ended (difference {d:.1f})")
        prev_last = f[-1]
    # sound
    speech, rate = sf.read(qa_dir / "speech.wav", dtype="float32")
    lines = json.loads((qa_dir / "lines.json").read_text(encoding="utf-8"))
    fail += [f"sound: {p}" for p in voice.audio_check(final, label=final.name)]
    fail += [f"talking over: {p}" for p in overlaps(lines)]
    fail += [f"loudness: {p}" for p in loudness(speech, lines, rate)]
    fail += [f"loudness: {p}" for p in spikes(final)]
    bad, notes = words(qa_dir)
    fail += [f"words: {p}" for p in bad]
    warn += notes
    if ai:
        castf = ROOT / slug / "cartoon" / "cast.yaml"
        notes = (yaml.safe_load(castf.read_text(encoding="utf-8")) or {}) if castf.exists() else {}
        s, m = ai_shots(shots, src, qa_dir, notes)
        fail += [f"picture: {p}" for p in s]
        warn += [f"picture: {p}" for p in m]
        s, m = ai_lines(speech, rate, lines, qa_dir)
        fail += [f"voice: {p}" for p in s]
        warn += [f"voice: {p}" for p in m]
    else:
        warn.append("Gemini picture and voice review skipped (--no-ai): not a full pass")
    ok = not fail and ai
    report = [f"# QA {slug} {ep}: {'PASS' if ok else 'FAIL'}", "", f"File: {final.name}", "",
              "## Must fix" if fail else "## Must fix: nothing", *[f"- {p}" for p in fail], "",
              "## Worth a look (minor)", *([f"- {p}" for p in warn] or ["- nothing"])]
    (qa_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    failed_name = final.with_name(final.stem + ".QA-FAILED.mp4")
    if ok:
        failed_name.unlink(missing_ok=True)
        (qa_dir / "PASS.json").write_text(json.dumps({"file": final.name, "size": final.stat().st_size}), encoding="utf-8")
    elif fail:
        final.replace(failed_name)                       # a failed episode can't be sent or posted by mistake
    print("\n".join(report))
    return ok


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(0 if gate(*args, ai="--no-ai" not in sys.argv) else 1)
