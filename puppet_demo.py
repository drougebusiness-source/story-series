"""Cutout-puppet demo: Kael drawn once in parts (body, arms, head, eyes, mouths), moved by code over a flat background.

    python puppet_demo.py   -> out/puppet/kael-puppet.mp4   ($0: everything is drawn here)
In the real pipeline the parts come from a character sheet (Gemini or an artist) instead of these code drawings.
"""
import math
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from stories import reel
from stories.series import ROOT, Series

W, H, FPS = 1080, 1920, 30
SS = 2  # draw parts at 2x, shrink for clean edges
INK = (22, 18, 24)
LINE = 7 * SS
SKIN, SKIN_SH = (214, 160, 118), (184, 128, 92)
HAIR = (38, 30, 34)
SUIT, SUIT_SH, TEAL = (196, 92, 48), (158, 68, 36), (64, 196, 184)
BRASS, GLASS = (198, 152, 70), (120, 220, 210)


def canvas(w, h):
    im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def done(im):
    return im.resize((im.width // SS, im.height // SS), Image.LANCZOS)


def S(*v):
    return [x * SS for x in v]


# ---------- parts (each with its pivot, in part pixels) ----------
def body():
    im, d = canvas(420, 620)
    for leg_x in (120, 230):  # legs and boots
        d.rounded_rectangle(S(leg_x, 330, leg_x + 80, 560), 30 * SS, fill=SUIT_SH, outline=INK, width=LINE)
        d.rounded_rectangle(S(leg_x - 14, 520, leg_x + 96, 600), 24 * SS, fill=(70, 58, 56), outline=INK, width=LINE)
    d.polygon(S(95, 40, 325, 40, 350, 360, 70, 360), fill=SUIT, outline=INK, width=LINE)  # torso
    d.rectangle(S(80, 300, 340, 340), fill=TEAL, outline=INK, width=LINE)                  # belt stripe
    d.rounded_rectangle(S(150, 120, 270, 220), 14 * SS, fill=(90, 84, 80), outline=INK, width=LINE)  # chest rig
    for k in range(3):
        d.ellipse(S(168 + k * 32, 150, 190 + k * 32, 172), fill=TEAL if k != 1 else (240, 120, 70), outline=INK,
                  width=4 * SS)
    d.rectangle(S(118, 250, 150, 275), fill=TEAL, outline=INK, width=4 * SS)              # patch
    d.ellipse(S(140, 0, 280, 80), fill=(80, 76, 74), outline=INK, width=LINE)              # breath mask at neck
    d.ellipse(S(185, 20, 235, 62), fill=(52, 50, 50), outline=INK, width=4 * SS)
    return done(im), (210, 40)      # pivot: neck


def arm(flip=False):
    im, d = canvas(120, 330)
    d.rounded_rectangle(S(18, 10, 102, 250), 40 * SS, fill=SUIT, outline=INK, width=LINE)
    d.rectangle(S(20, 200, 100, 225), fill=TEAL, outline=INK, width=5 * SS)
    d.ellipse(S(8, 230, 112, 325), fill=(84, 70, 64), outline=INK, width=LINE)            # glove
    im = done(im)
    return (im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im), (60, 40)  # pivot: shoulder


def head():
    im, d = canvas(380, 420)
    d.ellipse(S(30, 170, 80, 240), fill=SKIN, outline=INK, width=LINE)                     # ears
    d.ellipse(S(300, 170, 350, 240), fill=SKIN, outline=INK, width=LINE)
    d.polygon(S(60, 110, 320, 110, 335, 260, 280, 360, 190, 395, 100, 360, 45, 260), fill=SKIN, outline=INK,
              width=LINE)                                                                   # long jaw face
    d.polygon(S(100, 360, 190, 395, 280, 360, 250, 380, 190, 400, 130, 380), fill=SKIN_SH)
    d.line(S(120, 300, 150, 312), fill=SKIN_SH, width=6 * SS)                              # scar
    spikes = [(40, 150), (55, 70), (95, 95), (110, 20), (160, 70), (200, 5), (230, 65), (285, 25), (290, 90),
              (340, 60), (340, 150), (300, 120), (80, 120)]
    d.polygon(S(*sum(spikes, ())), fill=HAIR, outline=INK, width=LINE)                     # spiky hair block
    for gx in (110, 230):                                                                  # goggles on forehead
        d.ellipse(S(gx - 10, 95, gx + 70, 165), fill=BRASS, outline=INK, width=LINE)
        d.ellipse(S(gx + 5, 110, gx + 55, 150), fill=GLASS, outline=INK, width=4 * SS)
    d.rectangle(S(175, 120, 225, 135), fill=BRASS, outline=INK, width=4 * SS)
    d.line(S(165, 285, 180, 300, 195, 290), fill=INK, width=5 * SS)                       # nose
    return done(im), (190, 395)     # pivot: chin


def eyes(state, look=0.0):
    im, d = canvas(380, 420)
    for ex in (120, 255):
        if state == "closed":
            d.arc(S(ex - 38, 205, ex + 38, 245), 10, 170, fill=INK, width=6 * SS)
            continue
        top = 190 if state == "open" else 212
        d.ellipse(S(ex - 40, top, ex + 40, 262), fill=(250, 248, 240), outline=INK, width=6 * SS)
        px = ex + int(look * 16)
        d.ellipse(S(px - 9, 222, px + 9, 240), fill=INK)
        if state == "half":
            d.line(S(ex - 40, top + 2, ex + 40, top + 2), fill=INK, width=7 * SS)
    d.line(S(78, 182, 160, 170), fill=INK, width=9 * SS)                                   # brows
    d.line(S(215, 170, 297, 182), fill=INK, width=9 * SS)
    return done(im)


def mouth(shape):
    im, d = canvas(380, 420)
    cx, cy = 190, 340
    if shape == "closed":
        d.line(S(cx - 40, cy, cx + 38, cy - 6), fill=INK, width=7 * SS)
    elif shape == "E":
        d.rounded_rectangle(S(cx - 45, cy - 12, cx + 45, cy + 14), 10 * SS, fill=(90, 30, 36), outline=INK,
                            width=6 * SS)
        d.rectangle(S(cx - 38, cy - 9, cx + 38, cy - 1), fill=(245, 240, 230))
    elif shape == "A":
        d.ellipse(S(cx - 34, cy - 18, cx + 34, cy + 30), fill=(90, 30, 36), outline=INK, width=6 * SS)
        d.ellipse(S(cx - 18, cy + 8, cx + 18, cy + 26), fill=(214, 96, 96))
    else:  # O
        d.ellipse(S(cx - 20, cy - 20, cx + 20, cy + 26), fill=(90, 30, 36), outline=INK, width=6 * SS)
    return done(im)


# ---------- background (flat, layered, drifts for depth) ----------
def background_layers():
    a = np.linspace(0, 1, H)[:, None]
    top, bot = np.array([40, 120, 128]), np.array([236, 150, 96])
    rows = (top * (1 - a) + bot * a).astype(np.uint8)             # (H, 3)
    sky = Image.fromarray(np.repeat(rows[:, None, :], W + 200, axis=1))
    d = ImageDraw.Draw(sky)
    d.ellipse((640, 260, 1120, 740), fill=(214, 226, 214), outline=INK, width=6)          # ringed planet
    d.ellipse((700, 330, 1060, 470), outline=(180, 196, 190), width=10)
    d.arc((470, 430, 1290, 600), 160, 380, fill=(240, 236, 214), width=14)
    far, fd = canvas(W + 300, H)
    fd.polygon(S(0, 1150, 200, 1080, 420, 1130, 700, 1040, 1000, 1110, 1380, 1060, 1380, 1920, 0, 1920),
               fill=(196, 104, 64), outline=INK, width=LINE)
    fd.polygon(S(820, 1080, 1180, 960, 1260, 990, 1300, 1100), fill=(92, 84, 84), outline=INK, width=LINE)  # wreck
    fd.polygon(S(1180, 960, 1230, 900, 1260, 990), fill=(70, 64, 66), outline=INK, width=LINE)
    near, nd = canvas(W + 400, H)
    nd.polygon(S(0, 1500, 300, 1430, 700, 1480, 1100, 1400, 1480, 1460, 1480, 1920, 0, 1920),
               fill=(222, 128, 76), outline=INK, width=LINE)
    for rx, ry in ((160, 1560), (1180, 1520), (420, 1700)):
        nd.ellipse(S(rx, ry, rx + 120, ry + 60), fill=(150, 80, 54), outline=INK, width=LINE)
    return sky, done(far), done(near)


def paste_rot(frame, part, pivot, at, angle=0.0, scale=1.0):
    im, (px, py) = part, pivot
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.BICUBIC)
        px, py = px * scale, py * scale
    pad = int(math.hypot(im.width, im.height))
    big = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    big.paste(im, (int(pad - px), int(pad - py)))
    big = big.rotate(angle, resample=Image.BICUBIC, center=(pad, pad))
    frame.alpha_composite(big, (int(at[0] - pad), int(at[1] - pad)))


LINES = [(1.0, 3.6, "Okay. Nobody else hears that hum... right?"), (4.4, 7.4, "It's coming from inside the wreck.")]


def mouth_at(t):
    for a, b, text in LINES:
        if a <= t < b:
            letters = [c for c in text.lower() if c.isalpha()]
            c = letters[min(len(letters) - 1, int((t - a) / (b - a) * len(letters)))]
            return {"a": "A", "e": "E", "i": "E", "o": "O", "u": "O"}.get(c, "closed" if c in "mbp" else "E"), text
    return "closed", None


def main():
    s = Series.load("driftborn")
    out = ROOT / "out" / "puppet"
    out.mkdir(parents=True, exist_ok=True)
    B, (AL, ALp), (AR, ARp), (HD, HDp) = body(), arm(), arm(True), head()
    Bp = B[1]
    B = B[0]
    EYES = {k: eyes(k) for k in ("open", "half", "closed")}
    MOUTHS = {k: mouth(k) for k in ("closed", "E", "A", "O")}
    sky, far, near = background_layers()
    caps = {text: reel.caption_overlay(s, text, 1) for *_, text in LINES}
    n = int(8.5 * FPS)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
                           "-movflags", "+faststart", str(out / "kael-puppet.mp4")], stdin=subprocess.PIPE)
    for i in range(n):
        t = i / FPS
        cam = 40 * t / 8.5
        fr = Image.new("RGBA", (W, H))
        fr.paste(sky.crop((int(cam * 0.3), 0, int(cam * 0.3) + W, H)))
        fr.alpha_composite(far, (-int(cam * 0.6), 0))
        walk = min(1.0, t / 1.0)
        x = -300 + (540 + 300) * (1 - (1 - walk) ** 3)       # walk on from the left, ease out
        bob = abs(math.sin(t * 9)) * 22 if t < 1.0 else math.sin(t * 2.2) * 4  # step bounce, then breathing
        neck = (x, 1010 - bob)
        talking, text = mouth_at(t)
        speaking = text is not None
        point = max(0.0, min(1.0, (t - 4.6) / 0.35)) * (1 - max(0.0, min(1.0, (t - 7.2) / 0.4)))
        lean = math.sin(t * 9) * 4 if t < 1.0 else 0
        paste_rot(fr, B, Bp, neck, angle=lean)
        paste_rot(fr, AR, ARp, (neck[0] + 108, neck[1] + 60), angle=10 + 115 * point + lean)  # pointing arm
        paste_rot(fr, AL, ALp, (neck[0] - 108, neck[1] + 60), angle=-10 + math.sin(t * 3) * 3 + lean)
        tilt = (math.sin(t * 7) * 3 if speaking else math.sin(t * 1.5) * 1.5) + (6 * point)
        nod = (abs(math.sin(t * 6)) * 6 if speaking else 0)
        head_at = (neck[0], neck[1] + 10 + nod)
        paste_rot(fr, HD, HDp, head_at, angle=tilt)
        bl = (t % 2.6)
        es = "closed" if 2.45 < bl < 2.53 else ("half" if 2.4 < bl < 2.58 else "open")
        if 3.8 < t < 4.3:
            es = "half"                                           # suspicious squint between lines
        look = 0.9 if point > 0.3 else (-0.4 if 3.7 < t < 4.4 else 0.2)
        e = eyes(es, look) if es != "closed" else EYES["closed"]
        paste_rot(fr, e, HDp, head_at, angle=tilt)
        paste_rot(fr, MOUTHS[talking], HDp, head_at, angle=tilt)
        fr.alpha_composite(near, (-int(cam * 1.2), 0))
        if text:
            fr.alpha_composite(caps[text])
        ff.stdin.write(fr.tobytes())
    ff.stdin.close()
    ff.wait()
    print(out / "kael-puppet.mp4")


if __name__ == "__main__":
    main()
