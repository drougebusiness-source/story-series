"""20 minutes after a series' Mon/Wed/Fri slot, make sure its episode went up (owner, 2026-11-21).
    python post_check.py <series>
Windows Task Scheduler runs this at 6:20, 7:20, 8:20 and 9:20 PM (one task per series). No Claude, no tokens:
it reads the posted state from GitHub and starts the "Post episode" job by hand if GitHub's timer missed it.
1. Posted already -> log it, done.
2. Not posted and the episode is queued (release <series>-epN) -> start the post job, check again after
   ~7 minutes and once more at ~10 minutes.
3. Not queued (waiting on the owner's OK or a render) -> nothing to post; log it.
Still not up after the re-checks -> review/POST-FAILED-<series>-<date>.txt says what happened.
Log: logs/post-check.log
"""
import json
import subprocess
import sys
import time
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path

import yaml

from stories.schedule import CENTRAL, POST_DAYS

ROOT = Path(__file__).resolve().parent
REPO = "drougebusiness-source/story-series"
LOG = ROOT / "logs" / "post-check.log"
REVIEW = ROOT.parent / "review"
RECHECKS_MIN = (7, 3)      # first look after 7 min, then 3 more (10 min total)


def log(msg: str) -> None:
    line = f"{datetime.now(CENTRAL):%Y-%m-%d %H:%M} {msg}"
    print(line)
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def last_posted(slug: str) -> tuple[int, datetime | None]:
    """(last episode number, when it posted) from GitHub's copy of state.json."""
    run("git", "fetch", "-q", "origin", "main")
    out = run("git", "show", f"origin/main:{slug}/state.json").stdout or '{"episodes": []}'
    eps = json.loads(out)["episodes"]
    if not eps:
        return 0, None
    at = eps[-1].get("posted_at")
    return eps[-1]["n"], datetime.strptime(at.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z") if at else None


def main(slug: str, now: datetime | None = None) -> int:
    cfg = yaml.safe_load((ROOT / slug / "series.yaml").read_text(encoding="utf-8"))
    now = (now or datetime.now(timezone.utc)).astimezone(CENTRAL)
    if now.weekday() not in POST_DAYS or not cfg.get("live"):
        return 0
    slot = datetime.combine(now.date(), dtime(int(cfg["slot_central"])), tzinfo=CENTRAL)
    if now < slot + timedelta(minutes=10):
        log(f"{slug}: too early to check (slot {slot:%H:%M})")
        return 0

    def up() -> tuple[bool, int]:
        n, at = last_posted(slug)
        return bool(at and at >= slot - timedelta(hours=6)), n

    ok, n = up()
    if ok:
        log(f"{slug}: ✅ episode {n} is up (posted by the schedule)")
        return 0
    tag = f"{slug}-ep{n + 1}"
    if run("gh", "release", "view", tag, "-R", REPO).returncode != 0:
        log(f"{slug}: ⏸ episode {n + 1} isn't queued (no release {tag}: waiting on approval or a render); "
            f"nothing to post, it goes out at the next slot once queued")
        return 0
    log(f"{slug}: ⚠️ episode {n + 1} should be up but isn't; starting the post job")
    r = run("gh", "workflow", "run", "post.yml", "-R", REPO, "-f", f"series={slug}")
    if r.returncode != 0:
        log(f"{slug}: ❌ couldn't start the post job: {r.stderr.strip()[:300]}")
    for wait in RECHECKS_MIN:
        time.sleep(wait * 60)
        ok, _ = up()
        if ok:
            log(f"{slug}: ✅ episode {n + 1} is up (posted by the check)")
            return 0
    runs = run("gh", "run", "list", "-R", REPO, "-w", "Post episode", "-L", "1", "--json", "url,conclusion").stdout
    REVIEW.mkdir(exist_ok=True)
    (REVIEW / f"POST-FAILED-{slug}-{now:%Y-%m-%d}.txt").write_text(
        f"{cfg['title']} episode {n + 1} was due at {slot:%I:%M %p} Central on {now:%A %m-%d} and still isn't on "
        f"Instagram after the check re-ran the post job.\nLast post job: {runs.strip()}\nLog: {LOG}\n",
        encoding="utf-8")
    log(f"{slug}: ❌ episode {n + 1} still isn't up after {sum(RECHECKS_MIN)} min; see review/POST-FAILED-{slug}-*.txt")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1]))
