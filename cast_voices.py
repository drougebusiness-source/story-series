"""Find and listen-check an ElevenLabs library voice for a role (owner 11-17: pick one voice per character, check it,
keep it). For each candidate, Gemini listens to the voice's preview and rates accent, clarity and fit.
    python cast_voices.py "<role brief>" "<search params as k=v&k=v>"   -> ranked candidates
"""
import base64
import json
import os
import sys
import urllib.parse
import urllib.request

import render
from qa import _gemini

render._env("ELEVENLABS_API_KEY")
render._env("GEMINI_API_KEY")
H = {"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}

ASK = """You are casting a voice actor for an animated short. The role: {role}
Listen to this voice sample and answer JSON: {{"accent": "<what accent you actually hear>",
"clear": true|false (crisp and easy to understand, not muffled, not whispery, no noise),
"fits": 0-10 (how well it fits the role, accent included), "why": "<one short sentence>"}}"""


def candidates(params: str) -> list[dict]:
    q = dict(urllib.parse.parse_qsl(params))
    q.setdefault("page_size", "8")
    r = json.load(urllib.request.urlopen(urllib.request.Request(
        "https://api.elevenlabs.io/v1/shared-voices?" + urllib.parse.urlencode(q), headers=H)))
    return r["voices"]


def rate(role: str, v: dict) -> dict:
    url = v.get("preview_url")
    if not url:
        return {"fits": -1}
    audio = urllib.request.urlopen(url, timeout=60).read()
    res = _gemini([{"text": ASK.format(role=role)},
                   {"inline_data": {"mime_type": "audio/mpeg", "data": base64.b64encode(audio).decode()}}])
    return res


def main(role: str, *searches: str):
    seen, rows = set(), []
    for s in searches:
        for v in candidates(s):
            if v["voice_id"] in seen:
                continue
            seen.add(v["voice_id"])
            try:
                r = rate(role, v)
            except Exception as e:
                r = {"fits": -1, "why": str(e)[:80]}
            rows.append((r.get("fits", -1), bool(r.get("clear")), v["voice_id"], v["public_owner_id"], v["name"][:34],
                         r.get("accent", "?"), r.get("why", "")))
    for row in sorted(rows, key=lambda x: (-x[1], -x[0]))[:6]:
        print(f"{row[0]:>3} clear={row[1]!s:5} {row[2]} {row[3][:12]} {row[4]:<34} | {row[5]} | {row[6]}")
        print(f"      owner {row[3]}")


if __name__ == "__main__":
    main(*sys.argv[1:])
