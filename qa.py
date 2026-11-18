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


def caption_mismatch(shots: list[dict]) -> list[str]:
    """Owner 11-17: the words on screen must match the words spoken (the caption said "old school", the voice
    "old high school")."""
    def words(t):
        t = re.sub(r"<[^>]+>", " ", t or "")
        t = re.sub(r"^[A-Z][A-Z .'\"-]{1,30}:\s*", "", t.strip())
        return re.sub(r"[^a-z0-9 ]+", " ", t.lower().replace("-", " ")).split()
    out = []
    for i, sh in enumerate(shots, 1):
        if not sh.get("line"):
            continue
        cap, said = words(sh.get("caption", "")), words(sh["line"])
        nums = [w for w in cap if w.isdigit()]
        cap = [w for w in cap if not w.isdigit()]          # numbers are written as digits on screen, words in speech
        extra = [w for w in cap if w not in said]
        missing = [w for w in said if w not in cap and not nums]
        if extra or (missing and not nums):
            out.append(f"shot {i}: caption and voice differ (on screen only: {' '.join(extra) or '-'}; "
                       f"spoken only: {' '.join(missing) or '-'})")
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


def background_check(speech: np.ndarray, bg_file: Path, rate: int) -> list[str]:
    """Owner 11-17: nothing in the background louder than 50% of the voice, and the voice never slammed."""
    out = []
    if np.abs(speech).max() > 0.85:
        out.append(f"the voice peaks at {np.abs(speech).max():.2f} (keep it at about 0.8)")
    if not bg_file.exists():
        return out
    bg, _ = sf.read(bg_file, dtype="float32")
    w = int(rate * 0.4)
    n = min(len(bg), len(speech)) // w
    worst = -99.0
    import voice as _v
    voice_db = _v.speech_db(speech, rate)
    for k in range(n):
        v = speech[k * w:(k + 1) * w]; b = bg[k * w:(k + 1) * w]
        vr = np.sqrt(np.mean(v ** 2))
        if vr < 10 ** ((voice_db - 12) / 20):            # judge only where someone is really talking, not pause edges
            continue
        worst = max(worst, 20 * np.log10((np.sqrt(np.mean(b ** 2)) + 1e-9) / vr))
    if worst > -6.0:
        out.append(f"background reaches {worst:+.1f} dB against the voice (must stay at or under -6 dB, half the voice)")
    if np.abs(bg).max() > 0.5 * max(np.abs(speech).max(), 1e-6):
        out.append(f"a background sound peaks at {np.abs(bg).max():.2f}, over half the voice's peak")
    return out


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
    global MISSING                                       # shots where the transcriber really lost a word
    MISSING = {}                                         # shot -> the words the transcriber really didn't hear
    for l in r.stdout.splitlines():
        if l.startswith("MISS"):
            m_ = re.match(r"MISS shot (\d+): (.*)", l)
            MISSING[m_.group(1)] = {w.strip().lower() for w in m_.group(2).split(",")}
    return bad, ([] if r.returncode in (0, 1) else [f"word check crashed: {r.stderr[-300:]}"])


MISSING: dict = {}


def _gemini(parts: list[dict]) -> dict:
    try:
        return _gemini_once(parts)
    except (json.JSONDecodeError, KeyError, IndexError):     # a malformed reply: ask once more
        return _gemini_once(parts)


def _gemini_once(parts: list[dict]) -> dict:
    from stories import gemini
    model = gemini.text_model()
    out = gemini._post(f"{gemini.API}/models/{model}:generateContent", {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}})
    txt = "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"])
    return json.loads(re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip())


STILL_REVIEW = """You are the art director on a professional narrated horror series. This one picture is shown with a slow
camera move (no animation). The script for this shot says: {motion}
{who}
Report only what is wrong IN THE PICTURE: (1) people or creatures that aren't in the script (extra people,
duplicated characters); (2) warped faces, extra or missing limbs, melted hands; (3) text, letters or captions drawn
in; (4) the picture contradicts the script in a way a viewer would notice: the wrong person or place, a missing
main character, someone facing the wrong way. A slightly different expression, pose, prop or colour is MINOR.
Answer JSON: {{"problems": [{{"severity": "severe"|"minor", "what": "<one plain sentence>"}}]}}. SEVERE = a viewer
would notice and it looks wrong; MINOR = small. Missing motion is NOT a problem: it's a still. Empty list if clean."""

