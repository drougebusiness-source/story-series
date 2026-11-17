"""Kael, rigged from his character sheet, acting out a short scene over a painted background.

    python rig_kael.py          (once: cut the sheet into parts)
    python puppet2.py frame     -> out/puppet/test-frame.png
    python puppet2.py           -> out/puppet/kael-rig.mp4
"""
import math
import subprocess
import sys

from PIL import Image

from stories import reel
from stories.series import ROOT, Series

W, H, FPS = 1080, 1920, 30
P = ROOT / "characters" / "kael" / "parts"
OUT = ROOT / "out" / "puppet"
G = 1.75  # rig units (sheet pixels at head scale) -> screen pixels


def load(name, scale=1.0, rotate=0):
    im = Image.open(P / f"{name}.png").convert("RGBA")
    s = G * scale
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    return im.rotate(rotate, expand=True, resample=Image.BICUBIC) if rotate else im


def paste_rot(frame, im, pivot, at, angle=0.0):
    px, py = pivot
    pad = int(math.hypot(im.width, im.height)) + 4
    big = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    big.paste(im, (int(pad - px), int(pad - py)))
    if angle:
        big = big.rotate(angle, resample=Image.BICUBIC, center=(pad, pad))
    frame.alpha_composite(big, (int(at[0] - pad), int(at[1] - pad)))


def rot(v, deg):
    r = math.radians(-deg)  # PIL rotates counter-clockwise on screen
    return (v[0] * math.cos(r) - v[1] * math.sin(r), v[0] * math.sin(r) + v[1] * math.cos(r))


