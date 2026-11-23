"""Hand a finished, owner-approved episode to the posting job.
    python publish.py <series> <epN> [--replace]
Only an episode that PASSED the quality gate (out/qa/<series>-<epN>/PASS.json, same file size) can be published.
It becomes the public GitHub release <series>-epN (the video + post.json). GitHub's "Post episode" job posts it at
that series' next Mon/Wed/Fri slot, in episode order. Publishing is the "yes, post it" step: run it only after the
owner approved the script AND, while WEEKLY.md says "Video check: ON", the finished video.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REPO = "drougebusiness-source/story-series"
COVER_FROM_END_MS = 1500   # the cover is the vote screen, near the end


def duration_ms(video: Path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True, check=True).stdout
    return int(float(out.strip()) * 1000)


def first_line(script: dict) -> str:
    """No `hook:` in the script -> the episode's own first caption sentence (already approved text)."""
    import re
    for shot in script.get("shots") or []:
        for sentence in re.split(r"(?<=[.!?])\s+", str(shot.get("caption", "")).strip()):
            if sentence and not sentence.lower().startswith("last time"):
                return sentence
    return ""


def main(slug: str, ep: str, replace: bool = False) -> int:
    n = int(ep.removeprefix("ep"))
    passed = ROOT / "out" / "qa" / f"{slug}-{ep}" / "PASS.json"
    if not passed.exists():
        print(f"❌ {slug} {ep} has not passed the quality gate ({passed} missing). Run render.py first.")
        return 1
    gate = json.loads(passed.read_text(encoding="utf-8"))
    video = ROOT / "out" / "cartoon" / gate["file"]
    if not video.exists() or video.stat().st_size != gate["size"]:
        print(f"❌ {video.name} changed after the quality gate passed. Run render.py again.")
        return 1
    script = yaml.safe_load((ROOT / slug / "cartoon" / f"{ep}.yaml").read_text(encoding="utf-8"))
    choice = script["choice"]
    name = f"{slug}-ep{n}.mp4"
    post = {"n": n, "series": slug, "title": script["title"], "question": choice["question"],
            "options": choice["options"], "hook": script.get("hook") or first_line(script), "video": name, "size": video.stat().st_size, "qa_pass": True,
            "thumb_offset_ms": max(0, duration_ms(video) - COVER_FROM_END_MS)}
    tag = f"{slug}-ep{n}"
    with tempfile.TemporaryDirectory() as d:
        shutil.copy(video, Path(d) / name)
        (Path(d) / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
        exists = subprocess.run(["gh", "release", "view", tag, "-R", REPO], capture_output=True).returncode == 0
        if exists and not replace:
            print(f"❌ release {tag} already exists (add --replace to swap in this render before it posts)")
            return 1
        if exists:
            subprocess.run(["gh", "release", "upload", tag, str(Path(d) / name), str(Path(d) / "post.json"),
                            "--clobber", "-R", REPO], check=True)
        else:
            subprocess.run(["gh", "release", "create", tag, str(Path(d) / name), str(Path(d) / "post.json"),
                            "-R", REPO, "--title", f"{script['title']} ({slug} episode {n})",
                            "--notes", f"Queued for {slug}'s next Mon/Wed/Fri slot. Quality gate: PASS."], check=True)
    print(f"✅ {slug} episode {n} queued: it posts at the next {slug} slot (Mon/Wed/Fri evening, Central)")
    try:   # the same episode on YouTube Shorts and TikTok at the same slot (skipped where not set up)
        import crosspost
        crosspost.schedule(slug, ep, video, post)
        subprocess.run(["git", "add", f"{slug}/crosspost.json"], cwd=ROOT, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", f"crosspost: {slug} ep{n}"], cwd=ROOT, capture_output=True)
    except Exception as e:
        print(f"⚠️ cross-posting failed (Instagram is still queued): {e}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(*args, replace="--replace" in sys.argv))
