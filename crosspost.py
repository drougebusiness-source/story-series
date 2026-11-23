"""Post each episode to YouTube Shorts and TikTok too, at the same Mon/Wed/Fri slot as Instagram (owner, 2026-11-23).
Runs on the PC (publish.py calls `schedule` when it queues an episode), so no new GitHub secrets are needed:
  - YouTube: uploaded right away as PRIVATE with publishAt = the slot, so YouTube itself publishes it on time.
    Each series has its own channel; sign in once per channel with `python crosspost.py youtube-login <series>`
    (needs .youtube/client_secret.json, a Google Cloud "Desktop app" OAuth client; tokens stay in .youtube/).
  - TikTok: scheduled in GoHighLevel's Social Planner for the slot (same route as JIC's TikToks). Set the
    series' `tiktok_ghl_account` in series.yaml once its TikTok is connected in GHL (`python crosspost.py
    tiktok-accounts` lists them).
A platform that isn't set up is skipped quietly; a failure never blocks the Instagram post.
Votes: `python crosspost.py votes <series>` adds YouTube comment votes to the episode's Instagram count in
state.json (TikTok comments can't be read through GHL, so TikTok captions point people to vote on IG or YouTube).

    python crosspost.py schedule <series> <epN>     (publish.py runs this)
    python crosspost.py votes <series>              (the writer runs this before writing the next episode)
    python crosspost.py youtube-login <series>      (once per channel; opens the browser)
    python crosspost.py tiktok-accounts             (lists GHL's connected social accounts)
    python crosspost.py status
"""
from __future__ import annotations

import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import uuid
import webbrowser
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path

import requests
import yaml

from stories import votes
from stories.schedule import CENTRAL, POST_DAYS, close_time, close_words, iso

ROOT = Path(__file__).resolve().parent
YT_DIR = ROOT / ".youtube"
SLUGS = ("compliant", "last-draft", "roll-for-fate", "driftborn")
YT_SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl"
GHL = "https://services.leadconnectorhq.com"
GHL_OWNER = "FRH9DaSNIzLefLBFjXGj"


# ---------------------------------------------------------------- shared
def cfg(slug: str) -> dict:
    return yaml.safe_load((ROOT / slug / "series.yaml").read_text(encoding="utf-8"))


def log_path(slug: str) -> Path:
    return ROOT / slug / "crosspost.json"


def load_log(slug: str) -> dict:
    p = log_path(slug)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_log(slug: str, data: dict) -> None:
    log_path(slug).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def next_slot(slot_hour: int, now: datetime) -> datetime:
    """The next Mon/Wed/Fri at slot_hour Central that is at least 20 minutes away (UTC)."""
    local = now.astimezone(CENTRAL)
    for ahead in range(0, 8):
        day = local.date() + timedelta(days=ahead)
        slot = datetime.combine(day, dtime(slot_hour), tzinfo=CENTRAL)
        if day.weekday() in POST_DAYS and slot >= local + timedelta(minutes=20):
            return slot.astimezone(timezone.utc)
    raise RuntimeError("no slot found")


def captions(c: dict, post: dict, slot: datetime) -> dict:
    opts = "\n".join(f"{k}: {v}" for k, v in post["options"].items())
    letters = " or ".join(post["options"])
    hook = f"{post['hook']}\n\n" if post.get("hook") else ""
    body = f"{hook}EP {post['n']}: {post['title']}\n\n{post['question']}\n{opts}\n\n"
    tags = c.get("hashtags", "")
    return {
        "yt_title": f"{post.get('hook') or post['title']} | {c['title']} EP {post['n']}"[:90] + " #shorts",
        "yt_desc": (f"{body}Comment {letters}. Voting closes {close_words(slot)}. Most votes wins (YouTube and "
                    f"Instagram @{c.get('handle', '')} together). No votes? The story chooses.\n\n"
                    f"New episodes every Monday, Wednesday and Friday.\n\n{tags} #shorts"),
        "tiktok": (f"{body}Vote A or B on our Instagram @{c.get('handle', '')} or YouTube. Voting closes "
                   f"{close_words(slot)}. New episodes Mon/Wed/Fri.\n\n{tags}"),
    }


# ---------------------------------------------------------------- YouTube
def yt_token_file(slug: str) -> Path:
    return YT_DIR / f"{slug}.json"


def yt_client() -> dict:
    data = json.loads((YT_DIR / "client_secret.json").read_text(encoding="utf-8"))
    return data.get("installed") or data.get("web") or data


