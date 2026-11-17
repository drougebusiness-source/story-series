"""A ~20 s hybrid sample: animated hook (Gemini Omni video) -> two sliding stills -> animated cliffhanger -> vote card.

    python hybrid_sample.py      -> out/hybrid/driftborn-hybrid.mp4   (about $1: 10 s of video + 2 pictures)
"""
import base64
import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from stories import gemini, reel
from stories.__main__ import pictures
from stories.series import ROOT, Series

OUT = ROOT / "out" / "hybrid"
VIDEO_MODEL = "gemini-omni-1.2-flash"
PRICE_PER_SECOND = 0.07  # 720p, published Nov 2026
SOUND = " Sound: only ambient sound effects (hum, creaking metal, wind). No music, no dialogue, no voices."

SHOTS = [
    {"kind": "video", "image": "art:driftborn", "seconds": 5,
     "motion": "Kael slowly climbs deeper into the tilted wreck, dust drifting through shafts of rust-orange light; the "
               "sealed data core ahead pulses brighter, teal light flickering across his goggles. Slow camera push in.",
     "text": "Nobody else hears the hum. It's coming from inside the wreck."},
    {"kind": "still", "seconds": 4,
     "image": "Extreme close-up of the sealed cylindrical data core half-buried in rubble inside the dark wreck, faint "
              "teal light leaking through cracks in its casing, dust motes, rust-orange rim light.",
     "text": "Ninety years buried. Still warm."},
    {"kind": "still", "seconds": 4,
     "image": "Close-up of Kael Torvin's gloved hand reaching toward the glowing data core, the teal glow reflected in "
              "his goggles, his breath fogging the mask, dark wreck behind him.",
     "text": "He should run. He doesn't."},
    {"kind": "video", "image": "prev", "seconds": 5,
     "motion": "His fingertips touch the core: it flares with blinding teal light that floods the wreck, Kael recoils; "
               "in the flickering light a tall silhouette is revealed standing motionless in the torn hull behind him.",
     "text": "Then the wreck answers."},
]
CHOICE = {"question": "Something is standing behind him.", "options": {"A": "Turn and face it", "B": "Grab the core and run"}}


def animate(first_frame: bytes, prompt: str, seconds: int) -> bytes:
    body = {"model": VIDEO_MODEL,
            "input": [{"type": "image", "data": base64.b64encode(first_frame).decode(), "mime_type": "image/jpeg"},
                      {"type": "text", "text": prompt}],
            "generation_config": {"video_config": {"task": "image_to_video"}},
            "response_format": {"type": "video", "aspect_ratio": "9:16", "resolution": "720p", "duration": f"{seconds}s"}}
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/interactions",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"x-goog-api-key": gemini.key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"video API {e.code}: {e.read().decode()[:800]}") from None

    def find(o):
        if isinstance(o, dict):
            if o.get("type") == "video" and o.get("data"):
                return base64.b64decode(o["data"])
            for v in o.values():
                if (x := find(v)) is not None:
                    return x
        elif isinstance(o, list):
            for v in o:
                if (x := find(v)) is not None:
                    return x
    vid = find(res)
    if vid is None:
        raise RuntimeError("no video in response: " + json.dumps(res)[:800])
    return vid


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def main():
    s = Series.load("driftborn")
    OUT.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    stills = [sh for sh in SHOTS if sh["kind"] == "still"]
    raws, cost = pictures(s, {"n": 1, "scenes": stills}, fake=False)
    spent += cost
    for sh, raw in zip(stills, raws):
        sh["raw"] = raw
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips, prev_raw = [], None
        for i, sh in enumerate(SHOTS):
            out = tmp / f"c{i}.mp4"
            ov = tmp / f"ov{i}.png"
            reel.caption_overlay(s, sh["text"], 1).save(ov)
            if sh["kind"] == "still":
                silent = tmp / f"s{i}.mp4"
                reel._clip_from_image(reel.cover(sh["raw"]), sh["seconds"], silent, zoom=True,
                                      overlay=reel.caption_overlay(s, sh["text"], 1))
                run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-f", "lavfi", "-i",
                     "anullsrc=r=48000:cl=stereo", "-shortest", "-c:v", "copy", "-c:a", "aac", str(out)])
                prev_raw = sh["raw"]
            else:
                first = (ROOT / "out/style/driftborn-art.jpg").read_bytes() if sh["image"].startswith("art:") else prev_raw
                cache = OUT / f"shot{i}.mp4"
                if not cache.exists():
                    cache.write_bytes(animate(first, f"{s.cfg['style']} {sh['motion']}{SOUND}", sh["seconds"]))
                    spent += sh["seconds"] * PRICE_PER_SECOND
                print(f"shot {i} animated")
                has_audio = "audio" in subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(cache)],
                    capture_output=True, text=True).stdout
                amix = "[0:a][2:a]amix=inputs=2:duration=first[ao]" if has_audio else "[2:a]anull[ao]"
                run(["ffmpeg", "-v", "error", "-y", "-i", str(cache), "-i", str(ov), "-f", "lavfi", "-i",
                     "anullsrc=r=48000:cl=stereo", "-filter_complex",
                     f"[0:v]scale={reel.W}:{reel.H}:force_original_aspect_ratio=increase,crop={reel.W}:{reel.H},"
                     f"fps={reel.FPS}[v];[v][1]overlay=0:0,format=yuv420p[vo];"
                     + amix,
                     "-map", "[vo]", "-map", "[ao]", "-t", str(sh["seconds"]), "-c:v", "libx264", "-crf", "19",
                     "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out)])
            clips.append(out)
        card = tmp / "card.png"
        reel.card(s, "choice", {"choice": CHOICE}).save(card)
        cc = tmp / "card.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(card), "-f", "lavfi", "-i",
             "anullsrc=r=48000:cl=stereo", "-t", "4", "-vf", "format=yuv420p", "-r", str(reel.FPS),
             "-c:v", "libx264", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(cc)])
        clips.append(cc)
        inputs = sum((["-i", str(c)] for c in clips), [])
        n = len(clips)
        joined = tmp / "joined.mp4"
        run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex",
             "".join(f"[{k}:v][{k}:a]" for k in range(n)) + f"concat=n={n}:v=1:a=1[v][a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "19", "-c:a", "aac", str(joined)])
        secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     str(joined)], capture_output=True, text=True, check=True).stdout)
        pad = reel.pad(secs, tmp / "pad.wav", seed=1)
        final = OUT / "driftborn-hybrid.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(joined), "-i", str(pad), "-filter_complex",
             "[0:a]volume=1.0[a0];[1:a]volume=0.8[a1];[a0][a1]amix=inputs=2:duration=first[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
             str(final)])
    print(f"{final}  {secs:.1f} s  spent about ${spent:.2f}")


if __name__ == "__main__":
    main()
