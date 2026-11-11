"""Gemini for the words (episode scripts) and the pictures (scene art). Needs GEMINI_API_KEY.

The text model is picked from the account's model list at run time (the newest "flash" text model), so a retired
model name never breaks a run; STORIES_TEXT_MODEL overrides it. The picture model and its price match JIC's.
Pictures are cached by prompt, so a re-render never pays twice.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

API = "https://generativelanguage.googleapis.com/v1beta"
IMAGE_MODEL = os.environ.get("STORIES_IMAGE_MODEL", "gemini-nano-banana-2.1")  # same as JIC
IMAGE_SIZE = os.environ.get("STORIES_IMAGE_SIZE", "1K")  # about $0.034 a picture
COST_PER_IMAGE = {"1K": 0.034, "2K": 0.05}
MAX_NEW_IMAGES = int(os.environ.get("STORIES_IMAGE_LIMIT", "14"))  # per run: a bad loop can't run up a bill
CACHE = Path(os.environ.get("STORIES_CACHE", Path.home() / ".cache" / "stories")) / "images"
NO_TEXT = ("Absolutely no text, letters, numbers, captions, speech bubbles, logos or watermarks anywhere in the "
           "picture. No gore: violence is implied, never shown.")


def key() -> str:
    k = os.environ.get("GEMINI_API_KEY", "")
    if not k:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return k


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"x-goog-api-key": key(), "Content-Type": "application/json"})
    return _send(req)


def _send(req) -> dict:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode(errors="replace")
            if e.code == 404:
                raise FileNotFoundError(detail) from None
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                log.warning("Gemini %s, retrying: %s", e.code, detail)
                time.sleep(8 * 2 ** attempt)
                continue
            raise RuntimeError(f"Gemini error {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            if attempt < 3:
                time.sleep(8 * 2 ** attempt)
                continue
            raise RuntimeError(f"Gemini unreachable: {e}") from None
    raise RuntimeError("Gemini: no response")


def pick_text_model(models: list[dict]) -> str:
    """The newest general 'flash' text model that can generateContent (not image, tts, lite, live or embedding)."""
    best, best_v = None, (-1.0,)
    for m in models:
        name = m.get("name", "").removeprefix("models/")
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if "flash" not in name or re.search(r"image|tts|lite|live|embed|audio|banana|preview|exp", name):
            continue
        nums = re.findall(r"\d+(?:\.\d+)?", name)
        v = tuple(float(x) for x in nums) or (0.0,)
        if v > best_v:
            best, best_v = name, v
    if not best:
        raise RuntimeError("no Gemini flash text model available on this key")
    return best


def text_model() -> str:
    if os.environ.get("STORIES_TEXT_MODEL"):
        return os.environ["STORIES_TEXT_MODEL"]
    req = urllib.request.Request(f"{API}/models?pageSize=200", headers={"x-goog-api-key": key()})
    return pick_text_model(_send(req).get("models", []))


def write_json(prompt: str, temperature: float = 0.9) -> dict:
    """One JSON answer from the text model."""
    model = text_model()
    out = _post(f"{API}/models/{model}:generateContent", {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"}})
    try:
        txt = "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError):
        raise RuntimeError(f"Gemini returned no text: {json.dumps(out)[:300]}") from None
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    log.info("script written with %s", model)
    return json.loads(txt)


def _find_image(obj) -> bytes | None:
    if isinstance(obj, dict):
        data = obj.get("data")
        kind = str(obj.get("type", "")) + str(obj.get("mime_type", obj.get("mimeType", "")))
        if isinstance(data, str) and len(data) > 200 and ("image" in kind or not kind):
            return base64.b64decode(data)
        for v in obj.values():
            if (found := _find_image(v)):
                return found
    elif isinstance(obj, list):
        for v in obj:
            if (found := _find_image(v)):
                return found
    return None


class Painter:
    """One 9:16 picture per scene, cached by prompt; counts new pictures and their cost."""

    def __init__(self):
        self.new = 0

    @property
    def spent(self) -> float:
        return round(self.new * COST_PER_IMAGE.get(IMAGE_SIZE, 0.05), 3)

    def picture(self, prompt: str) -> bytes:
        CACHE.mkdir(parents=True, exist_ok=True)
        path = CACHE / (hashlib.sha256(f"{IMAGE_MODEL}|{IMAGE_SIZE}|{prompt}".encode()).hexdigest()[:24] + ".jpg")
        if path.exists():
            return path.read_bytes()
        if self.new >= MAX_NEW_IMAGES:
            raise RuntimeError(f"picture limit reached ({MAX_NEW_IMAGES} new pictures in one run)")
        body = {"model": IMAGE_MODEL, "input": [{"type": "text", "text": prompt}],
                "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "9:16",
                                    "image_size": IMAGE_SIZE}}
        try:
            out = _post(f"{API}/interactions", body)
        except FileNotFoundError:  # no Interactions API for this model: the classic call
            out = _post(f"{API}/models/{IMAGE_MODEL}:generateContent", {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE"],
                                     "imageConfig": {"aspectRatio": "9:16", "imageSize": IMAGE_SIZE}}})
        raw = _find_image(out)
        if not raw:
            raise RuntimeError(f"Gemini returned no picture: {json.dumps(out)[:300]}")
        path.write_bytes(raw)
        self.new += 1
        return raw