def yt_access(slug: str) -> str | None:
    f = yt_token_file(slug)
    if not f.exists():
        return None
    tok, client = json.loads(f.read_text(encoding="utf-8")), yt_client()
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": client["client_id"], "client_secret": client["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def youtube_login(slug: str) -> int:
    """One-time sign-in for a series' channel: the browser opens, pick the channel, click Allow."""
    client = yt_client()
    port, state, got = 8765, secrets.token_urlsafe(16), {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state:
                got.update(code=q.get("code", [""])[0], error=q.get("error", [""])[0])
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Done. You can close this tab and go back to Claude.</h2>")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    redirect = f"http://127.0.0.1:{port}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": YT_SCOPES,
        "access_type": "offline", "prompt": "consent select_account", "state": state})
    print(f"Sign in and pick the {cfg(slug)['title']} channel:\n{url}")
    webbrowser.open(url)
    srv.timeout = 600
    for _ in range(600):
        if got:
            break
        threading.Event().wait(1)
    if not got.get("code"):
        print(f"❌ no sign-in ({got.get('error') or 'timed out'})")
        return 1
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "code": got["code"], "client_id": client["client_id"], "client_secret": client["client_secret"],
        "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    YT_DIR.mkdir(exist_ok=True)
    tok = r.json()
    ch = requests.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"},
                      headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=30).json()
    name = (ch.get("items") or [{}])[0].get("snippet", {}).get("title", "?")
    yt_token_file(slug).write_text(json.dumps({"refresh_token": tok["refresh_token"], "channel": name}), encoding="utf-8")
    print(f"✅ {slug} will post to the YouTube channel “{name}”")
    return 0


def youtube_upload(slug: str, video: Path, title: str, desc: str, publish_at: datetime) -> str | None:
    token = yt_access(slug)
    if not token:
        return None
    meta = {"snippet": {"title": title, "description": desc, "categoryId": "1"},
            "status": {"privacyStatus": "private", "publishAt": publish_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                       "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
    start = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                   "X-Upload-Content-Type": "video/mp4"}, json=meta, timeout=60)
    start.raise_for_status()
    up = requests.put(start.headers["Location"], data=video.read_bytes(),
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"}, timeout=1800)
    up.raise_for_status()
    return up.json()["id"]


def youtube_comments(slug: str, video_id: str) -> list[dict]:
    token = yt_access(slug)
    out, page = [], None
    while True:
        params = {"part": "snippet", "videoId": video_id, "maxResults": 100, "textFormat": "plainText"}
        if page:
            params["pageToken"] = page
        d = requests.get("https://www.googleapis.com/youtube/v3/commentThreads", params=params,
                         headers={"Authorization": f"Bearer {token}"}, timeout=30).json()
        for it in d.get("items", []):
            s = it["snippet"]["topLevelComment"]["snippet"]
            out.append({"username": "yt:" + (s.get("authorChannelId", {}).get("value") or s.get("authorDisplayName", "")),
                        "name": s.get("authorDisplayName", ""), "text": s.get("textDisplay", ""),
                        "timestamp": s["publishedAt"][:19] + "+0000"})
        page = d.get("nextPageToken")
        if not page:
            return out


# ---------------------------------------------------------------- TikTok (GoHighLevel)
def ghl_headers() -> tuple[dict, str]:
    c = json.load(open(os.path.expanduser("~/.claude.json"), encoding="utf-8"))["mcpServers"]["ghl"]["headers"]
    return ({"Authorization": c["Authorization"], "Version": "2021-07-28", "Accept": "application/json",
             "User-Agent": "ghl-helper/1.0"}, c["locationId"])


def tiktok_accounts() -> int:
    h, loc = ghl_headers()
    d = requests.get(f"{GHL}/social-media-posting/{loc}/accounts", headers=h, timeout=60).json()
    for a in (d.get("results") or {}).get("accounts", []):
        print(f"{a.get('platform'):10} {a.get('name')!s:30} {a.get('id')}")
    return 0


def tiktok_schedule(account: str, video: Path, caption: str, when: datetime) -> str:
    h, loc = ghl_headers()
    name = video.name
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: video/mp4\r\n\r\n").encode() + video.read_bytes() + \
           (f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\n{name}\r\n--{b}--\r\n").encode()
    r = requests.post(f"{GHL}/medias/upload-file", data=body, timeout=300,
                      headers={**h, "Content-Type": f"multipart/form-data; boundary={b}"})
    r.raise_for_status()
    payload = {"accountIds": [account], "summary": caption, "media": [{"url": r.json()["url"], "type": "video/mp4"}],
               "status": "scheduled", "scheduleDate": when.strftime("%Y-%m-%dT%H:%M:00.000Z"), "type": "post",
               "userId": GHL_OWNER,
               "tiktokPostDetails": {"privacyLevel": "PUBLIC_TO_EVERYONE", "enableComment": True, "enableDuet": True,
                                     "enableStitch": True, "videoDisclosure": False, "promoteYourBrand": False,
                                     "promoteOtherBrand": False}}
    r = requests.post(f"{GHL}/social-media-posting/{loc}/posts", json=payload, headers=h, timeout=300)
    r.raise_for_status()
    return r.json()["results"]["post"]["_id"]


