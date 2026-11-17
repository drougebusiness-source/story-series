"""A creature flying in and landing, animated in code instead of by the video model (which kept teleporting the
raven and changing its size, 5 tries on 2026-11-17). Deterministic: it can't pop, teleport or change size.
    python glide.py <series> <shot n> "<creature description>" [x,y]   (x,y: roughly where it perches, 0-1)
Needs key<n+1>.jpg (the creature already perched, e.g. the next shot's first frame). Makes:
  key<n>.jpg   that picture with the creature painted out (Gemini edit)
  shot<n>.mp4  a gliding sprite of the creature flies in along a smooth curve, lands on its perch and swaps to the
               perched pose, ending exactly on key<n+1>.jpg
"""
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

import cartoon
import render
from cartoon import ROOT, paint, _jpeg


def _largest(mask: np.ndarray):
    """The largest 8-connected True region (simple flood fill; no scipy on this PC)."""
    seen = np.zeros_like(mask, bool)
    best, h, w = None, *mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack, pts = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        stack.append((yy, xx))
        if best is None or len(pts) > len(best):
            best = pts
    if not best:
        return None
    out = np.zeros_like(mask, bool)
    ys, xs = zip(*best)
    out[list(ys), list(xs)] = True
    return out


def _fit(img: Image.Image, size, z: float, dx: int, dy: int) -> Image.Image:
    """img zoomed by z about its centre and shifted by (dx, dy), cropped back to size."""
    W, H = size
    big = img.resize((int(W * z), int(H * z)), Image.LANCZOS)
    out = Image.new(img.mode, size)
    out.paste(big, (int((W - big.width) / 2 + dx), int((H - big.height) / 2 + dy)))
    return out


def _align(plate: Image.Image, ref: Image.Image) -> Image.Image:
    """Zoom/shift plate to best match ref (brute force on small greyscale copies)."""
    W, H = ref.size
    sw, sh = 135, 240
    r = np.asarray(ref.convert("L").resize((sw, sh)), np.float32)
    small = plate.convert("L").resize((sw, sh))
    best = (1e18, 1.0, 0, 0)
    for z in np.linspace(0.92, 1.08, 17):
        for dx in range(-8, 9):
            for dy in range(-8, 9):
                c = np.asarray(_fit(small, (sw, sh), z, dx, dy), np.float32)
                err = np.abs(c[12:-12, 12:-12] - r[12:-12, 12:-12]).mean()
                if err < best[0]:
                    best = (err, z, dx, dy)
    err, z, dx, dy = best
    print(f"aligned plate: zoom {z:.3f}, shift {dx * W / sw:.0f},{dy * H / sh:.0f} px (error {err:.1f})")
    return _fit(plate, (W, H), z, int(dx * W / sw), int(dy * H / sh))


def _img(b: bytes) -> Image.Image:
    return Image.open(io.BytesIO(b)).convert("RGB")


