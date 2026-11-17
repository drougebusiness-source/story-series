"""The quality gate catches what the owner flagged (2026-11-16): jumps, talking over, uneven loudness."""
import numpy as np

import qa
import voice


def test_jump_is_caught_but_steady_motion_is_not():
    f = np.zeros((48, 16, 9), np.float32)
    for k in range(48):
        f[k, :, :] = k * 2.0                      # smooth steady change
    assert qa.jumps(f) == []
    f[30:] += 60                                  # something pops
    assert len(qa.jumps(f)) == 1


def test_overlapping_lines_are_caught():
    lines = [{"shot": 1, "who": "narrator", "start": 0.3, "end": 3.0},
             {"shot": 2, "who": "wren", "start": 2.9, "end": 4.0}]
    assert qa.overlaps(lines)
    lines[1]["start"] = 3.4
    assert qa.overlaps(lines) == []


def test_lines_are_levelled_and_a_loud_one_is_caught():
    rate = 48000
    t = np.arange(rate) / rate
    quiet = (0.02 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    loud = (0.6 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    assert abs(voice.speech_db(voice.level(quiet)) - voice.speech_db(voice.level(loud))) < 0.5
    speech = np.concatenate([quiet * 10, np.zeros(rate, np.float32), loud, np.zeros(rate, np.float32), quiet * 10])
    lines = [{"shot": 1, "who": "a", "start": 0, "end": 1}, {"shot": 2, "who": "b", "start": 2, "end": 3},
             {"shot": 3, "who": "c", "start": 4, "end": 5}]
    assert [p for p in qa.loudness(speech, lines, rate) if "shot 2" in p]
