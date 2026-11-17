"""Driftborn 2D test in a flat adult-animation comedy look (see driftborn/LOOK-2D.md). Original designs only.

    python cartoon_sample.py keys     -> out/cartoon/kael-2d.jpg + key<n>.jpg  (~$0.17; check them first)
    python cartoon_sample.py video    -> out/cartoon/driftborn-2d.mp4          (~14 s of video, ~$1.00)
"""
import base64
import io
import sys

from PIL import Image

import animated_sample as base
from animated_sample import paint
from stories import gemini
from stories.series import ROOT

OUT = ROOT / "out" / "cartoon"
LOOK = ("Frame from an adult animated sci-fi TV comedy, flat 2D cel animation: even dark outlines, flat colour fills "
        "with one hard-edged shadow tone, no gradients or painterly texture on characters; simple rounded character "
        "designs with big round eyes and small dot pupils, slightly droopy lids; dark blue-grey and plum sets lit "
        "by cyan screen glow, saturated neon effects; clean TV composition. Original characters and designs only, "
        "not from any existing show.")
KAEL = ("Kael: lanky teenage guy, brown skin, spiky black hair, brass goggles pushed up on his forehead, a black "
        "breath mask hanging at his neck, rust-orange jumpsuit with dark brown panels and teal stripes, utility belt, "
        "long dark gloves and boots.")
DROID = ("a small rusty dome-headed scavenger droid the size of a dog, one big round cyan lens eye, two spindly arms, "
         "dented orange paint.")
WORLD = "Setting: the dark tilted interior of a ninety-year-old crashed freighter."

SHOTS = [  # (keyframe picture, motion, seconds, caption) paced like the reference: hold, action burst, reaction hold
    ("Medium shot inside the dark wreck: Kael creeps forward holding up a wrist lamp, its beam on a glowing teal "
     "cylindrical data core resting in debris ahead; cables hang from the ceiling.",
     "Kael tiptoes two steps toward the glowing core, eyes darting side to side, then slowly reaches out one finger. "
     "Locked camera. Limited TV animation: held poses, only small movements.", 4,
     "Okay. Don't touch the glowing thing."),
    ("Close-up of Kael's gloved fingertip touching the glowing teal data core, which is starting to crackle with "
     "bright cyan energy.",
     "The core erupts: a huge bright cyan energy blast fills the frame with crackling arcs and sparks, blowing "
     "debris past the camera. Fast, punchy effects animation.", 3,
     "He touched the glowing thing."),
    ("Medium shot: Kael standing stiffly in the dark wreck, face covered in soot, hair smoking and standing straight "
     "up, goggles cracked, blank wide-eyed stare straight at the camera.",
     "Kael holds completely still and stares blankly; a thin wisp of smoke rises from his hair; after a beat he "
     "blinks once, slowly. Locked camera. Mostly held frame.", 4,
     "..."),
    (f"Medium shot: Kael still sooty and frozen in the foreground, and behind him {DROID} has popped up out of the "
     "debris, staring at him with its glowing lens.",
     "The little droid tilts its head, its lens zooms in and out with a whirr, then it raises one spindly arm and "
     "gives a tiny wave. Kael's eyes slowly slide sideways toward it without moving his head. Locked camera.", 3,
     "Something in the wreck is awake."),
]


def keys():
    OUT.mkdir(parents=True, exist_ok=True)
    ref_path = OUT / "kael-2d.jpg"
    if not ref_path.exists():  # redesign the sheet's Kael in the 2D look, then every keyframe copies that
        sheet = Image.open(ROOT / "characters" / "kael" / "sheet-3.webp").convert("RGB")
        buf = io.BytesIO()
        sheet.save(buf, "JPEG", quality=92)
        prompt = (f"Redraw the character from this sheet in a completely different art style: {LOOK} Keep the same "
                  f"outfit, colours and hair, but simplify him into the flat 2D comedy style. Vertical 9:16, full body "
                  f"standing, three-quarter view, plain dark grey background. {KAEL} {base.NO_TEXT}")
        out = gemini._post(f"{gemini.API}/interactions", {
            "model": gemini.IMAGE_MODEL,
            "input": [{"type": "image", "data": base64.b64encode(buf.getvalue()).decode(), "mime_type": "image/jpeg"},
                      {"type": "text", "text": prompt}],
            "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "9:16",
                                "image_size": gemini.IMAGE_SIZE}})
        ref_path.write_bytes(gemini._find_image(out))
    ref = ref_path.read_bytes()
    for i, (pic, *_rest) in enumerate(SHOTS, 1):
        path = OUT / f"key{i}.jpg"
        if not path.exists():
            path.write_bytes(paint(f"{LOOK} Vertical 9:16. {KAEL} {WORLD} Scene: {pic} {base.NO_TEXT}", ref))
            print("key", i)
    print(f"keyframes ~${0.034 * (len(SHOTS) + 1):.2f}")


def video():
    base.OUT, base.LOOK, base.KAEL, base.SHOTS = OUT, LOOK, KAEL, SHOTS
    base.video()
    (OUT / "driftborn-animated.mp4").replace(OUT / "driftborn-2d.mp4")
    print(OUT / "driftborn-2d.mp4")


if __name__ == "__main__":
    {"keys": keys, "video": video}[sys.argv[1]]()
