"""Check every lip-synced shot says its script line: transcribes the shot's own audio (free, local faster-whisper
from the agent-office reels venv) and compares it with the line. Run with that venv's python:
    ../agent-office/reels/.venv/Scripts/python.exe check_lines.py <series> [ep1]"""
import difflib
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml
from faster_whisper import WhisperModel

ROOT = Path(__file__).parent
NUM = {"731": "seven thirty one", "213": "two thirteen", "4471": "forty four seventy one", "39": "thirty nine", "90": "ninety"}


ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "        "seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def words_for(n: int) -> str:
    """A number as spoken words (0 to 999,999): 11000 -> eleven thousand."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + words_for(n % 100))
    return words_for(n // 1000) + " thousand" + ("" if n % 1000 == 0 else " " + words_for(n % 1000))


def norm(t: str) -> str:
    t = t.lower()
    for k, v in NUM.items():                             # how the script says them ("Day 731" = seven thirty-one)
        t = t.replace(k, v)
    t = re.sub(r"\d[\d,]*", lambda m: words_for(int(m.group().replace(",", ""))) if len(m.group()) < 9 else m.group(), t)
    return " ".join(re.sub(r"[^a-z ]+", " ", t.replace("-", " ")).split())


def main(slug: str, ep: str = "ep1"):
    shots = yaml.safe_load((ROOT / slug / "cartoon" / f"{ep}.yaml").read_text(encoding="utf-8"))["shots"]
    voices = yaml.safe_load((ROOT / slug / "cartoon" / "voices.yaml").read_text(encoding="utf-8"))
    m = WhisperModel("base.en", device="cpu", compute_type="int8")
    bad = 0
    for i, shot in enumerate(shots, 1):
        cap = re.match(r"^([A-Z][A-Z .'\"-]{1,30}):\s*(.+)$", shot.get("caption", "").strip())
        if not cap or not (voices.get(cap.group(1).strip().lower()) or {}).get("eleven"):
            continue
        want = shot.get("line", cap.group(2))
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ROOT / "out" / "cartoon" / f"{slug}-{ep}" / f"shot{i}.mp4"),
                              "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
        heard = " ".join(s.text.strip() for s in m.transcribe(np.frombuffer(pcm, np.float32))[0])
        score = difflib.SequenceMatcher(None, norm(want), norm(heard)).ratio()
        ok = score >= 0.85
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} shot {i} {score:.2f}  want: {want}\n              heard: {heard}")
    sys.exit(1 if bad else 0)


def from_qa(qa_dir: str):
    """Gate mode: every line in out/qa/<series>-<ep>/lines.json, cut from speech.wav, against its script text."""
    import json
    import wave
    d = Path(qa_dir)
    lines = json.loads((d / "lines.json").read_text(encoding="utf-8"))
    with wave.open(str(d / "speech.wav")) as w:            # 16-bit mono (no soundfile in this venv)
        rate = w.getframerate()
        speech = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    m = WhisperModel("base.en", device="cpu", compute_type="int8")
    bad = 0
    for ln in lines:
        seg = speech[int(ln["start"] * rate):int(ln["end"] * rate)]
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(rate), "-ac", "1", "-i", "-", "-f",
                              "f32le", "-ar", "16000", "-"], input=seg.tobytes(), capture_output=True).stdout
        heard = " ".join(x.text.strip() for x in m.transcribe(np.frombuffer(pcm, np.float32))[0])
        score = difflib.SequenceMatcher(None, norm(ln["text"]), norm(heard)).ratio()
        ok = score >= 0.9                                # a dropped word must fail (owner 11-16)
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} shot {ln['shot']} {ln['who']} {score:.2f}: wanted \"{ln['text']}\", heard \"{heard}\"")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if sys.argv[1] == "--qa":
        from_qa(sys.argv[2])
    else:
        main(*sys.argv[1:])
