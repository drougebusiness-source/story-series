"""Owner rule: no scratchy, clicky or static sound in any video. These keep the cleaning and the check honest."""
import numpy as np

import voice


def _speechlike(secs, rate=24000):
    t = np.arange(int(rate * secs)) / rate
    return (0.3 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)


def test_clean_never_touches_speech_sounds():
    """Owner 11-17: clean() used to zero out noisy bursts, which silenced every S/SH/T inside words ("My sister?"
    became "Duh"). It must leave the voice exactly as recorded and only trim true silence off the ends."""
    rng = np.random.default_rng(1)
    hiss = (0.15 * rng.uniform(-1, 1, 2400)).astype(np.float32)             # an "s" sound: a short noisy burst
    word = np.concatenate([_speechlike(0.3), hiss, _speechlike(0.3)])
    a = np.concatenate([np.zeros(12000, np.float32), word, np.zeros(12000, np.float32)])
    c = voice.clean(a)
    assert len(c) < len(a)                                                    # silence at the ends is trimmed
    k = len(c) - 1
    # the word survives intact: the result contains the hiss samples unchanged (nothing zeroed or smoothed)
    joined = c.tobytes()
    assert hiss.tobytes() in joined


def test_audio_check_flags_clicks_and_dead_gaps():
    rate = 48000
    good = np.resize(_speechlike(1.0, rate), rate * 4)
    assert voice.audio_check(good) == []
    bad = good.copy()
    bad[rate] = 0.95
    bad[rate + 1] = -0.95
    bad[2 * rate: 2 * rate + rate // 4] = 0
    probs = " ".join(voice.audio_check(bad))
    assert "click" in probs and "dead-silent" in probs


def test_rambling_line_is_rejected():
    assert voice._length_ok(np.zeros(24000 * 3, np.float32), "Forty names. Home by six.")
    assert not voice._length_ok(np.zeros(24000 * 19, np.float32), "Forty names. Home by six.")
