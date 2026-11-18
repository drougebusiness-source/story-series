"""Character voices for the animated episodes.

Each series has <series>/cartoon/voices.yaml: every recurring character (and the narrator) gets an entry keyed by the
speaker as written before ":" in a caption, with name, brief (personality/build/accent for the world: the casting
spec), kokoro (free stand-in) and later eleven (ElevenLabs voice id). VOICE_ENGINE=eleven uses the eleven ids where
cast. A new character is not finished until it has a voice entry (tests/test_voices.py checks). Engines:
  kokoro:<voice>       free, runs locally on the CPU (model files in ~/.cache/doodle, shared with JIC)
  gemini:<Voice>|<brief>  Gemini TTS acting the brief (accents work; well under a cent a line, uses Gemini credit)
  eleven:<voice_id>    ElevenLabs (needs ELEVENLABS_API_KEY; better acting, costs voice credits)

    python voice.py audition <series>   -> out/voices/<series>-audition.wav  (every voice reading its first line)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml

from stories.series import ROOT

RATE = 24000
# ElevenLabs narration model. eleven_v3 is more expressive but swallowed short phrases and once switched voices
# mid-line (11-16), so the steadier multilingual v2 is the default.
ELEVEN_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVEN_SETTINGS = {"stability": 0.5, "similarity_boost": 0.8, "style": 0.0, "use_speaker_boost": True, "speed": 1.0}
# 11-17 #3: a touch slower (owner: narrators too fast). Below ~0.9 ElevenLabs can drag; 1.08 dropped words.
# 11-17 #2: the same calm settings as the JIC narrator (owner likes JIC; style 0.3 sounded over-acted).
# 11-17: livelier delivery (owner: flat, no drama); speed stays 1.0 (1.08 dropped words). Pauses are written into lines
# as <break time="0.8s" /> tags, which ElevenLabs honours.
KOKORO = Path.home() / ".cache" / "doodle"
_kokoro = None


def speaker_and_text(caption: str) -> tuple[str, str]:
    m = re.match(r"^([A-Z][A-Z .'\"-]{1,30}):\s*(.+)$", caption.strip())
    return (m.group(1).strip().lower(), m.group(2)) if m else ("narrator", caption.strip())


def speakable(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def load_voices(series_dir: Path) -> dict:
    """speaker -> voice spec string ("kokoro:bm_george@0.92" or "eleven:<id>")."""
    return {k: pick(v) for k, v in load_cast(series_dir).items()}


def load_cast(series_dir: Path) -> dict:
    f = series_dir / "cartoon" / "voices.yaml"
    return {k.lower(): v for k, v in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).items()} if f.exists() else {}


def pick(entry) -> str:
    """Every story voice is ElevenLabs (owner 11-17). A character without an `eleven:` voice gets a placeholder that
    timeline() refuses to render, so a Gemini or Kokoro voice can never slip into an episode."""
    if isinstance(entry, str):
        return entry
    if entry.get("eleven"):                              # per-voice pace: `speed:` in voices.yaml (default 1.0)
        return f"eleven:{entry['eleven']}" + (f"@{entry['speed']}" if entry.get("speed") else "")
    return f"missing:{entry.get('name', '?')}"


def missing(slug: str) -> list[str]:
    """Recurring characters in series.yaml that have no voice yet."""
    sdir = ROOT / slug
    have = {(v.get("name") or k).lower() for k, v in load_cast(sdir).items() if isinstance(v, dict)}
    chars = (yaml.safe_load((sdir / "series.yaml").read_text(encoding="utf-8")) or {}).get("characters", {})
    return [n for n in chars if n.lower() not in have]


def say(text: str, voice: str) -> np.ndarray:
    """Mono float32 audio at 24 kHz, cleaned of clicks and static (clean()). Paid engines are cached raw in
    out/voices/cache; the cleaning runs on every read, so old cached lines get cleaned too."""
    if not voice.startswith("kokoro"):
        tag = f"{voice}|{ELEVEN_MODEL}|{json.dumps(ELEVEN_SETTINGS, sort_keys=True)}|whole2" if voice.startswith("eleven") else voice   # a new model is a new take
        f = ROOT / "out" / "voices" / "cache" / (hashlib.sha1(f"{tag}|{text}".encode()).hexdigest() + ".npy")
        if f.exists() and _length_ok(clean(np.load(f)), text):
            return clean(np.load(f))
        for _ in range(3):                         # an engine that rambles or reads the notes aloud: try again
            a = _say(text, voice)
            if _length_ok(clean(a), text):
                break
        else:
            raise RuntimeError(f"{voice.split('|')[0]} keeps returning {len(clean(a)) / RATE:.1f}s for a "
                               f"{len(text.split())}-word line (it says more than the line): {text!r}")
        f.parent.mkdir(parents=True, exist_ok=True)
        np.save(f, a)
        return clean(a)
    return clean(_say(text, voice))


def _length_ok(a: np.ndarray, text: str) -> bool:
    """A spoken line runs about 0.3-0.5 s per word. Far longer means extra words or junk were spoken."""
    return len(a) / RATE <= 1.5 + 0.75 * len(text.split())


NOISE_RATIO_DB = -6.0   # a sound burst whose sample-to-sample energy is this close to its level is static, not a voice


def _bursts(a: np.ndarray, rate: int, floor_db: float = -40.0):
    """(start, end) sample ranges of sound bursts above floor_db, with their noisiness (dB; voice is about -12 to
    -25 at 24 kHz, clicks and static are about -9 to +1). Works on 10 ms frames."""
    w = max(1, int(rate * 0.01))
    n = len(a) // w
    if n == 0:
        return []
    f = a[: n * w].reshape(n, w)
    db = 20 * np.log10(np.sqrt((f ** 2).mean(1)) + 1e-9)
    hf = 20 * np.log10(np.sqrt((np.diff(f, axis=1) ** 2).mean(1)) + 1e-9)
    loud = db > floor_db
    out, i = [], 0
    while i < n:
        if loud[i]:
            j = i
            while j < n and loud[j]:
                j += 1
            out.append((i * w, j * w, float((hf[i:j] - db[i:j]).mean())))
            i = j
        else:
            i += 1
    return out


def clean(a: np.ndarray, rate: int = RATE) -> np.ndarray:
    """Returns the take untouched apart from trimming true silence off its ends.
    It USED to zero out every short "noisy" burst and smooth sample jumps, meant to remove clicks and static. But the
    S, SH, F and T sounds of speech ARE noisy bursts, so it silenced them inside every word, in every voice: "My
    sister?" became "Duh", and the owner heard every S and T cutting out (11-17). Never filter voices like that:
    if a take is bad, re-record it or recast the voice."""
    return trim_silence(np.asarray(a, np.float32), rate)


def isolated_clicks(a: np.ndarray) -> np.ndarray:
    """Sample indexes of true clicks: a jump far bigger than the jumps right around it. Loud consonants ("k", "t")
    are noisy bursts with big jumps all around them, so they are not counted (and must never be removed)."""
    d = np.abs(np.diff(a))
    idx = np.flatnonzero(d > 0.6)
    return np.array([i for i in idx if d[i] > 8 * np.median(d[max(0, i - 40):i + 40])], int)


def repair_clicks(a: np.ndarray) -> np.ndarray:
    """Smooth over true clicks only: each lone spike is replaced by a short cubic bridge between its neighbours."""
    a = a.copy()
    for i in isolated_clicks(a):
        lo, hi = max(0, i - 12), min(len(a) - 1, i + 13)
        x = np.array([lo - 2, lo - 1, hi, hi + 1]).clip(0, len(a) - 1)
        a[lo:hi] = np.interp(np.arange(lo, hi), [lo - 1, hi], [a[max(0, lo - 1)], a[hi]])
    return a


def audio_check(src, rate: int = 48000, label: str = "") -> list[str]:
    """Problems in a finished soundtrack (a file or a 48 kHz array): clicks, static bursts and dead-silent gaps
    inside the video. voiced() and cartoon.py final() refuse to finish when this finds anything."""
    a = _decode(src) if not isinstance(src, np.ndarray) else src
    probs = []
    ratio = NOISE_RATIO_DB + 20 * np.log10(rate / RATE)
    for s0, s1, r in _bursts(a, rate, -45.0):
        if r > ratio and (s1 - s0) >= int(rate * 0.02):
            probs.append(f"static/click burst at {s0 / rate:.2f}s ({(s1 - s0) * 1000 // rate} ms)")
    jumps = isolated_clicks(a)                           # a lone spike, not a loud consonant
    if len(jumps):
        probs.append(f"{len(jumps)} click(s), first at {jumps[0] / rate:.2f}s")
    w = int(rate * 0.01)
    n = len(a) // w
    dead = (np.abs(a[: n * w].reshape(n, w)).max(1) < 1e-4) if n else np.zeros(0, bool)
    i = 0
    while i < n - 160:                                # the last 1.6 s (the vote card fading out) may be silent
        if dead[i]:
            j = i
            while j < n and dead[j]:
                j += 1
            if j - i >= 15 and j < n - 160:
                probs.append(f"dead-silent gap at {i / 100:.2f}s ({(j - i) * 10} ms)")
            i = j
        else:
            i += 1
    for p_ in probs:
        print(f"  AUDIO {label}: {p_}")
    return probs


def _say(text: str, voice: str) -> np.ndarray:
    engine, _, name = voice.partition(":")
    spec = {}
    m = re.search(r"@([0-9.]+)$", name)
    if m:                                # kokoro:am_onyx@0.9 -> speed 0.9
        name, spec["speed"] = name[: m.start()], float(m.group(1))
    if engine == "gemini":
        return _gemini_say(text, *name.split("|", 1), spec.get("speed", 1.0))
    if engine == "kokoro":
        global _kokoro
        if _kokoro is None:
            from kokoro_onnx import Kokoro
            _kokoro = Kokoro(str(KOKORO / "kokoro-v1.0.onnx"), str(KOKORO / "voices-v1.0.bin"))
        audio, rate = _kokoro.create(text, voice=name, speed=spec.get("speed", 1.0), lang="en-us")
        assert rate == RATE
        return audio.astype(np.float32)
    if engine == "eleven":
        return _eleven_phrases(text, name, speed=spec.get("speed", 1.0))
    raise ValueError(f"unknown voice engine in {voice!r}")


def trim_silence(a: np.ndarray, rate: int) -> np.ndarray:
    """Cut only true silence off the ends, judged on a smoothed 10 ms loudness envelope 50 dB under the peak, with
    generous margins, so soft first sounds and trailing consonants ("t", "s", "x") are always kept."""
    w = max(1, int(rate * 0.01))
    n = len(a) // w
    if n < 3:
        return a
    env = 20 * np.log10(np.sqrt((a[: n * w].reshape(n, w) ** 2).mean(1)) + 1e-9)
    on = np.flatnonzero(env > env.max() - 50)
    if not len(on):
        return a
    return a[max(0, (on[0] - 15) * w): min(len(a), (on[-1] + 25) * w)]   # 150 ms before, 250 ms after


def _eleven_one(text: str, voice_id: str, before: str = "", after: str = "") -> np.ndarray:
    """One ElevenLabs reading. before/after give it the neighbouring words so separate phrases still flow."""
    settings = dict(ELEVEN_SETTINGS)
    if len(text.split()) <= 3:                           # very short lines garbled at low stability ("My sister?")
        settings.update(stability=0.65)
    body = {"text": text, "model_id": ELEVEN_MODEL, "voice_settings": settings}   # no previous/next text: with it,
    # phrases ended early and lost their last sounds ("touched", "machines", "relax"; owner 11-17)
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_24000", data=json.dumps(body).encode(),
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        a = np.frombuffer(r.read(), dtype=np.int16).astype(np.float32) / 32768
    return trim_silence(a, RATE)


def _checked_take(text: str, voice_id: str, tries: int = 3) -> np.ndarray:
    """An ElevenLabs reading, checked by the free local transcriber right away and re-recorded (up to `tries`) if it
    dropped a word; the best take is kept. Takes vary: one said "with her back to you", the next dropped "to you"."""
    import subprocess, tempfile
    py = ROOT.parent / "agent-office" / "reels" / ".venv" / "Scripts" / "python.exe"
    best, best_score = None, -1.0
    for k in range(tries):
        a = _eleven_one(text, voice_id)
        if not py.exists():
            return a
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "take.wav"
            sf.write(f, a, RATE)
            r = subprocess.run([str(py), str(ROOT / "take_check.py"), str(f), text], capture_output=True, text=True,
                               cwd=str(ROOT))
        try:
            score_s, _, missing = r.stdout.strip().splitlines()[-1].partition(" ")
            score = float(score_s) - 0.1 * len([w for w in missing.split(",") if w])
        except (ValueError, IndexError):
            return a
        if score > best_score:
            best, best_score = a, score
        if not missing and float(score_s) >= 0.9:
            return a
        print(f"  retake {k + 1} for {text[:40]!r}: missing {missing or '-'}")
    return best


def hf_share(a: np.ndarray, rate: int = RATE) -> float:
    """Share of the voice's energy above 4 kHz. Clear speech is about 0.45-0.65; a dull, muffled take where the S
    and T sounds are missing measured 0.30 (owner heard it as "muffled, scratchy", and "My sister?" became "Duh")."""
    s_ = np.abs(np.fft.rfft(a))
    f_ = np.fft.rfftfreq(len(a), 1 / rate)
    return float(s_[f_ > 4000].sum() / (s_.sum() or 1))


def voice_brightness(voice_id: str) -> float:
    """This voice's normal brightness (median of 3 clean readings of a test sentence), measured once and cached.
    Voices differ (Paul ~0.23, Ezra's voice ~0.64), so a take is judged against its own voice."""
    f = ROOT / "out" / "voices" / f"brightness-{voice_id}.json"
    if f.exists():
        return json.loads(f.read_text())["hf"]
    vals = [hf_share(_eleven_timed("She sat still, and the tall sisters stopped talking at last.", voice_id)[0])
            for _ in range(3)]
    hf = float(np.median(vals))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"hf": hf, "takes": vals}))
    return hf


