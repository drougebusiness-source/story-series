"""Turns an episode JSON into a 1080x1920 Reel: an opening card (the vote result), the scenes (a picture with a slow
zoom and its caption), a dice card when a roll decided things, and the choice card (or the death card).

Captions and cards are drawn here, never by the image model (AI-drawn text is unreliable). Music is a quiet
generated pad: no samples, no licences. Needs ffmpeg.
"""
from __future__ import annotations

import io
import subprocess
import tempfile
import textwrap
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .series import Series

W, H, FPS = 1080, 1920, 30
CARD_SECONDS = {"opening": 1.5, "dice": 2.2, "choice": 3.5, "death": 3.0}   # short-form (owner 11-16)


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    try:  # variable fonts: use the boldest style
        f.set_variation_by_axes([min(a["maximum"], 800) if a.get("name", b"").lower().startswith(b"w") else a["default"]
                                 for a in f.get_variation_axes()])
    except Exception:
        pass
    return f


def _rgb(hex_: str) -> tuple[int, int, int]:
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _wrap(draw, text, font, width) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def cover(raw: bytes) -> Image.Image:
    """The picture cropped to fill 9:16, 10% bigger than the frame so the slow zoom has room."""
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    tw, th = int(W * 1.1), int(H * 1.1)
    s = max(tw / im.width, th / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - tw) // 2, (im.height - th) // 2
    return im.crop((x, y, x + tw, y + th))


