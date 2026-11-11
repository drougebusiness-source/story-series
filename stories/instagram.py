"""Instagram through the Graph API (the same calls JIC uses): post a Reel, read its comments, check a connection.

Each series has its own account, so its own pair of GitHub secrets: IG_USER_ID_<X> and META_PAGE_TOKEN_<X>.
The video is uploaded straight to Instagram (resumable upload), so it never needs a public link.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
RUPLOAD = "https://rupload.facebook.com"


class PostError(RuntimeError):
    pass


def _check(resp: requests.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        data = {"raw": resp.text[:500]}
    if resp.status_code >= 400 or (isinstance(data, dict) and "error" in data):
        raise PostError(f"{resp.request.method} {resp.url.split('?')[0]} -> {resp.status_code}: {data.get('error', data)}")
    return data


class Account:
    def __init__(self, ig_user: str, token: str, http=None, poll_seconds: float = 10, max_polls: int = 60):
        self.ig, self.token = ig_user, token
        self.http = http or requests.Session()
        self.poll_seconds, self.max_polls = poll_seconds, max_polls

    def username(self) -> str:
        return _check(self.http.get(f"{GRAPH}/{self.ig}", params={
            "fields": "username", "access_token": self.token}, timeout=30)).get("username", "")

    def post_reel(self, video: Path, caption: str) -> dict:
        container = _check(self.http.post(f"{GRAPH}/{self.ig}/media", data={
            "media_type": "REELS", "upload_type": "resumable", "caption": caption, "share_to_feed": "true",
            "access_token": self.token}, timeout=60))["id"]
        with open(video, "rb") as f:
            _check(self.http.post(f"{RUPLOAD}/ig-api-upload/{GRAPH_VERSION}/{container}",
                                  headers={"Authorization": f"OAuth {self.token}", "offset": "0",
                                           "file_size": str(video.stat().st_size)}, data=f, timeout=1800))
        for _ in range(self.max_polls):  # Instagram processes the video before it can be published
            st = _check(self.http.get(f"{GRAPH}/{container}", params={
                "fields": "status_code,status", "access_token": self.token}, timeout=60))
            if st.get("status_code") == "FINISHED":
                break
            if st.get("status_code") in ("ERROR", "EXPIRED"):
                raise PostError(f"Instagram could not process the video: {st}")
            time.sleep(self.poll_seconds)
        else:
            raise PostError("Instagram took too long to process the video")
        media = _check(self.http.post(f"{GRAPH}/{self.ig}/media_publish", data={
            "creation_id": container, "access_token": self.token}, timeout=60))["id"]
        info = _check(self.http.get(f"{GRAPH}/{media}", params={
            "fields": "permalink,timestamp", "access_token": self.token}, timeout=60))
        return {"media_id": media, "permalink": info.get("permalink", ""), "posted_at": info.get("timestamp", "")}

    def comments(self, media_id: str) -> list[dict]:
        """Every top-level comment (text, timestamp, username), following the pages."""
        out, url = [], f"{GRAPH}/{media_id}/comments"
        params = {"fields": "text,timestamp,username", "limit": 50, "access_token": self.token}
        while url:
            d = _check(self.http.get(url, params=params, timeout=60))
            out += d.get("data", [])
            url, params = (d.get("paging") or {}).get("next"), None
        return out

    def insights(self, media_id: str) -> dict:
        """Views, likes and comments for the office's Performance tab (best effort)."""
        try:
            d = _check(self.http.get(f"{GRAPH}/{media_id}", params={
                "fields": "like_count,comments_count", "access_token": self.token}, timeout=30))
            try:
                ins = _check(self.http.get(f"{GRAPH}/{media_id}/insights", params={
                    "metric": "views", "access_token": self.token}, timeout=30))
                d["views"] = ins["data"][0]["values"][0]["value"]
            except (PostError, KeyError, IndexError):
                pass
            return d
        except PostError as e:
            log.warning("insights failed: %s", e)
            return {}

    def check(self) -> str:
        """Who we're connected to and whether the token can read comments. Posts nothing."""
        name = self.username()
        perms = ""
        try:
            d = _check(self.http.get(f"{GRAPH}/me/permissions", params={"access_token": self.token}, timeout=30))
            granted = {p["permission"] for p in d.get("data", []) if p.get("status") == "granted"}
            need = {"instagram_basic", "instagram_content_publish", "instagram_manage_comments"}
            missing = need - granted
            perms = " (can post and read comments)" if not missing else f" ⚠️ token is missing: {', '.join(sorted(missing))}"
        except PostError:
            perms = " (couldn't list the token's permissions; a Page token usually can't, that's OK)"
        return f"✅ connected to @{name}{perms}"
