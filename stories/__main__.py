"""Story series pipeline.

    python -m stories check                     test every account's Instagram token and the Gemini key (posts nothing)
    python -m stories preview <series> [--fake-art]
                                                write + render the NEXT episode to out/ without posting or changing
                                                the story (episode 1 is kept as the approved draft)
    python -m stories episode <series>          the scheduled job: count the last vote, write, draw, render, post
    python -m stories slot <HH>                 run `episode` for the series whose slot_utc is HH (GitHub's cron)
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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import art, gemini, reel, votes, writer
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
        result = votes.tally(acct.comments(prev["media_id"]), list(prev["choice"]["options"]), prev["posted_at"], own)
    except PostError as e:
        log.warning("couldn't read the comments, the story will choose: %s", e)
        return {"counts": {}, "total": 0, "winner": None, "share": 0, "error": str(e)[:200]}
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
    sl = sub.add_parser("slot")
    sl.add_argument("hour")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return cmd_check()
    if a.cmd == "status":
        return cmd_status()
    if a.cmd == "preview":
        cmd_preview(a.series, a.fake_art)
        return 0
    if a.cmd == "episode":
        return cmd_episode(a.series)
    if a.cmd == "art":
        art.make_profile(Series.load(a.series), min(a.n, 6))
        return 0
    s = Series.for_slot(a.hour.zfill(2))
    if s is None:
        print(f"no series in slot {a.hour}")
        return 0
    return cmd_episode(s.slug)


if __name__ == "__main__":
    sys.exit(main())
