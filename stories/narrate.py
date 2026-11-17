"""Narration for `narrated: true` episodes (THE LAST DRAFT horror format, 2026-11-16).

One narrator voice per series: the `narrator` entry in <series>/cartoon/voices.yaml with an `eleven:` voice id.
ElevenLabs reads each scene's text and returns, with the audio, when every character is spoken, so captions can
light up word by word. Needs ELEVENLABS_API_KEY; without it (or without an eleven narrator) the Reel stays
captions-only. Lines are cached by voice and text, so a re-render never pays twice.
Uses only numpy and ffmpeg (the GitHub runner has no audio libraries).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import yaml

log = logging.getLogger(__name__)

RATE = 48000
SPEECH_DB = -20.0           # every line the same loudness (owner 11-16: nobody randomly louder or softer)
MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")   # steadier than v3 (11-16)
CACHE = Path(os.environ.get("STORIES_CACHE", Path.home() / ".cache" / "stories")) / "voice"


def narrator(series_dir: Path) -> str | None:
    """The series narrator's ElevenLabs voice id, or None when it has none (or there is no key)."""
    f = series_dir / "cartoon" / "voices.yaml"
    if not f.exists() or not os.environ.get("ELEVENLABS_API_KEY"):
        return None
    entry = ({k.lower(): v for k, v in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).items()}
             .get("narrator") or {})
    return entry.get("eleven") if isinstance(entry, dict) else None


def words_from_alignment(text: str, al: dict) -> list[tuple[str, float, float]]:
    """(word, start s, end s) for each word, from ElevenLabs' per-character times."""
    chars, starts, ends = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    out, cur, t0, t1 = [], "", 0.0, 0.0
    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            if cur:
                out.append((cur, t0, t1))
            cur = ""
            continue
        if not cur:
            t0 = s
        cur, t1 = cur + c, e
    if cur:
        out.append((cur, t0, t1))
    return out


def _level(a: np.ndarray) -> np.ndarray:
    w = int(RATE * 0.05)
    n = len(a) // w
    if n:
        db = 20 * np.log10(np.sqrt((a[: n * w].reshape(n, w) ** 2).mean(1)) + 1e-9)
        on = db[db > db.max() - 25]
        level = 20 * np.log10(np.sqrt(np.mean(10 ** (on / 10))) + 1e-9)
        a = a * 10 ** ((SPEECH_DB - level) / 20)
    a = a * min(1.0, 0.95 / (np.abs(a).max() or 1))
    k = min(int(RATE * 0.02), len(a) // 2)          # 20 ms soft edges: no clicks
    if k:
        ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, k))
        a[:k] *= ramp
        a[-k:] *= ramp[::-1]
    return a.astype(np.float32)


def _resample(pcm16: bytes, rate_in: int) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "s16le", "-ar", str(rate_in), "-ac", "1", "-i", "pipe:0",
                        "-af", "highpass=f=80", "-ar", str(RATE), "-f", "f32le", "pipe:1"],
                       input=pcm16, capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def speak(text: str, voice_id: str) -> tuple[np.ndarray, list[tuple[str, float, float]]]:
    """The narrated line (mono float32, 48 kHz, levelled) and its word timings."""
    key = hashlib.sha1(f"{MODEL}|1.08|{voice_id}|{text}".encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
    else:
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=pcm_24000",
            data=json.dumps({"text": text, "model_id": MODEL, "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": 1.08}}).encode(),
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    d = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < 3:
                    time.sleep(10 * 2 ** attempt)
                    continue
                raise RuntimeError(f"ElevenLabs {e.code}: {e.read()[:300]!r}") from None
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d), encoding="utf-8")
    audio = _level(_resample(base64.b64decode(d["audio_base64"]), 24000))
    return audio, words_from_alignment(text, d.get("alignment") or d["normalized_alignment"])   # the caption's own words