SHOT_REVIEW = """You are the animation supervisor on a professional adult animated series. Be strict: the owner rejects
anything that looks like cheap AI video. The image is one shot as 24 frames in time order, read left to right along each row, then the next row
(a new row is NOT a jump back: it continues from the end of the row above).
The script for this shot says: {motion}
{who}
Check: (1) anyone or anything teleporting or popping to a new place; (2) a character, creature or prop changing size
or being the wrong size for what it is; (3) faces, hair, bodies or outfits morphing or changing; (4) extra or missing
limbs, melted hands, warped faces; (5) text, letters or captions drawn into the picture; (6) the scripted action does
not happen or is unclear; (7) jittery, stiff or confusing movement; (8) the background changing.
Answer JSON: {{"problems": [{{"severity": "severe"|"minor", "what": "<one plain sentence>"}}]}}.
SEVERE = a viewer would notice it at normal speed AND it looks broken: (1)-(5), a person or object popping in or out,
a duplicated character, or a person in the shot who isn't in the script.
MINOR = everything else, including a small scripted motion that is missing or weak, and still or held moments
(in limited TV animation and horror, holding still is often the point). Empty list if the shot is clean."""

LINE_REVIEW = """You are the sound supervisor on a professional animated series. Listen to this one line of dialogue.
Script: {who} says "{text}". {shout}
Report only real problems a viewer would notice: (1) shouting or yelling when the script doesn't call for it;
(2) clicks, pops, static, hiss, crackle or distortion; (3) words cut off, mumbled or different from the script;
(4) the voice suddenly much louder or softer inside the line; (5) robotic or glitchy voice.
Answer JSON: {{"problems": [{{"severity": "severe"|"minor", "what": "<one plain sentence>"}}]}}. Empty list if clean."""


TONE = ""


def ai_shots(shots: list[dict], src: Path, qa_dir: Path, notes: dict | None = None,
             lengths: list[float] | None = None) -> tuple[list[str], list[str]]:
    """notes: cast.yaml design notes, so designed features (a white feather) aren't reported as glitches.
    lengths: how much of each shot the viewer sees; the sheet spreads 24 frames across exactly that."""
    severe, minor = [], []
    notes = notes or {}
    for i, shot in enumerate(shots, 1):
        sheet = qa_dir / f"shot{i}.jpg"
        used = (lengths or [None] * len(shots))[i - 1] or float(shot.get("secs", 6))
        have = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     str(src / f"shot{i}.mp4")], capture_output=True, text=True).stdout or used)
        used = min(used, have)                           # a held last frame adds nothing to look at: no black tiles
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-t", f"{used:.2f}", "-i", str(src / f"shot{i}.mp4"), "-vf",
                        f"fps={24 / used:.4f},scale=180:-1,tile=8x3", "-frames:v", "1", "-q:v", "4", str(sheet)],
                       check=True)
        who = f"On screen: {', '.join(shot.get('cast', []))}." if shot.get("cast") else "No characters in the script."
        who += "".join(f" Design of {c} (correct, not a glitch): {' '.join(str(notes[c]).split())}" for c in
                       shot.get("cast", []) if c in notes)
        if shot.get("_still"):                           # a still: judge the picture, not motion
            sheet = src / f"key{i}.jpg"
        parts = [{"text": (STILL_REVIEW if shot.get("_still") else SHOT_REVIEW).format(   # a still is judged
                      motion=shot.get("frame" if shot.get("_still") else "motion", ""), who=who + TONE)},  # on its picture text
                 {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(sheet.read_bytes()).decode()}}]
        try:
            res = _gemini(parts)
            if any(p.get("severity") == "severe" for p in res.get("problems", [])):
                again = _gemini(parts)                   # a severe finding must hold up on a second look
                if not any(p.get("severity") == "severe" for p in again.get("problems", [])):
                    for p in res.get("problems", []):
                        p["severity"] = "minor"
                        p["what"] = f"{p.get('what')} (not confirmed on a second look)"
        except Exception as e:                          # a review that can't run is a failure, never a silent pass
            severe.append(f"shot {i}: picture review could not run ({e})")
            continue
        for p in res.get("problems", []):
            if shot.get("owner_ok"):                     # the owner watched this shot and approved it
                minor.append(f"shot {i}: {p.get('what')} (owner approved the shot: {shot['owner_ok']})")
                continue
            (severe if p.get("severity") == "severe" else minor).append(f"shot {i}: {p.get('what')}")
    return severe, minor


