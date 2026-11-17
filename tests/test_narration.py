"""Narrated episodes (THE LAST DRAFT horror): scenes last as long as their narration, captions follow the words."""
import subprocess

import numpy as np
import pytest

from stories import narrate, reel
from stories.series import Series


def test_words_from_alignment():
    text = "You lift it."
    al = {"characters": list(text), "character_start_times_seconds": [i * 0.1 for i in range(len(text))],
          "character_end_times_seconds": [i * 0.1 + 0.1 for i in range(len(text))]}
    w = narrate.words_from_alignment(text, al)
    assert [x[0] for x in w] == ["You", "lift", "it."]
    assert w[1][1] == pytest.approx(0.4)


def test_narrated_reel_follows_the_voice(monkeypatch, tmp_path):
    s = Series.load("last-draft")
    monkeypatch.setattr(narrate, "narrator", lambda d: "fake-voice")
    monkeypatch.setattr(narrate, "speak", lambda text, v: (
        (0.1 * np.sin(np.arange(int(48000 * 2.0)) / 9)).astype(np.float32),
        [(w, 0.3 * k, 0.3 * k + 0.25) for k, w in enumerate(text.split())]))
    ep = {"n": 1, "narrated": True, "choice": {"question": "Q?", "options": {"A": "a", "B": "b"}},
          "scenes": [{"text": "It's two in the morning.", "image": "dark hall", "seconds": 9},
                     {"text": "The scratching stops.", "image": "lantern", "seconds": 9}]}
    pics = [reel.placeholder(s, sc, i) for i, sc in enumerate(ep["scenes"], 1)]
    out = reel.build(s, ep, pics, tmp_path / "ep.mp4")
    secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(out)], capture_output=True, text=True).stdout)
    want = 2 * (reel.LEAD + 2.0 + reel.TAIL) + reel.CARD_SECONDS["choice"]
    assert secs == pytest.approx(want, abs=0.4)          # scenes follow the narration, not the guessed 9 s