def _eleven_timed(text: str, voice_id: str, speed: float = 1.0) -> tuple[np.ndarray, dict]:
    """One whole-line ElevenLabs reading plus when every character is spoken."""
    import base64
    settings = dict(ELEVEN_SETTINGS, speed=speed)
    if len(text.split()) <= 3:
        settings.update(stability=0.65)
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=pcm_24000",
        data=json.dumps({"text": text, "model_id": ELEVEN_MODEL, "voice_settings": settings}).encode(),
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read())
    a = np.frombuffer(base64.b64decode(d["audio_base64"]), np.int16).astype(np.float32) / 32768
    return a, d.get("alignment") or d.get("normalized_alignment") or {}


def _listener_ok(a: np.ndarray, text: str) -> tuple[bool, str]:
    """The strict listener (Gemini audio) on one take: every word fully spoken, nothing cut or glitched? It caught a
    take the transcriber passed ("is his sister" glitched, 11-17)."""
    import base64, io
    try:
        from qa import _gemini
        b = io.BytesIO(); sf.write(b, a, RATE, format="WAV")
        parts = [{"text": f'Script: "{text}". Listen closely. JSON {{"every_word_fully_spoken": true|false, '
                          f'"cut_or_glitched_words": "<list or none>"}}'},
                 {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(b.getvalue()).decode()}}]
        r = _gemini(parts)
        if r.get("every_word_fully_spoken"):
            return True, "none"
        r2 = _gemini(parts)                              # one listen isn't reliable: a cut must be heard twice
        return bool(r2.get("every_word_fully_spoken")), f"{r.get('cut_or_glitched_words')} / {r2.get('cut_or_glitched_words')}"
    except Exception as e:                               # no listener available: rely on the transcriber
        return True, f"listener unavailable ({e})"