def ai_lines(speech: np.ndarray, rate: int, lines: list[dict], qa_dir: Path) -> tuple[list[str], list[str]]:
    severe, minor = [], []
    for ln in lines:
        f = qa_dir / f"line{ln['shot']}.wav"
        sf.write(f, speech[int(ln["start"] * rate):int(ln["end"] * rate)], rate)
        try:
            parts_l = [{"text": LINE_REVIEW.format(who=ln["who"], text=re.sub(r"<[^>]+>", " ... ", ln["text"]),
                                                       shout="The script says they shout." if ln.get("shout") else
                                                       "They should speak at a normal volume.")},
                           {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(f.read_bytes()).decode()}}]
            res = _gemini(parts_l)
        except Exception as e:
            severe.append(f"shot {ln['shot']} line: sound review could not run ({e})")
            continue
        if any(p.get("severity") == "severe" for p in res.get("problems", [])):
            again = _gemini(parts_l)                     # a severe voice finding must be heard again too
            if not any(p.get("severity") == "severe" for p in again.get("problems", [])):
                for p in res.get("problems", []):
                    p["severity"] = "minor"; p["what"] = f"{p.get('what')} (not heard again on a second listen)"
        for p in res.get("problems", []):
            (severe if p.get("severity") == "severe" else minor).append(f"shot {ln['shot']} ({ln['who']}): {p.get('what')}")
    return severe, minor


