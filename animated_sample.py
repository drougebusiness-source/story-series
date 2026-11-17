"""Fully animated Driftborn sample in a stylized 3D cel-shaded TV-animation look (original designs).

    python animated_sample.py keys     -> out/animated/key<n>.jpg   (5 keyframes, ~$0.17; look at them first)
    python animated_sample.py video    -> out/animated/driftborn-animated.mp4  (5 shots, ~25 s of video, ~$1.75)
"""
import base64
import subprocess
import sys
import tempfile
from pathlib import Path

from hybrid_sample import PRICE_PER_SECOND, animate
from stories import gemini, reel
from stories.series import ROOT, Series

OUT = ROOT / "out" / "animated"
LOOK = ("Still frame from a stylized 3D CG animated TV series with a cel-shaded, hand-painted look: characters have "
        "angular, sharply sculpted faces carved in clean planes like wooden figurines, long strong jaws, high "
        "cheekbones, slightly elongated proportions, hair as solid sculpted shapes, matte painted textures with "
        "visible brush strokes on skin, cloth and metal, soft simple shading with crisp rim light, slightly muted "
        "colours, painterly matte-painting backgrounds with atmospheric haze, cinematic TV composition. Original "
        "characters and designs only, not from any existing franchise.")
KAEL = ("Kael Torvin: wiry 19-year-old man, sun-scarred tan skin, messy dark sculpted hair, brass goggles pushed up on "
        "his forehead, a breath mask hanging at his neck, patched rust-orange diving-style spacesuit with teal "
        "accents and a chest tool rig.")
WORLD = "Setting: a rust-orange desert mining moon, a giant ringed planet in a teal sky."
NO_TEXT = "No text, letters or logos anywhere."

SHOTS = [  # (keyframe picture, motion for the video model, seconds, caption)
    ("Wide shot: Kael stands on the crest of a rust-orange dune at dusk, small against the sky, looking down at a "
     "huge half-buried crashed freighter below; wind blowing sand; the ringed planet huge on the horizon.",
     "Kael breaks into a run and slides down the dune on his heels toward the crashed freighter, sand spraying "
     "behind him, his suit flapping in the wind; the camera follows him down.", 6,
     "Nobody else hears the hum."),
    ("Medium shot: Kael at the torn, jagged edge of the freighter's hull, both gloved hands gripping the twisted metal, "
     "dark opening above him, rust-orange evening light.",
     "Kael hauls himself up by the jagged hull edge, swings a leg over, pulls his goggles down over his eyes and drops "
     "inside into the darkness; dust puffs up.", 5,
     "It's coming from inside the wreck."),
    ("Inside the dark tilted freighter corridor: Kael with goggles down holds up a wrist lamp, its beam cutting "
     "through floating dust; far ahead, a sealed cylindrical data core glows soft teal among the debris.",
     "Kael edges forward through the tilted corridor, ducking under a hanging cable, his lamp beam sweeping; the teal "
     "core ahead pulses brighter in time with a heartbeat; he stops and stares.", 5,
     "Ninety years buried. Still warm."),
    ("Close-up: Kael's face lit teal from below, goggles reflecting the glowing data core, his gloved hand reaching "
     "toward it, breath fogging.",
     "Kael's fingertips touch the core: it flares with blinding teal light and crackling energy that floods the wreck; "
     "he flinches back, shielding his eyes.", 4,
     "He should run. He doesn't."),
    ("Kael in the teal-lit wreck, turned around in alarm, and behind him in the torn hull opening a tall dark "
     "silhouette of a figure stands motionless against the evening sky, faint glowing eyes.",
     "Kael spins around; the camera pushes past his shoulder toward the tall silhouette in the torn hull, which "
     "slowly tilts its head; dust swirls in the light.", 5,
     "Then the wreck answers."),
]
CHOICE = {"question": "Something is standing behind him.", "options": {"A": "Turn and face it", "B": "Grab the core and run"}}


