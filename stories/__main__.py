"""Story series pipeline.

    python -m stories check                     test every account's Instagram token and the Gemini key (posts nothing)
    python -m stories preview <series> [--fake-art]
                                                write + render the NEXT episode to out/ without posting or changing
                                                the story (episode 1 is kept as the approved draft)
    python -m stories episode <series>          the scheduled job: count the last vote, write, draw, render, post
    python -m stories post <series>             post the next episode the PC rendered and published as a GitHub release
                                                (tag <series>-epN: video + post.json). Not ready -> skip, post nothing
    python -m stories due                       post every series whose Mon/Wed/Fri slot has come and isn't posted yet
                                                (GitHub's cron runs this every 20 min on post evenings)
    python -m stories tally                     count the votes of every episode whose voting has closed
    python -m stories engage                    reply "B counted" to each new vote on the open episodes
    python -m stories status                    one line per series
    python -m stories art <series> [--n 3]      Gemini profile picture options -> out/art/

A series only posts when `live: true` in its series.yaml.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import art, gemini, reel, schedule, votes, writer
from .instagram import Account, PostError
from .series import ROOT, SLUGS, Series

log = logging.getLogger("stories")
OUT = ROOT / "out"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def caption(series: Series, ep: dict) -> str:
    tail = ("Next episode: REWIND." if ep.get("death") else
            f"{series.cfg.get('vote_line', '')} Comment {' or '.join(ep['choice']['options'])}. "
            f"Voting closes in 24 h. No votes? The story chooses.")
    head = f"{ep['opening']}\n\n" if ep.get("opening") else ""
    return f"{head}EP {ep['n']}: {ep['title']}\n{ep.get('caption', '')}\n\n{tail}\n\n{series.cfg.get('hashtags', '')}".strip()


def pictures(series: Series, ep: dict, fake: bool) -> tuple[list[bytes], float]:
    if fake or not os.environ.get("GEMINI_API_KEY"):
        return [reel.placeholder(series, s, i) for i, s in enumerate(ep["scenes"], 1)], 0.0
    who = "; ".join(f"{k}: {v}" for k, v in (series.cfg.get("characters") or {}).items())
    p = gemini.Painter()
    out = []
    for s in ep["scenes"]:
        out.append(p.picture(f"{series.cfg['style']} Vertical 9:16 frame. Characters (draw them exactly like this "
                             f"whenever they appear): {who}. Scene: {s['image']} {gemini.NO_TEXT}"))
    return out, p.spent


def account(series: Series) -> Account | None:
    creds = series.ig_creds()
    return Account(*creds) if creds else None


def count_last_vote(series: Series, prev: dict | None, acct: Account | None) -> dict | None:
    if not prev or prev.get("death") or not prev.get("media_id") or acct is None:
        return None
    try:
        own = acct.username()
        result = votes.tally(acct.comments(prev["media_id"]), list(prev["choice"]["options"]), prev["posted_at"], own,
                             prev.get("close_at", ""))
    except PostError as e:
        log.warning("couldn't read the comments, the story will choose: %s", e)
        prev["result"] = {"counts": {}, "total": 0, "winner": None, "share": 0, "error": str(e)[:200]}
        return prev["result"]
    prev["result"] = result
    prev["stats"] = acct.insights(prev["media_id"])
    return result


def draft_path(series: Series, n: int) -> Path:
    return series.dir / "episodes" / f"ep{n:03d}.json"


def cmd_preview(slug: str, fake: bool) -> Path:
    series = Series.load(slug)
    eps = series.state["episodes"]
    prev = eps[-1] if eps else None
    n = prev["n"] + 1 if prev else 1
    ep = writer.write_episode(series, prev, None if prev is None or prev.get("death") else {"winner": None, "total": 0},
                              eps)
    if n == 1:  # the approved first episode is posted exactly as previewed
        draft_path(series, 1).parent.mkdir(exist_ok=True)
        draft_path(series, 1).write_text(json.dumps(ep, indent=2, ensure_ascii=False), encoding="utf-8")
    pics, spent = pictures(series, ep, fake)
    out = reel.build(series, ep, pics, OUT / f"{slug}-ep{n:03d}-preview.mp4")
    (OUT / f"{slug}-ep{n:03d}-preview.json").write_text(json.dumps(ep, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / f"{slug}-ep{n:03d}-caption.txt").write_text(caption(series, ep), encoding="utf-8")
    print(f"{out}  ({len(ep['scenes'])} scenes, art ${spent:.2f})")
    return out


def cmd_episode(slug: str) -> int:
    series = Series.load(slug)
    if not series.live:
        print(f"{slug}: not live yet (set live: true in {slug}/series.yaml to start posting)")
        return 0
    acct = account(series)
    if acct is None:
        print(f"{slug}: ❌ no Instagram secrets ({' and '.join(series.ig_env)})")
        return 1
    state = series.state
    eps = state["episodes"]
    prev = eps[-1] if eps else None
    if prev and prev.get("posted_at"):
        posted = datetime.strptime(prev["posted_at"].replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
        if _now() < posted + votes.WINDOW + timedelta(minutes=5):
            print(f"{slug}: voting on episode {prev['n']} is still open; nothing to do")
            return 0
    result = count_last_vote(series, prev, acct)
    n = prev["n"] + 1 if prev else 1
    d1 = draft_path(series, 1)
    if n == 1 and d1.exists():
        ep = json.loads(d1.read_text(encoding="utf-8"))
    else:
        ep = writer.write_episode(series, prev, result, eps)
    pics, spent = pictures(series, ep, fake=False)
    video = reel.build(series, ep, pics, OUT / f"{slug}-ep{n:03d}.mp4")
    posted = acct.post_reel(video, caption(series, ep))
    ep.update(posted)
    ep["art_cost"] = spent
    eps.append(ep)
    series.save_state(state)  # saves prev's result too
    who = {"first": "start", "vote": f"audience voted {ep['chosen']}", "ai": f"no winner, story chose {ep['chosen']}",
           "rewind": f"rewind to {ep['chosen']}"}[ep["decided_by"]]
    series.add_canon(f"- Ep {n} \"{ep['title']}\" ({who}): {ep['canon']}")
    print(f"{slug}: ✅ episode {n} posted {posted.get('permalink')} (art ${spent:.2f})")
    return 0


REPO = os.environ.get("GITHUB_REPOSITORY", "drougebusiness-source/story-series")


def release_file(tag: str, name: str) -> bytes | None:
    """A file from the public GitHub release `tag`, or None if it isn't there (yet)."""
    r = requests.get(f"https://github.com/{REPO}/releases/download/{tag}/{name}", timeout=300)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content