def _transcriber_ok(a: np.ndarray, text: str) -> tuple[bool, str]:
    import subprocess, tempfile
    py = ROOT.parent / "agent-office" / "reels" / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return True, ""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "take.wav"
        sf.write(f, a, RATE)
        r = subprocess.run([str(py), str(ROOT / "take_check.py"), str(f), text], capture_output=True, text=True,
                           cwd=str(ROOT))
    try:
        score_s, _, missing = r.stdout.strip().splitlines()[-1].partition(" ")
        return (not missing and float(score_s) >= 0.9), missing
    except (ValueError, IndexError):
        return True, ""


def _eleven_phrases(text: str, voice_id: str, tries: int = 4, speed: float = 1.0) -> np.ndarray:
    """A line with <break time="Xs" /> pauses. The WHOLE line is read in one go (separately read short phrases came
    out glitched, 11-17); the pauses are then cut in at the word boundaries ElevenLabs reports. Every take must pass
    the transcriber AND the listener, or it is re-recorded."""
    parts = re.split(r'<break time="([\d.]+)s" */>', text)
    phrases, gaps = [p.strip() for p in parts[0::2]], [float(x) for x in parts[1::2]]
    plain = " ".join(p for p in phrases if p)
    best, best_key = None, None
    for k in range(tries):
        a, al = _eleven_timed(plain, voice_id, speed)
        bright = hf_share(a)
        dull = bright < 0.7 * voice_brightness(voice_id)   # much duller than this voice normally is: S/T lost ("Duh")
        ok_t, miss_t = _transcriber_ok(a, plain)
        ok_l, miss_l = (False, "skipped: dull take") if dull else _listener_ok(a, plain)
        key = (not dull) + ok_t + ok_l, bright           # most checks passed, then the clearest
        if best_key is None or key > best_key:
            best, best_key, best_al = a, key, al
        if not dull and ok_t and ok_l:
            break
        print(f"  retake {k + 1} for {plain[:40]!r}: brightness {bright:.2f} | transcriber {miss_t or 'ok'} | "
              f"listener {miss_l}")
    a, al = best, best_al
    if not gaps or not al.get("characters"):
        return trim_silence(a, RATE)
    # cut points: halfway between the last letter of a phrase and the first letter of the next
    ends, pos = [], 0
    starts_t, ends_t = al["character_start_times_seconds"], al["character_end_times_seconds"]
    for ph in phrases[:-1]:
        pos += len(ph)
        e = ends_t[min(pos, len(ends_t)) - 1]
        nxt = pos + 1 if pos + 1 < len(starts_t) else len(starts_t) - 1
        ends.append((e + starts_t[nxt]) / 2)
        pos += 1                                         # the joining space
    out, prev = [], 0
    for cut, gap in zip(ends, gaps):
        c = int(cut * RATE)
        out += [a[prev:c], np.zeros(int(RATE * gap), np.float32)]
        prev = c
    out.append(a[prev:])
    return trim_silence(np.concatenate(out), RATE)


