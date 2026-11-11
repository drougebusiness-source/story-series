"""Counting the audience's vote from an episode's comments.

Rules (shown to viewers on the pinned "How this works" post):
- A vote is the first standalone A, B or C in a comment ("A", "b!", "Option C", "A because...").
- One vote per account: the latest one counts. The series' own account is ignored.
- Only comments made within 24 h of the post count.
- Most votes wins. No votes or a tie -> the story (the AI) chooses, and the next episode says so.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

LEAD = re.compile(r"option\s+([abc])\b|([abc])(?=\s*$|[^\w\s'])", re.I)   # "b", "a!", "option c because..."
INSIDE = re.compile(r"(?<![A-Za-z0-9])([ABC])(?![A-Za-z0-9'])")     # capital letter later: "going with B"
WINDOW = timedelta(hours=24)


def parse_vote(text: str, options: list[str]) -> str | None:
    """A letter at the start counts in any case; later in the comment only a capital counts (a lowercase "a"
    mid-sentence is the word "a")."""
    t = (text or "").strip()
    m = LEAD.match(t)
    if m and (m.group(1) or m.group(2)).upper() in options:
        return (m.group(1) or m.group(2)).upper()
    for m in INSIDE.finditer(t):
        if m.group(1) in options:
            return m.group(1)
    return None


def _ts(s: str) -> datetime:
    return datetime.strptime(s.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")


def tally(comments: list[dict], options: list[str], posted_at: str, own_username: str = "") -> dict:
    """comments: Instagram comment objects with text, timestamp and username."""
    start = _ts(posted_at)
    latest: dict[str, tuple[datetime, str]] = {}
    for c in comments:
        user = (c.get("username") or c.get("from", {}).get("username") or c.get("id", "")).lower()
        if own_username and user == own_username.lower():
            continue
        when = _ts(c["timestamp"])
        if not (start <= when <= start + WINDOW):
            continue
        v = parse_vote(c.get("text", ""), options)
        if v and (user not in latest or when >= latest[user][0]):
            latest[user] = (when, v)
    counts = {o: 0 for o in options}
    for _, v in latest.values():
        counts[v] += 1
    total = sum(counts.values())
    top = max(counts.values()) if total else 0
    leaders = [o for o, n in counts.items() if n == top]
    winner = leaders[0] if total and len(leaders) == 1 else None
    return {"counts": counts, "total": total, "winner": winner,
            "share": round(100 * top / total) if winner else 0}
