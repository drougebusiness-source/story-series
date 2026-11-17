"""Owner rule: no scratchy, clicky or static sound in any video. These keep the cleaning and the check honest."""
import numpy as np

import voice


def _speechlike(secs, rate=24000):
    t = np.arange(int(rate * secs)) / rate
    return (0.3 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)


def test_clean_removes_static_bursts_and_clicks():
    rng = np.random.default_rng(1)
    a = np.concatenate([rng.uniform(-0.9, 0.9, 240).astype(np.float32),     # click at the start
                        np.zeros(2400, np.float32), _speechlike(1.0), np.zeros(4800, np.float32),
                        rng.uniform(-0.8, 0.8, 3600).astype(np.float32)])    # static burst at the end
    c = voice.clean(a)
    assert np.abs(np.diff(c)).max() < 0.5
    assert all(r <= voice.NOISE_RATIO_DB for *_, r in voice._bursts(c, 24000))
    assert len(c) / 24000 < 1.2          # dead air and junk trimmed, the voice kept


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