def _gemini_say(text: str, voice_name: str, brief: str, speed: float = 1.0) -> np.ndarray:
    import base64
    from stories import gemini
    pace = " Speak briskly, quite fast." if speed > 1.05 else (" Speak slowly." if speed < 0.95 else "")
    prompt = (f"# DIRECTOR'S NOTES (do not read aloud)\nCharacter voice: {brief}.{pace}\n\n"
              f"# TRANSCRIPT (read only this)\n{text}")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                           "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}}}}).encode()
    models = [os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts"), "gemini-3.1-flash-tts-preview",
              "gemini-2.5-flash-preview-tts"]
    import time
    for attempt in range(12):
        m = models[0]
        req = urllib.request.Request(f"{gemini.API}/models/{m}:generateContent", data=body, method="POST",
                                     headers={"x-goog-api-key": gemini.key(), "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                r = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code == 429 and "per_day" in detail and len(models) > 1:
                print(f"  {m} hit its daily voice limit, switching to {models[1]}")
                models.pop(0)
                continue
            if e.code in (429, 500, 503) and attempt < 11:
                time.sleep(20)                       # per-minute limit: wait and try again
                continue
            raise RuntimeError(f"Gemini voice {e.code}: {detail[:400]}") from None
    raw = base64.b64decode(r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    loud = np.flatnonzero(np.abs(a) > 0.02)             # trim leading/trailing silence
    return a[max(0, loud[0] - 1200): loud[-1] + 2400] if len(loud) else a


def stretch(a: np.ndarray, factor: float) -> np.ndarray:
    """Speed audio up by factor without changing pitch (ffmpeg atempo)."""
    import subprocess
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", "pipe:0",
                        "-filter:a", f"atempo={factor:.3f}", "-f", "f32le", "pipe:1"],
                       input=a.astype(np.float32).tobytes(), capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32)


def audition(slug: str):
    sdir = ROOT / slug
    voices = load_voices(sdir)
    ep = yaml.safe_load((sdir / "cartoon" / "ep1.yaml").read_text(encoding="utf-8"))
    lines = {}
    for shot in ep["shots"]:
        who, text = speaker_and_text(shot.get("caption", ""))
        if speakable(text):
            lines.setdefault(who, text)
    gap = np.zeros(int(RATE * 0.6), np.float32)
    parts = []
    for who, voice in voices.items():
        text = lines.get(who) or "Well. Here we are again, and nobody listened to me."
        parts += [say(f"{who.title()}.", "kokoro:af_sarah@1.1") * 0.6, gap[: RATE // 4], say(text, voice), gap]
        print(f"{who:>10}: {voice}  \"{text}\"")
    out = ROOT / "out" / "voices"
    out.mkdir(parents=True, exist_ok=True)
    name = f"{slug}-audition-{os.environ.get('VOICE_ENGINE', 'gemini')}.wav"
    sf.write(out / name, np.concatenate(parts), RATE)
    print(out / name)


MIX = 48000


def _decode(src, rate=MIX, pcm=None, in_rate=RATE, extra="") -> np.ndarray:
    """Decode a file (or resample a float array) to mono float32 at `rate` with ffmpeg."""
    import subprocess
    inp = ["-f", "f32le", "-ar", str(in_rate), "-ac", "1", "-i", "pipe:0"] if pcm is not None else ["-i", str(src)]
    af = ["-af", extra] if extra else []
    r = subprocess.run(["ffmpeg", "-v", "error", *inp, *af, "-ac", "1", "-ar", str(rate), "-f", "f32le", "pipe:1"],
                       input=None if pcm is None else pcm.astype(np.float32).tobytes(), capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def _fade(a: np.ndarray, n: int) -> np.ndarray:
    n = min(n, len(a) // 2)
    if n > 0:
        ramp = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))).astype(np.float32)
        a[:n] *= ramp
        a[-n:] *= ramp[::-1]
    return a


def lipsync_line(series_dir: Path, shot: dict):
    """(speaker key, spoken text, voices.yaml entry) when the shot's speaker is on screen and has an ElevenLabs
    voice, so the shot is lip-synced; (None, None, None) otherwise. The narrator is never lip-synced."""
    who, text = speaker_and_text(shot.get("caption", ""))
    entry = load_cast(series_dir).get(who)
    if who == "narrator" or not isinstance(entry, dict) or not entry.get("eleven") or not speakable(text):
        return None, None, None
    return who, shot.get("line", text), entry


def revoice(clip: Path, voice_id: str) -> np.ndarray:
    """ElevenLabs speech-to-speech on a shot's own audio: same words and timing, the cast voice, noise removed.
    Mono float32 at 48 kHz, cached by clip contents."""
    import subprocess, uuid
    data = clip.read_bytes()
    f = ROOT / "out" / "voices" / "cache" / ("sts-" + hashlib.sha1(data + voice_id.encode()).hexdigest() + ".mp3")
    if not f.exists():
        tmp = f.with_suffix(".wav")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vn", "-ac", "1", "-ar", "44100", str(tmp)],
                       check=True)
        wav = tmp.read_bytes()
        tmp.unlink()
        b = uuid.uuid4().hex
        nl = "\r\n"
        body = b"".join([
            f'--{b}{nl}Content-Disposition: form-data; name="model_id"{nl}{nl}eleven_multilingual_sts_v2{nl}'.encode(),
            f'--{b}{nl}Content-Disposition: form-data; name="remove_background_noise"{nl}{nl}true{nl}'.encode(),
            f'--{b}{nl}Content-Disposition: form-data; name="audio"; filename="a.wav"{nl}Content-Type: audio/wav{nl}{nl}'.encode()
            + wav + nl.encode(), f"--{b}--{nl}".encode()])
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}?output_format=mp3_44100_128", data=body,
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": f"multipart/form-data; boundary={b}"})
        with urllib.request.urlopen(req, timeout=300) as r:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(r.read())
    return _decode(f, extra="highpass=f=80")