def credit_line(prev: dict | None) -> str:
    """Thank last episode's voters by name (people come back to see it), or say the story chose."""
    r = (prev or {}).get("result")
    if not r:
        return ""
    if r.get("winner"):
        names = [f"@{u}" for u in (r.get("voters") or {}).get(r["winner"], []) if not u.isdigit()]
        more = r["total"] - len(names[:3])
        who = ", ".join(names[:3]) + (f" and {more} other{'s' if more != 1 else ''}" if more > 0 and names else "")
        return f"Last time you chose {r['winner']}" + (f". Thanks {who}! 🗳️" if names else ".")
    if r.get("total"):
        return "Last time it was a tie, so the story chose. Break the tie this time."
    return "Last time nobody voted, so the story chose. This time it's up to you."


FIRST_COMMENT = "👇 Comment {letters}. The votes decide what happens next."


def cartoon_caption(series: Series, post: dict, now: datetime, prev: dict | None = None) -> str:
    opts = "\n".join(f"{k}: {v}" for k, v in post["options"].items())
    letters = " or ".join(post["options"])
    head = "\n\n".join(x for x in (post.get("hook", ""), credit_line(prev)) if x)
    return (f"{head + chr(10) + chr(10) if head else ''}EP {post['n']}: {post['title']}\n\n{post['question']}\n{opts}\n\n"
            f"Comment {letters}. Voting closes {schedule.close_words(now)}. Most votes wins. "
            f"No votes? The story chooses.\n\nNew episodes every Monday, Wednesday and Friday.\n\n"
            f"{series.cfg.get('hashtags', '')}").strip()


