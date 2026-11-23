"""Growth features (owner, 2026-11-23): first comment, vote replies, voter credits, hooks, Shorts/TikTok slots."""
from datetime import datetime, timezone

import crosspost
import publish
import stories.__main__ as m
from stories import votes
from tests.test_weekly import FakeAcct, _series, utc


def test_tally_names_voters():
    c = [{"username": "Sam", "text": "B", "timestamp": "2026-11-21T10:00:00+0000"},
         {"username": "lee", "text": "b!", "timestamp": "2026-11-21T11:00:00+0000"}]
    r = votes.tally(c, ["A", "B"], "2026-11-21T00:05:00+0000", close_at="2026-11-22T18:00:00+0000")
    assert r["winner"] == "B" and sorted(r["voters"]["B"]) == ["lee", "sam"]


def test_credit_lines():
    assert m.credit_line(None) == ""
    won = {"result": {"winner": "B", "total": 5, "voters": {"B": ["sam", "lee", "kim", "jo"]}}}
    assert m.credit_line(won) == "Last time you chose B. Thanks @sam, @lee, @kim and 2 others! 🗳️"
    assert "nobody voted" in m.credit_line({"result": {"winner": None, "total": 0}})
    assert "tie" in m.credit_line({"result": {"winner": None, "total": 2}})


def test_caption_opens_with_hook_then_credit():
    s = m.Series.load("compliant")
    post = {"n": 2, "title": "T", "question": "Q?", "options": {"A": "a", "B": "b"}, "hook": "He copied the file."}
    cap = m.cartoon_caption(s, post, utc("2026-11-24T00:05:00"), {"result": {"winner": None, "total": 0}})
    assert cap.startswith("He copied the file.\n\nLast time nobody voted") and "EP 2: T" in cap


class EngageAcct(FakeAcct):
    def __init__(self, comments):
        super().__init__()
        self.c, self.replies, self.comments_made = comments, [], []

    def username(self):
        return "citizen.213"

    def comments(self, media_id):
        return self.c

    def reply(self, cid, text):
        self.replies.append((cid, text))
        return "r" + cid

    def comment(self, media_id, text):
        self.comments_made.append(text)
        return "c1"


def test_engage_replies_once_per_vote(tmp_path, monkeypatch):
    s = _series(tmp_path, monkeypatch)
    s.save_state({"episodes": [{"n": 1, "media_id": "m1", "posted_at": "2026-11-21T00:05:00+0000",
                                "close_at": "2026-11-22T18:00:00+0000",
                                "choice": {"question": "q", "options": {"A": "Delete it", "B": "Copy it"}}}]})
    acct = EngageAcct([{"id": "1", "username": "sam", "text": "B"},
                       {"id": "2", "username": "lee", "text": "love this"},
                       {"id": "3", "username": "citizen.213", "text": "👇 Comment A or B"}])
    monkeypatch.setattr(m, "SLUGS", ("compliant",))
    monkeypatch.setattr(m, "account", lambda series: acct)
    monkeypatch.setattr(m, "_now", lambda: utc("2026-11-21T12:00:00"))
    m.cmd_engage()
    assert acct.replies == [("1", "B counted 🗳️ (Copy it)")]
    m.cmd_engage()   # second run: nothing new
    assert len(acct.replies) == 1


def test_post_leaves_first_comment(tmp_path, monkeypatch):
    import json
    _series(tmp_path, monkeypatch)
    acct = EngageAcct([])
    post = {"n": 1, "title": "T", "question": "q", "options": {"A": "a", "B": "b"}, "video": "v.mp4", "size": 3,
            "qa_pass": True}
    files = {"post.json": json.dumps(post).encode(), "v.mp4": b"abc"}
    monkeypatch.setattr(m, "account", lambda series: acct)
    monkeypatch.setattr(m, "release_file", lambda tag, name: files.get(name))
    monkeypatch.setattr(m, "_now", lambda: utc("2026-11-21T00:05:00"))
    assert m.cmd_post("compliant") == 0
    assert acct.comments_made == ["👇 Comment A or B. The votes decide what happens next."]


def test_hook_fallback_skips_last_time():
    script = {"shots": [{"caption": "Last time, the story chose. Ezra copied the file."}, {"caption": "x"}]}
    assert publish.first_line(script) == "Ezra copied the file."
    assert publish.first_line({"shots": [{"caption": "Last time, you chose B."}, {"caption": "Juno saw."}]}) == "Juno saw."


def test_next_slot_for_crosspost():
    sun = datetime(2026, 11, 22, 20, 0, tzinfo=timezone.utc)   # Sunday 2 PM CT
    assert crosspost.next_slot(18, sun) == utc("2026-11-24T00:00:00")          # Monday 6 PM CT
    mon_559 = datetime(2026, 11, 23, 23, 59, tzinfo=timezone.utc)              # Monday 5:59 PM CT: too close
    assert crosspost.next_slot(18, mon_559) == utc("2026-11-26T00:00:00")      # -> Wednesday


def test_crosspost_captions():
    c = {"title": "COMPLIANT", "handle": "citizen.213", "hashtags": "#x"}
    post = {"n": 2, "title": "Copies", "question": "Q?", "options": {"A": "a", "B": "b"}, "hook": "He copied it."}
    t = crosspost.captions(c, post, utc("2026-11-24T00:00:00"))
    assert t["yt_title"].startswith("He copied it. | COMPLIANT EP 2") and t["yt_title"].endswith("#shorts")
    assert len(t["yt_title"]) <= 100
    assert "Tuesday at noon Central" in t["yt_desc"] and "@citizen.213" in t["tiktok"]


def test_notice_once(tmp_path, monkeypatch):
    s = _series(tmp_path, monkeypatch)
    s.save_state({"episodes": [{"n": 1, "media_id": "m1"}]})
    acct = EngageAcct([])
    monkeypatch.setattr(m, "SLUGS", ("compliant",))
    monkeypatch.setattr(m, "account", lambda series: acct)
    assert m.cmd_notice("Voting extended") == 0 and m.cmd_notice("Voting extended") == 0
    assert acct.comments_made == ["Voting extended"]