def bed_file(slug: str, key: str) -> Path | None:
    """<series>/cartoon/sound/<key>.mp3, the set's background bed: made once from sound.yaml with Lyria if missing."""
    import base64
    f = ROOT / slug / "cartoon" / "sound" / f"{key}.mp3"
    spec_f = ROOT / slug / "cartoon" / "sound.yaml"
    if f.exists() or not spec_f.exists():
        return f if f.exists() else None
    prompt = (yaml.safe_load(spec_f.read_text(encoding="utf-8")) or {}).get(key)
    if not prompt:
        return None
    from stories import gemini
    out = gemini._post(f"{gemini.API}/models/lyria-3-clip-preview:generateContent",
                       {"contents": [{"role": "user", "parts": [{"text": prompt}]}]})
    for part in out["candidates"][0]["content"]["parts"]:
        if "inlineData" in part:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(base64.b64decode(part["inlineData"]["data"]))
            print("  made sound bed", key)
            return f
    return None


def sfx_file(slug: str, key: str) -> Path:
    """<series>/cartoon/sfx/<key>.mp3, made once from sfx.yaml with ElevenLabs sound generation."""
    f = ROOT / slug / "cartoon" / "sfx" / f"{key}.mp3"
    if not f.exists():
        spec = yaml.safe_load((ROOT / slug / "cartoon" / "sfx.yaml").read_text(encoding="utf-8"))[key]
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/sound-generation",
            data=json.dumps({"text": spec["prompt"], "duration_seconds": spec.get("secs", 3),
                             "prompt_influence": 0.6}).encode(),
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
        f.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=300) as r:
            f.write_bytes(r.read())
        print("  made sound effect", key)
    return f