def cmd_post(slug: str) -> int:
    """The scheduled job (owner's week: Mon/Wed/Fri evenings). The PC writes, renders and quality-checks each
    episode, and after the owner's OK publishes it as a GitHub release; this posts it and opens the vote."""
    series = Series.load(slug)
    if not series.live:
        print(f"{slug}: not live yet (set live: true in {slug}/series.yaml to start posting)")
        return 0
    hold = series.cfg.get("hold_until")
    if hold and _now().astimezone(schedule.CENTRAL).date().isoformat() < str(hold):
        print(f"{slug}: ⏸ on hold until {hold} (owner's call, series.yaml hold_until); nothing posted")
        return 0
    acct = account(series)
    if acct is None:
        print(f"{slug}: ❌ no Instagram secrets ({' and '.join(series.ig_env)})")
        return 1
    state = series.state
    eps = state["episodes"]
    n = eps[-1]["n"] + 1 if eps else 1
    tag = f"{slug}-ep{n}"
    meta = release_file(tag, "post.json")
    if meta is None:
        print(f"{slug}: ⏸ episode {n} isn't ready (no release {tag}); nothing posted. "
              f"It goes out at the next slot once the PC publishes it.")
        return 0
    post = json.loads(meta)
    if not post.get("qa_pass"):
        print(f"{slug}: ❌ release {tag} has no quality-gate PASS; not posting")
        return 1
    OUT.mkdir(exist_ok=True)
    video = OUT / post["video"]
    video.write_bytes(release_file(tag, post["video"]) or b"")
    if video.stat().st_size != post["size"]:
        print(f"{slug}: ❌ downloaded video is {video.stat().st_size} bytes, expected {post['size']}; not posting")
        return 1
    now = _now()
    text = cartoon_caption(series, post, now, eps[-1] if eps else None)
    try:
        posted = acct.post_reel(video, text, post.get("thumb_offset_ms"))
    except PostError as e:   # Instagram's upload sometimes fails once ("Request processing failed", 11-21)
        log.warning("upload failed, trying once more in 30 s: %s", e)
        time.sleep(30)
        posted = acct.post_reel(video, text, post.get("thumb_offset_ms"))
    try:   # our own first comment, so the comment box isn't empty (best effort: never fails the post)
        acct.comment(posted["media_id"], FIRST_COMMENT.format(letters=" or ".join(post["options"])))
    except (PostError, KeyError) as e:
        log.warning("first comment failed: %s", e)
    when = datetime.strptime(posted["posted_at"].replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")         if posted.get("posted_at") else now
    ep = {"n": n, "title": post["title"], "kind": "cartoon",
          "choice": {"question": post["question"], "options": post["options"]},
          **posted, "close_at": schedule.iso(schedule.close_time(when))}
    eps.append(ep)
    series.save_state(state)
    print(f"{slug}: ✅ episode {n} posted {posted.get('permalink')} (voting closes {schedule.close_words(when)})")
    return 0


def cmd_due() -> int:
    """Post each live series whose slot (slot_central, Mon/Wed/Fri) has passed in the last 12 h and that hasn't
    posted since. Safe to run as often as you like."""
    now, bad = _now(), 0
    for slug in SLUGS:
        series = Series.load(slug)
        slot = schedule.due_slot(int(series.cfg["slot_central"]), now)
        if not series.live or slot is None:
            continue
        eps = series.state["episodes"]
        last = eps[-1].get("posted_at") if eps else None
        if last and datetime.strptime(last.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z") >= slot - timedelta(hours=6):
            continue   # already posted for this slot (or posted by hand shortly before it)
        bad |= cmd_post(slug)
    return bad


MAX_REPLIES = 40   # per series per run, well under Instagram's limits


def cmd_engage() -> int:
    """Reply to every new vote on each open episode ("B counted 🗳️"). Replies roughly double the comment count,
    which is what Instagram ranks on, and tell voters they were heard. Runs a few times a day on GitHub."""
    now = _now()
    for slug in SLUGS:
        series = Series.load(slug)
        state = series.state
        ep = state["episodes"][-1] if state["episodes"] else None
        acct = account(series)
        if not series.live or not ep or not ep.get("media_id") or acct is None or "result" in ep:
            continue
        if ep.get("close_at") and now >= datetime.strptime(ep["close_at"], "%Y-%m-%dT%H:%M:%S%z"):
            continue
        try:
            own = acct.username().lower()
            comments = acct.comments(ep["media_id"])
        except PostError as e:
            print(f"{series.title}: ⚠️ couldn't read comments: {e}")
            continue
        done, sent = set(ep.get("replied", [])), 0
        for c in comments:
            if c.get("id") in done or (c.get("username") or "").lower() == own or sent >= MAX_REPLIES:
                continue
            v = votes.parse_vote(c.get("text", ""), list(ep["choice"]["options"]))
            if not v:
                continue
            try:
                acct.reply(c["id"], f"{v} counted 🗳️ ({ep['choice']['options'][v]})")
            except PostError as e:
                print(f"{series.title}: ⚠️ reply failed: {e}")
                break
            done.add(c["id"])
            sent += 1
        if sent:
            ep["replied"] = sorted(done)
            series.save_state(state)
        print(f"{series.title}: episode {ep['n']}: {sent} new vote{'s' if sent != 1 else ''} answered")
    return 0


def cmd_tally() -> int:
    """Count every closed vote once and save it in state.json (the PC's writer reads it from there)."""
    now = _now()
    for slug in SLUGS:
        series = Series.load(slug)
        state = series.state
        prev = state["episodes"][-1] if state["episodes"] else None
        if not prev or not prev.get("media_id") or "result" in prev:
            print(f"{series.title}: nothing to count")
            continue
        close = prev.get("close_at")
        if close and now < datetime.strptime(close, "%Y-%m-%dT%H:%M:%S%z"):
            print(f"{series.title}: voting on episode {prev['n']} is open until {close}")
            continue
        r = count_last_vote(series, prev, account(series))
        if r is None:
            print(f"{series.title}: ❌ no Instagram secrets")
            continue
        series.save_state(state)
        counts = ", ".join(f"{k} {v}" for k, v in r["counts"].items())
        verdict = f"{r['winner']} wins ({r['share']}%)" if r["winner"] else "no winner: the story chooses"
        print(f"{series.title}: episode {prev['n']}: {counts} of {r['total']} votes -> {verdict}"
              + (f" ⚠️ {r['error']}" if r.get("error") else ""))
    return 0


def cmd_check() -> int:
    bad = 0
    print("Gemini:", "✅ key set, text model " + gemini.text_model() if os.environ.get("GEMINI_API_KEY") else "❌ GEMINI_API_KEY not set")
    for slug in SLUGS:
        s = Series.load(slug)
        acct = account(s)
        if acct is None:
            print(f"{s.title}: not set up (add {' and '.join(s.ig_env)})")
            continue
        try:
            print(f"{s.title}: {acct.check()}  live={s.live}")
        except PostError as e:
            bad += 1
            print(f"{s.title}: ❌ {e}")
    return 1 if bad else 0


def cmd_status() -> int:
    for slug in SLUGS:
        s = Series.load(slug)
        eps = s.state["episodes"]
        last = eps[-1] if eps else {}
        print(f"{s.title}: live={s.live} handle=@{s.cfg.get('handle') or '?'} episodes={len(eps)} "
              f"last={last.get('posted_at', '-')} {last.get('permalink', '')}")
    return 0


def cmd_notice(text: str) -> int:
    """One comment from each account on its open episode (e.g. "voting extended"), once per text. Owner-approved only."""
    bad = 0
    for slug in SLUGS:
        series = Series.load(slug)
        state = series.state
        eps = state["episodes"]
        ep = eps[-1] if eps else None
        if not series.live or not ep or not ep.get("media_id"):
            continue
        if text in ep.get("notices", []):
            print(f"{series.title}: already said that")
            continue
        acct = account(series)
        if acct is None:
            print(f"{series.title}: ❌ no Instagram secrets")
            bad = 1
            continue
        try:
            acct.comment(ep["media_id"], text)
        except PostError as e:
            print(f"{series.title}: ❌ {e}")
            bad = 1
            continue
        ep.setdefault("notices", []).append(text)
        series.save_state(state)
        print(f"{series.title}: ✅ commented on episode {ep['n']}")
    return bad


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="stories")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("status")
    p = sub.add_parser("preview")
    p.add_argument("series", choices=SLUGS)
    p.add_argument("--fake-art", action="store_true")
    e = sub.add_parser("episode")
    e.add_argument("series", choices=SLUGS)
    ar = sub.add_parser("art")
    ar.add_argument("series", choices=SLUGS)
    ar.add_argument("--n", type=int, default=3)
    po = sub.add_parser("post")
    po.add_argument("series", choices=SLUGS)
    sub.add_parser("tally")
    sub.add_parser("engage")
    sub.add_parser("due")
    no = sub.add_parser("notice")
    no.add_argument("text")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return cmd_check()
    if a.cmd == "status":
        return cmd_status()
    if a.cmd == "preview":
        cmd_preview(a.series, a.fake_art)
        return 0
    if a.cmd == "post":
        return cmd_post(a.series)
    if a.cmd == "tally":
        return cmd_tally()
    if a.cmd == "engage":
        return cmd_engage()
    if a.cmd == "notice":
        return cmd_notice(a.text)
    if a.cmd == "episode":
        return cmd_episode(a.series)
    if a.cmd == "art":
        art.make_profile(Series.load(a.series), min(a.n, 6))
        return 0
    return cmd_due()

if __name__ == "__main__":
    sys.exit(main())
