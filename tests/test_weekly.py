"""The Mon/Wed/Fri week: vote close times, counting only votes cast before the close, and the release-based post."""
import json
from datetime import datetime, timezone

import stories.__main__ as m
from stories import schedule, votes
from stories.series import Series


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_close_times():
    assert schedule.iso(schedule.close_time(utc("2026-11-21T00:05:00"))) == "2026-11-22T18:00:00+0000"  # Fri -> Sun
    assert schedule.iso(schedule.close_time(utc("2026-11-24T00:05:00"))) == "2026-11-24T18:00:00+0000"  # Mon -> Tue
    assert schedule.iso(schedule.close_time(utc("2026-11-26T03:05:00"))) == "2026-11-26T18:00:00+0000"  # Wed -> Thu
    assert schedule.close_words(utc("2026-11-21T00:05:00")) == "Sunday at noon Central"


def test_tally_respects_close():
    c = [{"username": "a", "text": "A", "timestamp": "2026-11-21T10:00:00+0000"},
         {"username": "b", "text": "B", "timestamp": "2026-11-22T17:59:00+0000"},   # Sunday morning: counts
         {"username": "c", "text": "B", "timestamp": "2026-11-22T18:01:00+0000"}]   # after the close: ignored
    r = votes.tally(c, ["A", "B"], "2026-11-21T00:05:00+0000", close_at="2026-11-22T18:00:00+0000")
    assert r["counts"] == {"A": 1, "B": 1} and r["winner"] is None
    r24 = votes.tally(c, ["A", "B"], "2026-11-21T00:05:00+0000")  # old episodes: 24 h
    assert r24["counts"] == {"A": 1, "B": 0}


class FakeAcct:
    def __init__(self):
        self.posted = None

    def post_reel(self, video, caption, thumb_offset_ms=None):
        self.posted = (video.read_bytes(), caption, thumb_offset_ms)
        return {"media_id": "m1", "permalink": "https://ig/p/1", "posted_at": "2026-11-21T00:06:00+0000"}

    def comment(self, media_id, text):
        return "c1"


def _series(tmp_path, monkeypatch, live=True):
    s = Series.load("compliant")
    s.cfg["live"] = live
    s.cfg.pop("hold_until", None)   # the real series.yaml may carry a temporary hold
    d = tmp_path / "compliant"
    d.mkdir()
    monkeypatch.setattr(Series, "dir", property(lambda self: d))
    monkeypatch.setattr(Series, "load", classmethod(lambda cls, slug: s))
    monkeypatch.setattr(m, "OUT", tmp_path / "out")
    return s


def test_post_skips_when_not_ready(tmp_path, monkeypatch):
    s = _series(tmp_path, monkeypatch)
    acct = FakeAcct()
    monkeypatch.setattr(m, "account", lambda series: acct)
    monkeypatch.setattr(m, "release_file", lambda tag, name: None)
    assert m.cmd_post("compliant") == 0
    assert acct.posted is None and s.state["episodes"] == []


def test_post_publishes_release_and_opens_vote(tmp_path, monkeypatch):
    s = _series(tmp_path, monkeypatch)
    acct = FakeAcct()
    video = b"x" * 10
    post = {"n": 1, "title": "The Delete Pile", "question": "Delete her, or copy it?",
            "options": {"A": "Delete it", "B": "Copy it"}, "video": "compliant-ep1.mp4", "size": 10,
            "qa_pass": True, "thumb_offset_ms": 28000}
    files = {("compliant-ep1", "post.json"): json.dumps(post).encode(), ("compliant-ep1", "compliant-ep1.mp4"): video}
    monkeypatch.setattr(m, "account", lambda series: acct)
    monkeypatch.setattr(m, "release_file", lambda tag, name: files.get((tag, name)))
    monkeypatch.setattr(m, "_now", lambda: utc("2026-11-21T00:05:00"))
    assert m.cmd_post("compliant") == 0
    body, caption, thumb = acct.posted
    assert body == video and thumb == 28000
    assert "EP 1: The Delete Pile" in caption and "A: Delete it" in caption and "Sunday at noon Central" in caption
    ep = s.state["episodes"][0]
    assert ep["media_id"] == "m1" and ep["close_at"] == "2026-11-22T18:00:00+0000"
    assert list(ep["choice"]["options"]) == ["A", "B"]


def test_post_refuses_without_gate(tmp_path, monkeypatch):
    _series(tmp_path, monkeypatch)
    acct = FakeAcct()
    post = {"n": 1, "title": "t", "question": "q", "options": {"A": "a", "B": "b"}, "video": "v.mp4", "size": 1}
    monkeypatch.setattr(m, "account", lambda series: acct)
    monkeypatch.setattr(m, "release_file", lambda tag, name: json.dumps(post).encode() if name == "post.json" else b"x")
    assert m.cmd_post("compliant") == 1 and acct.posted is None


def test_not_live_posts_nothing(tmp_path, monkeypatch):
    _series(tmp_path, monkeypatch, live=False)
    monkeypatch.setattr(m, "account", lambda series: (_ for _ in ()).throw(AssertionError("no account needed")))
    assert m.cmd_post("compliant") == 0


def test_due_slot():
    # Friday 6 PM Central = Sat 00:00 UTC (CST)
    assert schedule.due_slot(18, utc("2026-11-20T23:30:00")) is None                       # 5:30 PM: not yet
    assert schedule.due_slot(18, utc("2026-11-21T06:56:00")) == utc("2026-11-21T00:00:00")  # the late run: still due
    assert schedule.due_slot(18, utc("2026-11-21T18:00:00")) is None                       # 18 h late: wait for Monday
    assert schedule.due_slot(21, utc("2026-11-24T03:20:00")) == utc("2026-11-24T03:00:00")  # Monday 9 PM


def test_due_posts_once(tmp_path, monkeypatch):
    s = _series(tmp_path, monkeypatch)
    s.cfg["slot_central"] = 18
    calls = []
    monkeypatch.setattr(m, "SLUGS", ("compliant",))
    monkeypatch.setattr(m, "cmd_post", lambda slug: calls.append(slug) or 0)
    monkeypatch.setattr(m, "_now", lambda: utc("2026-11-21T00:40:00"))
    m.cmd_due()
    assert calls == ["compliant"]
    s.save_state({"episodes": [{"n": 1, "posted_at": "2026-11-21T00:41:00+0000"}]})
    monkeypatch.setattr(m, "_now", lambda: utc("2026-11-21T01:00:00"))
    m.cmd_due()
    assert calls == ["compliant"]


def test_hold_until(tmp_path, monkeypatch):
    s = _series(tmp_path, monkeypatch)
    s.cfg["hold_until"] = "2026-11-27"
    monkeypatch.setattr(m, "account", lambda series: (_ for _ in ()).throw(AssertionError("held")))
    monkeypatch.setattr(m, "_now", lambda: utc("2026-11-24T00:05:00"))   # Monday 6:05 PM CT
    assert m.cmd_post("compliant") == 0
    acct = FakeAcct()
    monkeypatch.setattr(m, "account", lambda series: acct)
    monkeypatch.setattr(m, "release_file", lambda tag, name: None)
    monkeypatch.setattr(m, "_now", lambda: utc("2026-11-28T00:05:00"))   # Friday 6:05 PM CT
    assert m.cmd_post("compliant") == 0   # past the hold: reaches the release check