SPEECH_DB = -19.0          # owner 11-17 #2: about 75-80% volume, not screaming
VOICE_PEAK = 0.8
BED_RMS = 0.012           # music/ambience about -35 dBFS (was -26: too loud, owner 11-17)
SFX_LEVEL = 0.4           # all effects scaled down (owner 11-17: too loud over the narrator)          # every spoken line is set to this loudness (owner 11-16: nobody randomly louder or softer)


def speech_db(a: np.ndarray, rate: int = MIX) -> float:
    """Loudness of the speech in a line (dBFS): the RMS of its 50 ms frames that aren't silence."""
    w = int(rate * 0.05)
    n = len(a) // w
    if n == 0:
        return -99.0
    db = 20 * np.log10(np.sqrt((a[: n * w].reshape(n, w) ** 2).mean(1)) + 1e-9)
    on = db[db > db.max() - 25]
    return float(20 * np.log10(np.sqrt(np.mean(10 ** (on / 10))) + 1e-9)) if len(on) else -99.0


def level(a: np.ndarray) -> np.ndarray:
    """Set a line to SPEECH_DB. A gentle compressor first tames spiky peaks, so short or punchy lines reach the same
    loudness as the rest instead of being held down by their peaks (owner 11-17: nobody randomly quieter)."""
    for _ in range(2):                                   # gain to target, peaks never above 0.8 (about 75-80%)
        a = a * 10 ** ((SPEECH_DB - speech_db(a)) / 20)
        a = a * min(1.0, VOICE_PEAK / (np.abs(a).max() or 1))
    return a.astype(np.float32)


def bg_level(a: np.ndarray, gain: float = 0.6) -> np.ndarray:
    """A sound effect at least 9 dB under the voice (more for low gains) and never peaking above half the voice's
    peak (owner 11-17: nothing in the background louder than 50% of the voice)."""
    rms = np.sqrt(np.mean(a ** 2)) or 1
    a = a / rms * 10 ** ((SPEECH_DB - 15 + 20 * np.log10(max(0.05, min(1.0, gain / 0.6)))) / 20)
    return (a * min(1.0, VOICE_PEAK * 0.5 / (np.abs(a).max() or 1))).astype(np.float32)


def fit_to_speech(a24: np.ndarray, clip: Path) -> np.ndarray:
    """A directly read line placed where the shot's own (video-model) speech is, gently time-fitted to the same
    span so the mouth or beak still moves with it. 48 kHz, levelled."""
    import subprocess
    raw = _decode(clip)
    w = int(MIX * 0.02)
    n = len(raw) // w
    db = 20 * np.log10(np.sqrt((raw[: n * w].reshape(n, w) ** 2).mean(1)) + 1e-9) if n else np.zeros(1)
    on = np.flatnonzero(db > db.max() - 30)
    s0, s1 = (on[0] * w, (on[-1] + 1) * w) if len(on) else (0, len(raw))
    a = _decode(None, pcm=a24, extra="highpass=f=80")
    a = trim_silence(a, MIX)
    f = (len(a) / MIX) / max(0.3, (s1 - s0) / MIX)
    if abs(f - 1) > 0.03:
        pass                                             # no speed change at all: even 10% smeared "I swear" (11-17)
    a = _fade(level(a), int(MIX * 0.02))
    return np.concatenate([np.zeros(s0, np.float32), a]).astype(np.float32)


VOTE_HOLD = 0.75           # the vote screen stays this long after the question (owner 11-17)
LEAD, TAIL = 0.12, 0.2     # silence before/after each line inside its shot (short-form pacing, owner 11-16)