def paint(prompt: str, ref: bytes | None) -> bytes:
    inp = [{"type": "text", "text": prompt}]
    if ref:
        inp.insert(0, {"type": "image", "data": base64.b64encode(ref).decode(), "mime_type": "image/jpeg"})
        inp[1]["text"] = ("Keep this exact character design (face, hair, suit) and this exact art style. " + prompt)
    out = gemini._post(f"{gemini.API}/interactions", {
        "model": gemini.IMAGE_MODEL, "input": inp,
        "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "9:16",
                            "image_size": gemini.IMAGE_SIZE}})
    raw = gemini._find_image(out)
    if not raw:
        raise RuntimeError("no picture")
    return raw


def keys():
    OUT.mkdir(parents=True, exist_ok=True)
    sheet = OUT / "kael-ref.jpg"  # one character portrait every keyframe copies
    if not sheet.exists():
        sheet.write_bytes(paint(f"{LOOK} Vertical 9:16. Character portrait, waist up, facing three-quarters, neutral "
                                f"background. {KAEL} {NO_TEXT}", None))
    ref = sheet.read_bytes()
    for i, (pic, _, _, _) in enumerate(SHOTS, 1):
        path = OUT / f"key{i}.jpg"
        if not path.exists():
            path.write_bytes(paint(f"{LOOK} Vertical 9:16. {KAEL} {WORLD} Scene: {pic} {NO_TEXT}", ref))
            print("key", i)
    print(f"keyframes ~${0.034 * (len(SHOTS) + 1):.2f}")


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def video():
    s = Series.load("driftborn")
    spent = 0.0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips = []
        for i, (_, motion, secs, text) in enumerate(SHOTS, 1):
            shot = OUT / f"shot{i}.mp4"
            if not shot.exists():
                shot.write_bytes(animate((OUT / f"key{i}.jpg").read_bytes(),
                                         f"{LOOK} {KAEL} Action: {motion} Lively, fluid character animation with "
                                         f"clear full-body movement, not a still image. Sound: only ambient sound "
                                         f"effects (wind, creaking metal, hum). No music, no dialogue.", secs))
                spent += secs * PRICE_PER_SECOND
                print("shot", i)
            ov = tmp / f"ov{i}.png"
            reel.caption_overlay(s, text, 1).save(ov)
            has_audio = "audio" in subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                                                   "-of", "csv=p=0", str(shot)], capture_output=True, text=True).stdout
            out = tmp / f"c{i}.mp4"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(shot), "-i", str(ov), "-f", "lavfi", "-i",
                 "anullsrc=r=48000:cl=stereo", "-filter_complex",
                 f"[0:v]scale={reel.W}:{reel.H}:force_original_aspect_ratio=increase,crop={reel.W}:{reel.H},"
                 f"fps={reel.FPS}[v];[v][1]overlay=0:0,format=yuv420p[vo];"
                 + ("[0:a][2:a]amix=inputs=2:duration=first[ao]" if has_audio else "[2:a]anull[ao]"),
                 "-map", "[vo]", "-map", "[ao]", "-t", str(secs), "-c:v", "libx264", "-crf", "19",
                 "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out)])
            clips.append(out)
        cc = tmp / "card.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(ROOT / "out/cards/driftborn-card-1.png"), "-f",
             "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "4", "-vf", "format=yuv420p", "-r", str(reel.FPS),
             "-c:v", "libx264", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(cc)])
        clips.append(cc)
        n = len(clips)
        joined = tmp / "joined.mp4"
        run(["ffmpeg", "-v", "error", "-y", *sum((["-i", str(c)] for c in clips), []), "-filter_complex",
             "".join(f"[{k}:v][{k}:a]" for k in range(n)) + f"concat=n={n}:v=1:a=1[v][a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "19", "-c:a", "aac", str(joined)])
        secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     str(joined)], capture_output=True, text=True, check=True).stdout)
        pad = reel.pad(secs, tmp / "pad.wav", seed=2)
        final = OUT / "driftborn-animated.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(joined), "-i", str(pad), "-filter_complex",
             "[1:a]volume=0.7[p];[0:a][p]amix=inputs=2:duration=first[a]", "-map", "0:v", "-map", "[a]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(final)])
    print(f"{final}  {secs:.1f} s  video spent about ${spent:.2f}")


if __name__ == "__main__":
    {"keys": keys, "video": video}[sys.argv[1]]()
