"""One-off Gemini art for an account: profile picture options (square, safe for Instagram's circle crop).

    python -m stories art <series> [--n 3]   -> out/art/<series>-profile-1.png .. -n.png

Each option uses a different composition of the main character in the series' look. No text in the picture
(AI-drawn text is unreliable); the account name already shows next to the picture.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from . import gemini
from .series import ROOT, Series

OUT = ROOT / "out" / "art"

COMPOSITIONS = [
    "A close-up head-and-shoulders portrait of {hero}, looking slightly past the viewer, face fully in frame and "
    "centred, strong rim light. Plain dark background so it reads at a tiny size.",
    "{hero} seen from the waist up, small against a huge, iconic element of the setting behind them, the figure "
    "centred and the whole subject inside the middle two-thirds of the frame.",
    "A bold, simple emblem-like silhouette of {hero} in profile, one glowing accent colour, lots of empty space "
    "around it, like a vintage book-cover icon.",
]
FRAME = ("Square 1:1 image for a social media profile picture: keep every important part inside a centred circle "
         "covering the middle 80% of the frame; nothing important near the corners or edges.")


def hero(series: Series) -> tuple[str, str]:
    name, look = next(iter((series.cfg.get("characters") or {}).items()))
    return name, look


def profile_prompts(series: Series, n: int = 3) -> list[str]:
    name, look = hero(series)
    who = f"{name} ({look})"
    return [f"{series.cfg['style']} {COMPOSITIONS[i % len(COMPOSITIONS)].format(hero=who)} {FRAME} {gemini.NO_TEXT}"
            for i in range(n)]


def make_profile(series: Series, n: int = 3, painter: gemini.Painter | None = None) -> list[Path]:
    painter = painter or gemini.Painter()
    OUT.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, prompt in enumerate(profile_prompts(series, n), 1):
        raw = painter.picture(prompt, aspect="1:1")
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        side = min(im.size)
        im = im.crop(((im.width - side) // 2, (im.height - side) // 2, (im.width + side) // 2, (im.height + side) // 2))
        p = OUT / f"{series.slug}-profile-{i}.png"
        im.resize((1080, 1080), Image.LANCZOS).save(p)
        paths.append(p)
    print(f"{len(paths)} options in {OUT} (art ${painter.spent:.2f})")
    return paths