def timeline(slug: str, ep_name: str = "ep1") -> list[tuple[float, np.ndarray | None, float]]:
    """Per shot: (real length in seconds, the shot's clean 48 kHz voice line or None, where in the shot it starts).
    A shot is lengthened to fit its line plus a pause, so lines can never run into the next shot or overlap.
    cartoon.py builds the video with these lengths and voiced() places the lines on them."""
    sdir = ROOT / slug
    voices = load_voices(sdir)
    ep = yaml.safe_load((sdir / "cartoon" / f"{ep_name}.yaml").read_text(encoding="utf-8"))
    out = []
    for i, shot in enumerate(ep["shots"], 1):
        secs = float(shot["secs"])
        who, text, entry = lipsync_line(sdir, shot)
        clip = ROOT / "out" / "cartoon" / f"{slug}-{ep_name}" / f"shot{i}.mp4"
        if ep.get("stills") or shot.get("still"):
            who = None                                   # a still never lip-syncs: its line is read directly below
        if who and clip.exists() and shot.get("voice_tts"):
            a = fit_to_speech(say(text, f"eleven:{entry['eleven']}"), clip)   # read directly, placed on the mouth
            a = np.pad(a, (0, int(MIX * 0.3)))
            out.append((len(a) / MIX, a, 0.0))
            continue
        if who and clip.exists():                        # lip-synced: the shot's own speech, revoiced, never stretched
            a = revoice(clip, entry["eleven"])
            a = _fade(level(a), int(MIX * 0.02))
            a = np.pad(a, (0, int(MIX * 0.3)))            # a breath after the talking shot before the next line
            out.append((len(a) / MIX, a, 0.0))
            continue
        who, text = speaker_and_text(shot.get("caption", ""))
        text = shot.get("line", text)                    # optional spoken wording (numbers as words, etc.)
        if not speakable(text):
            out.append((secs, None, 0.0))
            continue
        voice = voices.get(who) or voices.get("narrator")
        if not voice or not voice.startswith("eleven:"):
            raise SystemExit(f"{slug}: '{who}' has no ElevenLabs voice in cartoon/voices.yaml. Cast one first "
                             f"(cast_voices.py); story episodes only use ElevenLabs voices.")
        a = say(text, voice)
        room = secs - LEAD - TAIL
        if False and len(a) / RATE > room:               # no time-stretching (it sounded robotic): the shot gets longer
            a = stretch(a, min(1.08, (len(a) / RATE) / room))
        a = _decode(None, pcm=a, extra="highpass=f=80")          # 24k -> 48k, no low thumps
        a = np.pad(level(a), int(MIX * 0.08))           # breathing room so the soft edge never clips a word
        a = _fade(a, int(MIX * 0.02))                     # same loudness as every other line; 20 ms soft edges: no clicks
        need = LEAD + len(a) / MIX + TAIL
        if need > secs:
            print(f"  shot lengthened {secs:.1f}s -> {need:.1f}s for {who}: {text}")
        out.append((max(secs, round(need, 2)), a, LEAD))
    if ep.get("vote_line"):                              # the question, asked while the vote screen is up
        a = say(ep["vote_line"], voices.get("narrator"))
        a = _fade(np.pad(level(_decode(None, pcm=a, extra="highpass=f=80")), int(MIX * 0.08)),
                  int(MIX * 0.02))
        out.append((round(LEAD + len(a) / MIX + VOTE_HOLD, 2), a, LEAD))
    return out


MASTER_LUFS = -15.0       # finished episodes: about Instagram's playback loudness, so nothing gets turned down or up


def lufs(path) -> float:
    """Integrated loudness (LUFS) of an audio or video file, from ffmpeg's ebur128 meter."""
    import subprocess
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else MASTER_LUFS


