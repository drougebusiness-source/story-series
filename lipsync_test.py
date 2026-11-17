"""Lip-sync test: the video model speaks the line itself (so the mouth matches), then ElevenLabs speech-to-speech
swaps that voice for the character's cast voice, keeping the exact timing.
    python lipsync_test.py <series> <shot number> <eleven voice id>
-> out/lipsync/<series>-shot<N>-{raw,omni,revoiced}.mp4"""
import json
import os
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

import cartoon
import voice
from hybrid_sample import animate
from stories.series import ROOT


def sts(wav: Path, voice_id: str) -> bytes:
    """ElevenLabs speech-to-speech: same words and timing, the cast voice, background noise removed."""
    b = uuid.uuid4().hex
    parts = [
        f'--{b}\r\nContent-Disposition: form-data; name="model_id"\r\n\r\neleven_multilingual_sts_v2\r\n'.encode(),
        f'--{b}\r\nContent-Disposition: form-data; name="remove_background_noise"\r\n\r\ntrue\r\n'.encode(),
        f'--{b}\r\nContent-Disposition: form-data; name="audio"; filename="a.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
        + wav.read_bytes() + b"\r\n",
        f"--{b}--\r\n".encode()]
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}?output_format=mp3_44100_128", data=b"".join(parts),
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def main(slug: str, n: str, voice_id: str, secs: str = "6"):
    e = cartoon.Episode(slug, "ep1")
    shot = e.ep["shots"][int(n) - 1]
    who, text = voice.speaker_and_text(shot["caption"])
    text = shot.get("line", text)
    name = (voice.load_cast(e.s.dir).get(who) or {}).get("name", who.title())
    out = ROOT / "out" / "lipsync"
    out.mkdir(parents=True, exist_ok=True)
    raw = out / f"{slug}-shot{n}-omni.mp4"
    if not raw.exists():
        notes = "".join(" " + e.note(c).strip() for c in shot.get("cast", []) if e.note(c))
        raw.write_bytes(animate((e.out / f"key{n}.jpg").read_bytes(),
                                f"{cartoon.STYLE} Action: {shot['motion']} Every character keeps exactly the same face, "
                                f"hair, body and outfit as in the first frame for the whole shot.{notes} Locked-off "
                                f"camera. The background set must stay completely still. {name} says, out loud and "
                                f"clearly, exactly these words and nothing else: \"{text}\" Their mouth moves in sync "
                                f"with every word and closes when they finish. Everyone else keeps their mouth closed. "
                                f"Sound: only {name}'s voice, no music, no other voices. No subtitles or written words.",
                                int(secs)))
    wav = out / f"{slug}-shot{n}-omni.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vn", "-ac", "1", "-ar", "44100", str(wav)], check=True)
    mp3 = out / f"{slug}-shot{n}-cast.mp3"
    if not mp3.exists():
        mp3.write_bytes(sts(wav, voice_id))
    final = out / f"{slug}-shot{n}-revoiced.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-i", str(mp3), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)], check=True)
    print(final)


if __name__ == "__main__":
    main(*sys.argv[1:])
