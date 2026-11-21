"""post_check.py: 20 minutes after a slot, make sure the episode is up; if not, start the post job and re-check."""
from datetime import datetime, timezone
from types import SimpleNamespace

import post_check as pc

FRI_620 = datetime(2026, 11, 28, 0, 20, tzinfo=timezone.utc)   # Friday 6:20 PM CST, COMPLIANT's slot was 6 PM


def setup(monkeypatch, tmp_path, posted_seq, release=True):
    calls, seq = [], iter(posted_seq)
    monkeypatch.setattr(pc, "LOG", tmp_path / "log.txt")
    monkeypatch.setattr(pc, "REVIEW", tmp_path / "review")
    monkeypatch.setattr(pc.time, "sleep", lambda s: None)
    monkeypatch.setattr(pc, "last_posted", lambda slug: next(seq))

    def run(*cmd):
        calls.append(cmd[:3])
        return SimpleNamespace(returncode=0 if (cmd[1] != "release" or release) else 1, stdout="[]", stderr="")
    monkeypatch.setattr(pc, "run", run)
    return calls


def test_already_up(monkeypatch, tmp_path):
    calls = setup(monkeypatch, tmp_path, [(2, datetime(2026, 11, 28, 0, 1, tzinfo=timezone.utc))])
    assert pc.main("compliant", FRI_620) == 0 and calls == []


def test_missed_then_posted(monkeypatch, tmp_path):
    old = datetime(2026, 11, 26, 0, 1, tzinfo=timezone.utc)
    new = datetime(2026, 11, 28, 0, 25, tzinfo=timezone.utc)
    calls = setup(monkeypatch, tmp_path, [(1, old), (2, new)])
    assert pc.main("compliant", FRI_620) == 0
    assert ("gh", "workflow", "run") in calls
    assert "posted by the check" in (tmp_path / "log.txt").read_text(encoding="utf-8")


def test_not_queued_posts_nothing(monkeypatch, tmp_path):
    old = datetime(2026, 11, 26, 0, 1, tzinfo=timezone.utc)
    calls = setup(monkeypatch, tmp_path, [(1, old)], release=False)
    assert pc.main("compliant", FRI_620) == 0 and ("gh", "workflow", "run") not in calls


def test_still_down_leaves_a_note(monkeypatch, tmp_path):
    old = datetime(2026, 11, 26, 0, 1, tzinfo=timezone.utc)
    setup(monkeypatch, tmp_path, [(1, old)] * 3)
    assert pc.main("compliant", FRI_620) == 1
    assert list((tmp_path / "review").glob("POST-FAILED-compliant-*.txt"))


def test_not_a_post_day(monkeypatch, tmp_path):
    calls = setup(monkeypatch, tmp_path, [])
    assert pc.main("compliant", datetime(2026, 11, 29, 0, 20, tzinfo=timezone.utc)) == 0 and calls == []  # Saturday
