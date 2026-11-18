"""Check one voice take: does the audio say every word of the text? Run with the reels venv (faster-whisper):
    take_check.py <wav> "<text>"   -> prints "score missing1,missing2" (score 0-1)
voice.py calls this right after each new ElevenLabs reading and re-records a take that dropped words (owner 11-17)."""
import difflib
import re
import subprocess
import sys

import numpy as np
from faster_whisper import WhisperModel

from check_lines import norm

wav, text = sys.argv[1], sys.argv[2]
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", wav, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                     capture_output=True).stdout
m = WhisperModel("base.en", device="cpu", compute_type="int8")
heard = " ".join(s.text.strip() for s in m.transcribe(np.frombuffer(pcm, np.float32), beam_size=5)[0])
want, got = norm(text), norm(heard)
# names (capitalised mid-sentence) are often spelled differently by the transcriber ("Myra" -> "Mira"): skip them
names = {w.lower().strip(".,!?;:") for i, w in enumerate(text.split())
         if w[:1].isupper() and i > 0 and not text.split()[i - 1].endswith((".", "?", "!"))}
score = difflib.SequenceMatcher(None, want, got).ratio()
gw = got.split()
missing = [w for w in want.split() if w not in names and (len(w) > 1 or w == "i") and not any(difflib.SequenceMatcher(None, w, h).ratio() >= 0.75
                                                             for h in gw)]
print(f"{score:.2f} {','.join(missing)}")