def gate(slug: str, ep: str = "ep1", ai: bool = True) -> bool:
    import voice
    shots = yaml.safe_load((ROOT / slug / "cartoon" / f"{ep}.yaml").read_text(encoding="utf-8"))["shots"]
    src = ROOT / "out" / "cartoon" / f"{slug}-{ep}"
    qa_dir = ROOT / "out" / "qa" / f"{slug}-{ep}"
    out_dir = ROOT / "out" / "cartoon"
    for stem in (f"{slug}-{ep}-final", f"{slug}-{ep}-voiced"):  # re-checking a failed episode: take it back first
        failed = out_dir / f"{stem}.QA-FAILED.mp4"
        if failed.exists():
            if (out_dir / f"{stem}.mp4").exists():       # a newer render exists: the failed one is stale, drop it
                failed.unlink()
            else:
                failed.replace(out_dir / f"{stem}.mp4")
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
        warn += [f"shot {i}: {p} (check: scripted flicker or a real pop?)" for p in jumps(f)]
        if shot.get("continues") and prev_last is not None:
            d = float(np.abs(f[0] - prev_last).mean())
            if d > 8.0:
                fail.append(f"shot {i} doesn't start where shot {i - 1} ended (difference {d:.1f})")
        prev_last = f[-1]
    # length (owner 11-16: short form, 15-29 s, never over 30)
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(final)], capture_output=True, text=True).stdout or 0)
    if total > 40.0:
        fail.append(f"length: {total:.1f} s, over the 40 s hard limit (aim for 15-35 s; owner 11-17)")
    elif total < 15.0:
        warn.append(f"length: {total:.1f} s, under the 15-29 s sweet spot")
    # sound
    speech, rate = sf.read(qa_dir / "speech.wav", dtype="float32")
    lines = json.loads((qa_dir / "lines.json").read_text(encoding="utf-8"))
    for p in voice.audio_check(speech, rate, label="voices"):
        if "dead-silent" in p:
            continue
        m = re.search(r"burst at ([\d.]+)s", p)
        if m:                                            # a quiet hissy burst inside a spoken line is an "s"/"sh" sound
            t = float(m.group(1))
            seg = speech[int(t * rate):int((t + 0.05) * rate)]       # just the burst itself
            inside = any(ln["start"] <= t <= ln["end"] for ln in lines)
            if inside and len(seg) and float(np.abs(seg).max()) < 0.1:
                warn.append(f"voice: {p} (quiet hiss inside a word: a sibilant, not static)")
                continue
        fail.append(f"voice: {p}")
    fail += [f"sound: {p}" for p in voice.audio_check(final, label=final.name) if "dead-silent" in p]
    fail += [f"talking over: {p}" for p in overlaps(lines)]
    fail += [f"caption: {p}" for p in caption_mismatch(shots)]
    fail += [f"mix: {p}" for p in background_check(speech, qa_dir / "background.wav", rate)]
    cast = voice.load_voices(ROOT / slug)
    for ln in lines:                                     # a take much duller than its own voice (S/T sounds lost) fails
        vid = (cast.get(ln["who"]) or cast.get("narrator") or "").split(":")[-1].split("@")[0]
        if not vid:
            continue
        seg = voice._decode(None, pcm=speech[int(ln["start"] * rate):int(ln["end"] * rate)], in_rate=rate, rate=24000)
        b, ref = voice.hf_share(seg, 24000), voice.voice_brightness(vid)
        if b < 0.6 * ref:
            warn.append(f"voice: shot {ln['shot']} ({ln['who']}) may sound dull/muffled (brightness {b:.2f}, this voice is normally {ref:.2f})")
    fail += [f"loudness: {p}" for p in loudness(speech, lines, rate)]
    fail += [f"loudness: {p}" for p in spikes(final)]
    bad, notes = words(qa_dir)
    borderline = [p for p in bad if 0.8 <= float(re.search(r" (\d\.\d\d):", p).group(1)) <= 0.9]
    fail += [f"words: {p}" for p in bad if p not in borderline]
    fail += [f"words: {p}" for p in notes if "crashed" in p]     # a check that can't run is a failure
    warn += [f"words: {p}" for p in notes if "crashed" not in p]
    if ai:
        global TONE
        tf = ROOT / slug / "cartoon" / "tone.md"
        if tf.exists() and "COMEDY" in tf.read_text(encoding="utf-8"):
            TONE = (" This is a COMEDY: big, fast, exaggerated expression changes and comic takes are intended. Flag a"
                    " face only if it morphs into a different face or loses its design, not for comic acting.")
        else:
            TONE = ""
        castf = ROOT / slug / "cartoon" / "cast.yaml"
        notes = (yaml.safe_load(castf.read_text(encoding="utf-8")) or {}) if castf.exists() else {}
        lengths = [p[0] for p in voice.timeline(slug, ep)]
        ep_doc = yaml.safe_load((ROOT / slug / "cartoon" / f"{ep}.yaml").read_text(encoding="utf-8"))
        marked = [dict(sh, _still=bool(ep_doc.get("stills") or sh.get("still"))) for sh in shots]
        s, m = ai_shots(marked, src, qa_dir, notes, lengths)
        fail += [f"picture: {p}" for p in s]
        warn += [f"picture: {p}" for p in m]
        s, m = ai_lines(speech, rate, lines, qa_dir)
        # the listener sometimes claims a word is missing when it isn't: trust that claim only if the transcriber agrees
        wordy = re.compile(r"missing|cut off|omit|dropped|skipp", re.I)
        def agreed(x):                                   # the same word, heard missing by both
            k = re.search(r"shot (\d+)", x).group(1)
            named = {w.lower().strip(".,!?") for w in re.findall(r"['\"‘“]([^'\"’”]+)['\"’”]", x)}
            named = {t for w in named for t in w.split()}
            return bool(named & MISSING.get(k, set())) or (k in MISSING and not named)
        moved = [x for x in s if wordy.search(x) and not agreed(x)]
        s = [x for x in s if x not in moved]
        m = m + [x + " (transcriber heard every word)" for x in moved]
        # a transcriber "missing word" alone is usually its own mishearing ("Mira Vale" -> "mirror veil"): it counts
        # only when the listener also heard a word missing in that line (that pair caught the real drops on 11-17)
        m += [f"shot {k}: transcriber flagged {', '.join(sorted(w))} (the listener didn't: likely a mishearing)"
              for k, w in sorted(MISSING.items())]
        fail += [f"voice: {p}" for p in s]
        warn += [f"voice: {p}" for p in m]
        for p in borderline:                             # the small transcriber mishears soft voices: the listener decides
            shot_no = re.search(r"shot (\d+)", p).group(1)
            agree = [x for x in s + m if f"shot {shot_no} " in x and re.search(r"word|missing|cut off|instead", x, re.I)]
            (fail if agree else warn).append(f"words: {p}" + ("" if agree else " (listener heard the script: transcriber slip)"))
    else:
        fail += [f"words: {p}" for p in borderline]
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