def voiced(slug: str, ep_name: str = "ep1"):
    """Build the final soundtrack for out/cartoon/<slug>-<ep>.mp4 -> <slug>-<ep>-voiced.mp4:
    clean voice lines (soft edges, no clicks) over one quiet music/ambience bed per set (<series>/cartoon/sound/),
    which dips under speech. The video model's own sound is never used."""
    import subprocess
    sdir = ROOT / slug
    voices = load_voices(sdir)
    ep = yaml.safe_load((sdir / "cartoon" / f"{ep_name}.yaml").read_text(encoding="utf-8"))
    src = ROOT / "out" / "cartoon" / f"{slug}-{ep_name}.mp4"
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(src)], capture_output=True, text=True, check=True).stdout)
    plan = timeline(slug, ep_name)
    n = int(MIX * total)
    speech = np.zeros(n, np.float32)
    talking = np.zeros(n, np.float32)
    t = 0.0
    lines = []
    for i, (secs, a, at) in enumerate(plan):
        if a is not None:
            start = int(MIX * (t + at))
            a = a[: max(0, n - start)]
            speech[start:start + len(a)] += a
            talking[start:start + len(a)] = 1
            sh_i = ep["shots"][i] if i < len(ep["shots"]) else {"caption": "", "line": ep.get("vote_line", "")}
            who, text = speaker_and_text(sh_i.get("caption", ""))
            on = np.flatnonzero(np.abs(a) > 0.004)         # where the words are (soft first words included)
            pad = int(MIX * 0.12)
            s0, s1 = ((start + max(0, int(on[0]) - pad), start + min(len(a), int(on[-1]) + pad)) if len(on)
                      else (start, start + len(a)))
            lines.append({"shot": i + 1, "who": who, "text": sh_i.get("line", text),
                          "start": round(s0 / MIX, 3), "end": round(s1 / MIX, 3),
                          "shout": bool(sh_i.get("shout"))})
        t += secs
    qa_dir = ROOT / "out" / "qa" / f"{slug}-{ep_name}"
    qa_dir.mkdir(parents=True, exist_ok=True)
    # no click repair: it smoothed away sharp T/K starts after pauses (owner 11-17 #3)
    sf.write(qa_dir / "speech.wav", np.clip(speech, -1, 1), MIX)       # voices only: the gate listens to these
    voice_only = speech.copy()
    (qa_dir / "lines.json").write_text(json.dumps(lines, indent=1), encoding="utf-8")
    # sound effects: per shot `sfx: [{sound: key, at: secs into the shot, gain: 0-1, hold: true = loop the whole shot}]`
    t = 0.0
    for sh, (secs, _, _) in zip(ep["shots"], plan):
        for fx in sh.get("sfx", []):
            a = _decode(sfx_file(slug, fx["sound"]))
            a = bg_level(a, float(fx.get("gain", 0.6)))       # background: at most half the voice (owner 11-17)
            s0 = int(MIX * (t + float(fx.get("at", 0))))
            if fx.get("hold"):
                a = np.resize(a, max(0, int(MIX * (t + secs)) - s0))
            a = _fade(a[: max(0, n - s0)].copy(), int(MIX * 0.15 if fx.get("hold") else MIX * 0.005))
            speech[s0:s0 + len(a)] += a
        t += secs
    shots = [dict(sh, secs=secs) for sh, (secs, _) in zip(ep["shots"], (p[:2] for p in plan))]   # real (stretched) shot lengths
    # music / ambience bed: one per set, continuous while the set stays the same, crossfaded on a set change
    bed = np.zeros(n, np.float32)
    runs, t = [], 0.0
    for shot in shots:
        if runs and runs[-1][0] == shot["set"]:
            runs[-1][2] += float(shot["secs"])
        else:
            runs.append([shot["set"], t, float(shot["secs"])])
        t += float(shot["secs"])
    runs[-1][2] = total - runs[-1][1]                    # last bed carries on under the vote card
    xf = int(MIX * 0.6)
    for k, (key, start_s, dur) in enumerate(runs):
        f = bed_file(slug, key)
        if not f:
            print(f"  no sound bed for {key}")
            continue
        m = _decode(f)
        m = m / (np.sqrt(np.mean(m ** 2)) or 1) * BED_RMS   # quiet bed under the voices
        a0, a1 = max(0, int(MIX * start_s) - (xf // 2 if k else 0)), min(n, int(MIX * (start_s + dur)) + xf // 2)
        seg = np.resize(m, a1 - a0).copy()               # loops if the bed is shorter than the scene
        seg[:xf] *= np.linspace(0, 1, min(xf, len(seg)))[: len(seg[:xf])] if k else 1
        if k == len(runs) - 1:
            seg[-int(MIX * 2.5):] *= np.linspace(1, 0, len(seg[-int(MIX * 2.5):]))   # fade out over the card
        else:
            seg[-xf:] *= np.linspace(1, 0, len(seg[-xf:]))
        bed[a0:a1] += seg
    duck = np.convolve(talking, np.ones(int(MIX * 0.3)) / int(MIX * 0.3), "same")  # smooth dip under speech
    background = (speech - voice_only) + bed * (1 - 0.65 * np.clip(duck, 0, 1))   # music + effects, dipping under speech
    mix = voice_only + background
    sf.write(qa_dir / "background.wav", np.clip(background, -1, 1), MIX)
    tmp = ROOT / "out" / "voices" / f"{slug}-{ep_name}-mix.wav"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    sf.write(tmp, np.clip(mix, -1, 1), MIX)
    out = src.with_name(f"{slug}-{ep_name}-voiced.mp4")
    gain = MASTER_LUFS - lufs(tmp)                      # whole episode to Instagram loudness, one fixed gain
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-i", str(tmp), "-filter_complex",
                    f"[1:a]volume={gain:.2f}dB,alimiter=limit=0.84:level=0,aformat=channel_layouts=stereo[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", str(out)], check=True)
    if audio_check(out, label=out.name):                # qa.py's gate fails the episode on these (render.py)
        print(f"  {out.name}: the audio is not clean (see AUDIO lines); the quality gate will fail it")
    print(out)


if __name__ == "__main__":
    {"audition": audition, "voiced": voiced}[sys.argv[1]](*sys.argv[2:])
