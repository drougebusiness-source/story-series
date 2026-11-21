"""The posting week (owner, 2026-11-19): an episode goes out every Monday, Wednesday and Friday evening (Central).

Voting on an episode closes at NOON Central on the day before the next episode, which leaves time to write the
next script, get the owner's OK, render it and pass the quality gate:
    Monday's episode    -> votes close Tuesday noon   -> next episode Wednesday
    Wednesday's episode -> votes close Thursday noon  -> next episode Friday
    Friday's episode    -> votes close Sunday noon    -> next episode Monday (the weekend to vote)
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")
CLOSE_HOUR = 12
# local weekday of the post (Mon=0) -> days until voting closes
CLOSE_AFTER = {0: 1, 1: 1, 2: 1, 3: 1, 4: 2, 5: 1, 6: 1}
DAY_NAME = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def close_time(posted: datetime) -> datetime:
    """When voting on an episode posted at `posted` closes (UTC)."""
    local = posted.astimezone(CENTRAL)
    day = local.date() + timedelta(days=CLOSE_AFTER[local.weekday()])
    return datetime.combine(day, time(CLOSE_HOUR), tzinfo=CENTRAL).astimezone(timezone.utc)


def close_words(posted: datetime) -> str:
    """"Sunday at noon Central" for the caption."""
    return f"{DAY_NAME[close_time(posted).astimezone(CENTRAL).weekday()]} at noon Central"


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")


POST_DAYS = (0, 2, 4)        # Monday, Wednesday, Friday (Central)
LATE_LIMIT = timedelta(hours=12)


def due_slot(slot_hour: int, now: datetime) -> datetime | None:
    """The latest Mon/Wed/Fri slot (slot_hour Central) at or before `now`, if it was under 12 h ago.
    GitHub's timer often fires late or skips runs, so the post job checks this every 20 minutes instead of
    trusting the hour it wakes up in."""
    local = now.astimezone(CENTRAL)
    for back in range(0, 3):
        day = local.date() - timedelta(days=back)
        if day.weekday() not in POST_DAYS:
            continue
        slot = datetime.combine(day, time(slot_hour), tzinfo=CENTRAL)
        if slot <= local:
            return slot.astimezone(timezone.utc) if local - slot <= LATE_LIMIT else None
    return None