def placeholder(series: Series, scene: dict, i: int) -> bytes:
    """Stand-in art for previews without a Gemini key: the series colours and the picture description."""
    im = Image.new("RGB", (W, H), _rgb(series.color("bg")))
    d = ImageDraw.Draw(im)
    for k in range(0, H, 6):
        d.line([(0, k), (W, k)], fill=_rgb(series.color("accent2")) if k % 240 < 6 else None)
    f = _font(series.font("body"), 40)
    d.text((80, 200), f"ART {i}", font=_font(series.font("head"), 90), fill=_rgb(series.color("accent")))
    y = 340
    for line in textwrap.wrap(scene["image"], 34)[:14]:
        d.text((80, y), line, font=f, fill=_rgb(series.color("fg")))
        y += 56
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def caption_overlay(series: Series, text: str, n: int, hi: int | None = None) -> Image.Image:
    """The scene caption. hi: index of the word being spoken (narrated episodes), drawn in the accent colour."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bg = _rgb(series.color("bg"))
    for k in range(700):  # a soft dark fade behind the caption
        a = int(215 * min(1, k / 520))
        d.line([(0, H - 700 + k), (W, H - 700 + k)], fill=bg + (a,))
    f = _font(series.font("body"), 58)
    lines = _wrap(d, text, f, W - 160)
    y = H - 330 - (len(lines) - 1) * 74
    d.rectangle([80, y - 34, 200, y - 26], fill=_rgb(series.color("accent")))
    k = 0
    for line in lines:
        if hi is None:
            d.text((80, y), line, font=f, fill=_rgb(series.color("fg")), stroke_width=2, stroke_fill=bg)
        else:                                            # word by word, the spoken word lit up
            x = 80
            for w in line.split():
                d.text((x, y), w, font=f, fill=_rgb(series.color("accent" if k == hi else "fg")), stroke_width=2,
                       stroke_fill=bg)
                x += d.textlength(w + " ", font=f)
                k += 1
        y += 74
    d.text((80, 90), f"{series.title} / EP {n}", font=_font(series.font("head"), 40), fill=_rgb(series.color("fg")),
           stroke_width=2, stroke_fill=bg)
    return im


def card(series: Series, kind: str, ep: dict) -> Image.Image:
    bg, fg, acc = (_rgb(series.color(k)) for k in ("bg", "fg", "accent"))
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    head = lambda s: _font(series.font("head"), s)  # noqa: E731
    body = lambda s: _font(series.font("body"), s)  # noqa: E731
    d.rectangle([40, 40, W - 40, H - 40], outline=acc, width=6)

    def centred(text, font, y, fill=fg, width=W - 200, gap=1.18):
        for line in _wrap(d, text, font, width):
            d.text(((W - d.textlength(line, font=font)) / 2, y), line, font=font, fill=fill)
            y += int(font.size * gap)
        return y

    if kind == "opening" and (ep.get("vote") or {}).get("total") and ep.get("asked") and ep.get("chosen"):
        return recap_card(series, ep["asked"]["question"], ep["asked"]["options"], ep["vote"]["counts"], ep["chosen"])
    if kind == "opening":
        y = centred(series.title, head(56), 640, acc)
        centred(ep["opening"], head(118), y + 80)
    elif kind == "dice":
        r = ep["roll"]
        ok = r["rolled"] >= r["dc"]
        d.regular_polygon((W / 2, 760, 230), 6, outline=acc, width=10)
        centred(str(r["rolled"]), head(190), 640, fg)
        y = centred(f"NEEDS {r['dc']}+", body(64), 1080, fg)
        centred("SUCCESS" if ok else "FAILURE", head(130), y + 30, acc)
    elif kind == "death":
        y = centred("THAT'S HOW IT ENDS.", head(110), 700, acc)
        centred("Next episode: REWIND. Back to the choice.", body(56), y + 80)
    else:  # the choice
        ch = ep["choice"]
        y = centred(series.cfg.get("vote_line", "YOU DECIDE."), head(64), 420, acc)
        y = centred(ch["question"], head(92), y + 50)
        y += 70
        for letter, label in ch["options"].items():
            d.rectangle([110, y, 250, y + 140], fill=acc)
            lf = head(100)
            d.text((180 - d.textlength(letter, font=lf) / 2, y + 10), letter, font=lf, fill=bg)
            yy = y + 18
            for line in _wrap(d, label, body(58), W - 420):
                d.text((290, yy), line, font=body(58), fill=fg)
                yy += 66
            y = max(y + 180, yy + 40)
        y = centred("Comment " + " or ".join(ch["options"]) + ".", head(72), y + 60, acc)
        centred("Voting closes in 24 h. No votes? The story chooses.", body(46), y + 20)
    return im


def recap_card(series: Series, question: str, options: dict, counts: dict, chosen: str) -> Image.Image:
    """Last episode's vote: the question, one bar per option with its share, the winner lit up."""
    bg, fg, acc = (_rgb(series.color(k)) for k in ("bg", "fg", "accent"))
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    head = lambda s: _font(series.font("head"), s)  # noqa: E731
    body = lambda s: _font(series.font("body"), s)  # noqa: E731
    d.rectangle([40, 40, W - 40, H - 40], outline=acc, width=6)

    def centred(text, font, y, fill=fg, width=W - 200, gap=1.18):
        for line in _wrap(d, text, font, width):
            d.text(((W - d.textlength(line, font=font)) / 2, y), line, font=font, fill=fill)
            y += int(font.size * gap)
        return y

    total = sum(int(counts.get(k, 0)) for k in options) or 1
    dim = tuple((a + b) // 2 for a, b in zip(fg, bg))
    y = centred("LAST EPISODE", body(52), 560, dim)
    y = centred(question, head(80), y + 30)
    y += 60
    for letter, label in options.items():
        share = round(100 * int(counts.get(letter, 0)) / total)
        won = letter == chosen
        col = acc if won else dim
        d.text((110, y), letter, font=head(96), fill=col)
        lines = _wrap(d, label, body(50), W - 420)
        yy = y + 8
        for line in lines:
            d.text((230, yy), line, font=body(50), fill=fg if won else dim)
            yy += 58
        bar_y = yy + 14
        d.rectangle([230, bar_y, W - 230, bar_y + 46], outline=col, width=4)
        d.rectangle([230, bar_y, 230 + int((W - 460) * share / 100), bar_y + 46], fill=col)
        d.text((W - 210, bar_y - 4), f"{share}%", font=head(56), fill=col)
        y = bar_y + 110
    centred(f"YOU CHOSE {chosen}.", head(130), y + 40, acc)
    return im


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def _clip_from_image(img: Image.Image, seconds: float, out: Path, zoom: bool = False, overlay: Image.Image | None = None):
    src = out.with_suffix(".png")
    img.save(src)
    frames = int(seconds * FPS)
    if zoom:
        ov = out.with_name(out.stem + "_ov.png")
        overlay.save(ov)
        f = (f"[0]zoompan=z='1+0.09*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:"
             f"s={W}x{H}:fps={FPS}[v];[v][1]overlay=0:0,format=yuv420p")
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-loop", "1", "-i", str(ov), "-filter_complex", f,
              "-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(FPS), str(out)])
    else:
        _run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(src), "-t", f"{seconds:.2f}",
              "-vf", f"scale={W}:{H},format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
              "-r", str(FPS), str(out)])


def _clip_karaoke(img: Image.Image, seconds: float, out: Path, overlays: list[tuple[Image.Image, float]]):
    """Slow zoom on the picture with caption overlays that change over time: (overlay, start second) in order."""
    src = out.with_suffix(".png")
    img.save(src)
    frames = int(seconds * FPS)
    lst = out.with_name(out.stem + "_ov.txt")
    rows = []
    for k, (ov, t0) in enumerate(overlays):
        p = out.with_name(f"{out.stem}_ov{k:03d}.png")
        ov.save(p)
        t1 = overlays[k + 1][1] if k + 1 < len(overlays) else seconds
        rows.append(f"file '{p.as_posix()}'\nduration {max(0.04, t1 - t0):.3f}\n")
    rows.append(f"file '{p.as_posix()}'\n")                    # concat needs the last file twice
    lst.write_text("".join(rows), encoding="utf-8")
    f = (f"[0]zoompan=z='1+0.09*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:"
         f"s={W}x{H}:fps={FPS}[v];[1]fps={FPS},format=rgba[o];[v][o]overlay=0:0:eof_action=repeat,format=yuv420p")
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-f", "concat", "-safe", "0", "-i", str(lst),
          "-filter_complex", f, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
          "-r", str(FPS), str(out)])


