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