# ---------------------------------------------------------------- commands
def schedule(slug: str, ep: str, video: Path | None = None, post: dict | None = None) -> dict:
    """Queue episode `ep` on YouTube and TikTok for the series' next slot. Idempotent per platform."""
    c = cfg(slug)
    n = int(ep.removeprefix("ep"))
    if post is None or video is None:
        gate = json.loads((ROOT / "out" / "qa" / f"{slug}-{ep}" / "PASS.json").read_text(encoding="utf-8"))
        video = ROOT / "out" / "cartoon" / gate["file"]
        script = yaml.safe_load((ROOT / slug / "cartoon" / f"{ep}.yaml").read_text(encoding="utf-8"))
        post = {"n": n, "title": script["title"], "question": script["choice"]["question"],
                "options": script["choice"]["options"], "hook": script.get("hook", "")}
    slot = next_slot(int(c["slot_central"]), datetime.now(timezone.utc))
    text = captions(c, post, slot)
    data = load_log(slug)
    rec = data.setdefault(f"ep{n}", {"slot": iso(slot)})
    if "youtube" not in rec:
        try:
            vid = youtube_upload(slug, video, text["yt_title"], text["yt_desc"], slot)
            if vid:
                rec["youtube"] = vid
                print(f"✅ YouTube: {slug} ep{n} uploaded, goes public {slot.astimezone(CENTRAL):%a %I:%M %p} CT "
                      f"(https://youtube.com/shorts/{vid})")
            else:
                print(f"– YouTube: {slug} not signed in yet (python crosspost.py youtube-login {slug})")
        except Exception as e:
            print(f"⚠️ YouTube upload failed for {slug} ep{n}: {e}")
    if "tiktok" not in rec:
        acct = c.get("tiktok_ghl_account")
        if acct:
            try:
                rec["tiktok"] = tiktok_schedule(acct, video, text["tiktok"], slot)
                print(f"✅ TikTok: {slug} ep{n} scheduled in GHL for {slot.astimezone(CENTRAL):%a %I:%M %p} CT")
            except Exception as e:
                print(f"⚠️ TikTok scheduling failed for {slug} ep{n}: {e}")
        else:
            print(f"– TikTok: {slug} has no tiktok_ghl_account in series.yaml yet")
    save_log(slug, data)
    return rec


def add_youtube_votes(slug: str) -> int:
    """Merge YouTube comment votes into the last posted episode's result (after GitHub counted Instagram)."""
    state_p = ROOT / slug / "state.json"
    state = json.loads(state_p.read_text(encoding="utf-8"))
    ep = state["episodes"][-1] if state["episodes"] else None
    if not ep or "result" not in ep or "youtube" in (ep["result"].get("sources") or {}):
        print(f"{slug}: nothing to add")
        return 0
    vid = load_log(slug).get(f"ep{ep['n']}", {}).get("youtube")
    if not vid or not yt_token_file(slug).exists():
        print(f"{slug}: no YouTube video for episode {ep['n']}")
        return 0
    opts = list(ep["choice"]["options"])
    close = ep.get("close_at") or iso(close_time(datetime.strptime(ep["posted_at"], "%Y-%m-%dT%H:%M:%S%z")))
    yt = votes.tally(youtube_comments(slug, vid), opts, ep["posted_at"], "", close)
    ig = ep["result"]
    counts = {o: ig.get("counts", {}).get(o, 0) + yt["counts"][o] for o in opts}
    total = sum(counts.values())
    top = max(counts.values()) if total else 0
    leaders = [o for o, k in counts.items() if k == top]
    winner = leaders[0] if total and len(leaders) == 1 else None
    voters = {o: (ig.get("voters") or {}).get(o, []) for o in opts}   # credit lines name Instagram handles only
    ep["result"] = {**ig, "counts": counts, "total": total, "winner": winner,
                    "share": round(100 * top / total) if winner else 0, "voters": voters,
                    "sources": {"instagram": ig.get("counts", {}), "youtube": yt["counts"]}}
    state_p.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{slug}: episode {ep['n']}: YouTube {yt['counts']} + Instagram {ig.get('counts')} -> "
          f"{winner or 'no winner'}")
    return 0


def status() -> int:
    for s in SLUGS:
        c = cfg(s)
        yt = json.loads(yt_token_file(s).read_text(encoding="utf-8")).get("channel") if yt_token_file(s).exists() else None
        print(f"{c['title']}: YouTube {'✅ ' + yt if yt else '– not signed in'} | TikTok "
              f"{'✅ ' + c['tiktok_ghl_account'] if c.get('tiktok_ghl_account') else '– not connected'}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd, *rest = sys.argv[1:] or ["status"]
    sys.exit({"schedule": lambda: (schedule(*rest), 0)[1], "votes": lambda: add_youtube_votes(*rest),
              "youtube-login": lambda: youtube_login(*rest), "tiktok-accounts": tiktok_accounts,
              "status": status}[cmd]())