LEAD, TAIL = 0.15, 0.3       # quiet before and after each narrated scene's line (short-form)


def pad(seconds: float, path: Path, seed: int = 0) -> Path:
    """A quiet, slightly tense minor pad, one chord every 6 s, faded in and out."""
    sr = 48000
    n = int(seconds * sr)
    t = np.arange(n) / sr
    chords = [(110.0, 130.81, 164.81), (87.31, 110.0, 130.81), (98.0, 123.47, 146.83), (82.41, 103.83, 123.47)]
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    seg = 6 * sr
    for k, start in enumerate(range(0, n, seg)):
        end = min(n, start + seg + sr)
        tt = t[start:end]
        env = np.minimum(1, np.minimum((tt - tt[0]) / 1.5, (tt[-1] - tt + 1e-9) / 1.5))
        for f in chords[(k + seed) % len(chords)]:
            for det in (0.997, 1.0, 1.003):
                out[start:end] += np.sin(2 * np.pi * f * det * tt + rng.uniform(0, 6.28)) * env
    out += rng.normal(0, 0.02, n)  # a little air
    out *= 0.05 / (np.sqrt(np.mean(out ** 2)) + 1e-9)
    fade = np.minimum(1, np.minimum(t / 1.0, (seconds - t) / 1.5))
    data = (np.clip(out * fade, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(sr)
        w.writeframes(data.tobytes())
    return path


def build(series: Series, ep: dict, pictures: list[bytes], out: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips = []

        def add(img, secs, **kw):
            p = tmp / f"c{len(clips):02d}.mp4"
            _clip_from_image(img, secs, p, **kw)
            clips.append(p)

        # no opening/recap card (owner 11-17: "it adds too much"): the first line picks up the vote inside the story
        if ep.get("roll"):
            add(card(series, "dice", ep), CARD_SECONDS["dice"])
        voice_id = None
        if ep.get("narrated"):
            from . import narrate
            voice_id = narrate.narrator(series.dir)
            if not voice_id:
                print("narrated episode but no ElevenLabs narrator or key: captions only")
        spoken = []                                      # (start second in the Reel, audio)
        for scene, raw in zip(ep["scenes"], pictures):
            if voice_id:                                 # the scene lasts as long as its narration
                audio, words = narrate.speak(scene["text"], voice_id)
                secs = LEAD + len(audio) / narrate.RATE + TAIL
                at = sum(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                               "csv=p=0", str(c)], capture_output=True, text=True).stdout)
                         for c in clips)
                spoken.append((at + LEAD, audio))
                ovs = [(caption_overlay(series, scene["text"], ep["n"], hi=None), 0.0)]
                ovs += [(caption_overlay(series, scene["text"], ep["n"], hi=k), LEAD + w0)
                        for k, (_, w0, _) in enumerate(words)]
                p = tmp / f"c{len(clips):02d}.mp4"
                _clip_karaoke(cover(raw), secs, p, ovs)
                clips.append(p)
            else:
                add(cover(raw), float(scene["seconds"]), zoom=True,
                    overlay=caption_overlay(series, scene["text"], ep["n"]))
        add(card(series, "death" if ep.get("death") else "choice", ep),
            CARD_SECONDS["death" if ep.get("death") else "choice"])
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
        silent = tmp / "video.mp4"
        _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])
        secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     str(silent)], check=True, capture_output=True, text=True).stdout)
        music = pad(secs, tmp / "pad.wav", seed=ep["n"])
        if spoken:                                       # narration over the pad, which dips under the voice
            n = int(secs * 48000)
            with wave.open(str(music)) as w:
                bed = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)[:n] / 32767
            bed = np.pad(bed, (0, max(0, n - len(bed))))
            voice = np.zeros(n, np.float32)
            talk = np.zeros(n, np.float32)
            for t0, a in spoken:
                i = int(t0 * 48000)
                a = a[: max(0, n - i)]
                voice[i:i + len(a)] += a
                talk[i:i + len(a)] = 1
            duck = np.convolve(talk, np.ones(14400) / 14400, "same")
            mix = np.clip(voice + bed * (1 - 0.5 * np.clip(duck, 0, 1)), -1, 1)
            with wave.open(str(music), "wb") as w:
                w.setnchannels(1), w.setsampwidth(2), w.setframerate(48000)
                w.writeframes((mix * 32767).astype(np.int16).tobytes())
        out.parent.mkdir(parents=True, exist_ok=True)
        level = ["-af", "loudnorm=I=-15:TP=-1.5:LRA=9"] if spoken else []   # narrated: Instagram loudness
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(music), *level, "-c:v", "copy", "-c:a", "aac",
              "-ar", "48000", "-ac", "2", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)])
    return out