def main(slug: str, n: str, creature: str, near: str = "", secs="2.4"):
    secs = float(secs)
    render._env("GEMINI_API_KEY")
    n = int(n)
    e = cartoon.Episode(slug, "ep1")
    d = ROOT / "out" / "cartoon" / f"{slug}-ep1"
    end = Image.open(d / f"key{n + 1}.jpg").convert("RGB")
    W, H = end.size
    plate_f = d / f"key{n}.jpg"
    plate = Image.open(d / f"plate{n}.jpg").convert("RGB") if (d / f"plate{n}.jpg").exists() else _img(paint(
        f"Image 1: remove the {creature} completely and paint the background behind it so it looks like it was never "
        f"there. Change NOTHING else: same people, poses, framing, colours, lighting and style, pixel for pixel. "
        f"{cartoon.NO_TEXT}", [_jpeg(d / f"key{n + 1}.jpg")])).resize((W, H))
    plate.save(d / f"plate{n}.jpg", quality=95) if not (d / f"plate{n}.jpg").exists() else None
    plate = _align(plate, end)                          # the edit nudges the framing: line it up with the original
    plate.save(plate_f, quality=95)
    # the perched creature = where the two pictures differ (largest blob)
    e_a, p_a = np.asarray(end, np.int16), np.asarray(plate, np.int16)
    diff = np.abs(e_a - p_a).sum(2)
    gone = diff > 45                                     # what changed most between the picture and the plate
    if near:            # where it perches: "x,y" (a rough spot) or "x0,y0,x1,y1" (its box), as fractions of the frame
        v = [float(t) for t in near.split(",")]
        if len(v) == 2:
            v = [v[0] - 0.13, v[1] - 0.09, v[0] + 0.13, v[1] + 0.09]
        win = np.zeros_like(gone)
        win[max(0, int(H * v[1])):int(H * v[3]), max(0, int(W * v[0])):int(W * v[2])] = True
        gone = (diff > 18) & win                         # a looser threshold inside the window catches all of it
        m = Image.fromarray((gone * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.MinFilter(11))
        m = Image.fromarray(((np.asarray(m) > 0) & win).astype(np.uint8) * 255)
    else:
        m = Image.fromarray((gone * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(9))
    lab = np.asarray(m) > 0
    blob = _largest(lab)                                 # the largest dark blob that vanished
    if blob is None:
        raise SystemExit("could not find the creature in the picture")
    m = Image.fromarray((blob * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
    ys, xs = np.nonzero(blob)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    print("creature box", x0, y0, x1, y1)
    box = (int(x0) - 6, int(y0) - 6, int(x1) + 6, int(y1) + 6)
    perched = end.crop(box).convert("RGBA")
    alpha = m.crop(box).filter(ImageFilter.GaussianBlur(1.2))
    perched.putalpha(alpha)
    pw, ph = perched.size
    # the gliding pose, keyed off a green background
    gf = d / f"glide{n}.png"
    g = Image.open(gf).convert("RGB") if gf.exists() else _img(paint(f"The {creature} from image 1, flying with its wings spread wide in a smooth glide, side view, facing "
                   f"left, the same art style and colours as image 1. Alone on a plain pure bright green (#00FF00) "
                   f"background, nothing else. {cartoon.NO_TEXT}", [_jpeg(d / f"key{n + 1}.jpg")]))
    g.save(gf) if not gf.exists() else None
    a = np.asarray(g, np.int16)
    green = (a[..., 1] > 150) & (a[..., 1] - np.maximum(a[..., 0], a[..., 2]) > 60)
    gy, gx = np.nonzero(~green)
    glide = g.convert("RGBA")
    glide.putalpha(Image.fromarray(((~green) * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)))
    glide = glide.crop((gx.min(), gy.min(), gx.max() + 1, gy.max() + 1))
    scale = (pw * 1.9) / glide.width                     # a real wingspan is ~2.5x the body                     # wings spread: a bit wider than the perched bird
    glide = glide.resize((max(1, int(glide.width * scale)), max(1, int(glide.height * scale))), Image.LANCZOS)
    def centroid(im):                                    # body centre = centre of the solid pixels
        a_ = np.asarray(im.getchannel("A"), np.float32)
        ys_, xs_ = np.nonzero(a_ > 128)
        return float(xs_.mean()), float(ys_.mean())
    pcx, pcy = centroid(perched)
    gcx, gcy = glide.width * 0.42, glide.height * 0.55   # the body, not the wings (side view, facing left)
    land = (box[0] + pcx, box[1] + pcy)                  # the perched body's centre on screen
    start = (W + glide.width, land[1] - H * 0.35)        # off the top right
    fps, total = cartoon.reel.FPS, int(secs * cartoon.reel.FPS)
    pre = int(0.5 * fps)                                 # a beat of the scene before the swoop
    fly = int(0.8 * fps)                                 # a quick cartoon swoop (owner 11-17: the slow slide was terrible)

    def pos(t):
        e_ = 1 - (1 - t) ** 2.2
        return (start[0] + (land[0] - start[0]) * e_, start[1] + (land[1] - start[1]) * (e_ ** 0.7))

    def ghost(im, a_):
        g_ = im.copy(); g_.putalpha(g_.getchannel("A").point(lambda v: int(v * a_))); return g_
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for k in range(total):
            fr = plate.copy().convert("RGBA")
            if k < pre:
                pass
            elif k < pre + fly:                          # swoop in along a curve, with a short motion trail
                t = (k - pre + 1) / fly
                for lag, a_ in ((3, 0.12), (2, 0.22), (1, 0.38)):   # the trail: where it just was, fading
                    tt = max(0.0, t - lag * 0.09)
                    x, y = pos(tt)
                    fr.alpha_composite(ghost(glide, a_), (int(x - gcx), int(y - gcy)))
                x, y = pos(t)
                fr.alpha_composite(glide, (int(x - gcx), int(y - gcy)))
            elif False:                                  # (no crossfade: two half-see-through birds looked broken)
                w = (k - pre - fly + 1) / 4
                g2 = glide.resize((max(1, int(glide.width * 0.75)), max(1, int(glide.height * 0.75))))
                g2.putalpha(g2.getchannel("A").point(lambda v: int(v * (1 - w))))
                p2 = perched.copy(); p2.putalpha(p2.getchannel("A").point(lambda v: int(v * w)))
                fr.alpha_composite(g2, (int(land[0] - gcx * 0.75), int(land[1] - gcy * 0.75)))
                fr.alpha_composite(p2, box[:2])
            else:
                fr = end.convert("RGBA")                 # exactly the next shot's first frame
            fr.convert("RGB").save(tmp / f"f{k:04d}.jpg", quality=93)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", str(tmp / "f%04d.jpg"),
                        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(d / f"shot{n}.mp4")], check=True)
    print(d / f"shot{n}.mp4")


if __name__ == "__main__":
    main(*sys.argv[1:])