class Kael:
    def __init__(self):
        self.torso = load("torso", 1.27)
        self.head = load("head")
        self.leg = load("leg", 1.1)
        # arm chain: upper arm -> elbow -> forearm -> wrist -> hand, each part rotating at its joint
        self.upper = load("sleeve", 0.82)
        self.fore = load("forearm", 0.82)
        self.hands = {h: load(f"hand_{h}", 0.9, r) for h, r in (("open", 0), ("point", -90), ("fist", 0))}
        px = self.upper.load()
        self.sleeve_rgb = px[self.upper.width // 2, int(self.upper.height * 0.25)][:3]
        cap = int(self.upper.width * 0.44)
        self.cap = Image.new("RGBA", (cap * 2 + 4, cap * 2 + 4), (0, 0, 0, 0))
        from PIL import ImageDraw
        ImageDraw.Draw(self.cap).ellipse((2, 2, cap * 2 + 1, cap * 2 + 1), fill=self.sleeve_rgb + (255,),
                                         outline=None)
        eye = 0.62
        self.eyes = {k: (load(f"eye_l{k}", eye), load(f"eye_r{k}", eye)) for k in ("", "_half", "_shut")}
        self.mouths = {k: load(f"m_{k}", 0.5) for k in ("rest", "A", "E", "O", "wide", "teeth")}

    def arm(self, fr, shoulder, side, upper_deg, elbow_deg, wrist_deg, hand):
        """side=+1 screen-right arm, -1 screen-left (mirrored). Angles in degrees, positive swings outward."""
        U, F, Hn = self.upper, self.fore, self.hands[hand]
        if side < 0:
            U, F, Hn = (im.transpose(Image.FLIP_LEFT_RIGHT) for im in (U, F, Hn))
        a1 = side * upper_deg
        a2 = a1 + side * elbow_deg
        a3 = a2 + side * wrist_deg
        top = int(8 * G)
        l1 = U.height - int(22 * G)                       # elbow sits inside the upper sleeve's lower end
        l2 = F.height - int(16 * G)                       # wrist sits inside the cuff
        ex, ey = rot((0, l1), a1)
        elbow = (shoulder[0] + ex, shoulder[1] + ey)
        wx, wy = rot((0, l2), a2)
        wrist = (elbow[0] + wx, elbow[1] + wy)
        paste_rot(fr, U, (U.width / 2, top), shoulder, a1)
        paste_rot(fr, self.cap, (self.cap.width / 2, self.cap.height / 2), elbow, 0)
        paste_rot(fr, Hn, (Hn.width / 2, int(6 * G)), wrist, a3)          # hand under the cuff
        paste_rot(fr, F, (F.width / 2, int(10 * G)), elbow, a2)

    def draw(self, fr, x, y, *, lean=0, head_tilt=0, nod=0, arm_r=(6, 4, 0), arm_l=(6, 4, 0), hand_r="open",
             eyes="", look=0, mouth="rest"):
        """(x, y) = base of the neck on screen."""
        T, Hd = self.torso, self.head
        tor_pivot = (T.width / 2, 0)
        # legs, behind everything
        for dx in (-34, 34):
            px, py = rot((dx * G, 245 * G), lean)
            paste_rot(fr, self.leg, (self.leg.width / 2, 0), (x + px, y + py), lean)
        # arms behind the torso: the short sleeves cover the joint
        for side, (u, e, w), hand in ((-1, arm_l, "open"), (1, arm_r, hand_r)):
            px, py = rot((side * 100 * G, 165 * G), lean)
            self.arm(fr, (x + px, y + py), side, u + side * lean, e, w, hand)
        paste_rot(fr, T, tor_pivot, (x, y), lean)
        # head: pivot at the neck inside the collar
        hp = (94 * G, 232 * G)
        hx, hy = rot((0, (-8 + nod) * G), lean)
        hat = (x + hx, y + hy)
        paste_rot(fr, Hd, hp, hat, head_tilt + lean)
        # face parts, positioned in head coordinates (head piece px) and rotated with the head
        el, er = self.eyes[eyes]
        ang = head_tilt + lean
        for im, cx, cy in ((el, 63, 120), (er, 125, 120)):
            off = rot(((cx - 94 + look * 3) * G, (cy - 232) * G), ang)
            paste_rot(fr, im, (im.width / 2, im.height / 2), (hat[0] + off[0], hat[1] + off[1]), ang)
        m = self.mouths[mouth]
        off = rot(((96 - 94) * G, (183 - 232) * G), ang)
        paste_rot(fr, m, (m.width / 2, m.height / 2), (hat[0] + off[0], hat[1] + off[1]), ang)


LINES = [(1.2, 3.8, "Okay. Nobody else hears that hum... right?"), (4.6, 7.4, "It's coming from inside the wreck.")]
VIS = {"a": "A", "e": "E", "i": "E", "o": "O", "u": "O", "w": "O", "y": "E", "m": "rest", "b": "rest", "p": "rest",
       "f": "teeth", "v": "teeth", "s": "teeth", "t": "teeth"}


def mouth_at(t):
    for a, b, text in LINES:
        if a <= t < b:
            letters = [c for c in text.lower() if c.isalpha()]
            c = letters[min(len(letters) - 1, int((t - a) / (b - a) * len(letters) * 1.15) % len(letters))]
            return VIS.get(c, "A" if (int(t * 12) % 3) else "E"), text
    return "rest", None


def background():
    p = OUT / "bg-desert.jpg"
    if p.exists():
        return Image.open(p).convert("RGB")
    from stories import gemini
    raw = gemini.Painter().picture(
        "Background painting for a 2D animated TV series, no characters: a rust-orange desert on a mining moon at "
        "dusk, a huge crashed freighter half-buried in the dunes in the middle distance with a torn hull glowing "
        "faint teal inside, a giant ringed planet in a teal sky, matte painted with angular simplified shapes, "
        "clean edges, soft atmospheric haze, muted colours, cinematic. Lower third is open sand foreground. "
        + "No people, no text.")
    im = reel.cover(raw).crop((54, 96, 54 + W, 96 + H)).convert("RGB")
    im.save(p)
    return im


def frame_at(k, bg, caps, t):
    fr = Image.new("RGBA", (W, H))
    zoom = 1.0 + 0.03 * t / 8.5
    b = bg.resize((int(W * zoom), int(H * zoom)), Image.BILINEAR)
    fr.paste(b.crop(((b.width - W) // 2, (b.height - H) // 2, (b.width - W) // 2 + W, (b.height - H) // 2 + H)))
    walk = min(1.0, t / 1.1)
    x = -260 + (560 + 260) * (1 - (1 - walk) ** 3)
    step = abs(math.sin(t * 8.5)) * 26 if t < 1.1 else 0
    breathe = math.sin(t * 2.2) * 3
    mouth, text = mouth_at(t)
    talking = text is not None
    point = max(0.0, min(1.0, (t - 4.9) / 0.3)) * (1 - max(0.0, min(1.0, (t - 7.3) / 0.35)))
    bl = t % 2.7
    eyes = "_shut" if 2.5 < bl < 2.6 else ("_half" if 2.45 < bl < 2.65 else "")
    if 3.9 < t < 4.5:
        eyes = "_half"
    k.draw(fr, x, 690 - step + breathe,
           lean=(math.sin(t * 8.5) * 3 if t < 1.1 else 0) + 2 * point,
           head_tilt=(math.sin(t * 6.5) * 2.5 if talking else math.sin(t * 1.3) * 1.2) + 5 * point,
           nod=abs(math.sin(t * 5.5)) * 4 if talking else 0,
           arm_r=(6 + 52 * point + math.sin(t * 2) * 2, 6 + 48 * point, -10 * point),
           arm_l=(6 + math.sin(t * 2.4) * 2, 8 + 4 * math.sin(t * 1.7), 3),
           hand_r="point" if point > 0.2 else "open", eyes=eyes, look=(4 if point > 0.3 else 0), mouth=mouth)
    if text:
        fr.alpha_composite(caps[text])
    return fr


def main(only_frame=False):
    OUT.mkdir(parents=True, exist_ok=True)
    s = Series.load("driftborn")
    k, bg = Kael(), background()
    caps = {text: reel.caption_overlay(s, text, 1) for *_, text in LINES}
    if only_frame:
        a, b = frame_at(k, bg, caps, 2.0), frame_at(k, bg, caps, 6.0)
        sheet = Image.new("RGB", (W * 2, H))
        sheet.paste(a.convert("RGB")), sheet.paste(b.convert("RGB"), (W, 0))
        sheet.resize((W, H // 2)).save(OUT / "test-frame.png")
        return
    n = int(8.5 * FPS)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
                           "-movflags", "+faststart", str(OUT / "kael-rig.mp4")], stdin=subprocess.PIPE)
    for i in range(n):
        ff.stdin.write(frame_at(k, bg, caps, i / FPS).tobytes())
    ff.stdin.close()
    ff.wait()
    print(OUT / "kael-rig.mp4")


if __name__ == "__main__":
    main(len(sys.argv) > 1 and sys.argv[1] == "frame")
