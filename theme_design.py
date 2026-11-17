"""Design the 2D animated look ("theme") for a story series, the same way Driftborn was made: one style-anchor
portrait of the lead, every other character drawn from it, one empty set plate per location, and two sample
keyframes that drop the cast into an unchanged set. Nothing is animated here.

    python theme_design.py <series> lead     -> characters/<first>/2d.jpg for the lead (no reference)
    python theme_design.py <series> cast     -> the rest of the cast, styled from the lead's portrait
    python theme_design.py <series> sets     -> <series>/cartoon/sets/<key>.jpg from <series>/cartoon/sets.yaml
    python theme_design.py <series> keys     -> out/themes/<series>/key<n>.jpg
    python theme_design.py <series> sheet    -> out/themes/<series>-sheet.jpg (free: no pictures painted)
    python theme_design.py <series> all

Existing files are never repainted (delete one to redo it). Each picture is ~$0.034; spend is logged in
out/themes/spend-<series>.json. Folder names follow cartoon.py: the first word of the name, lower case.
"""
import json
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

from cartoon import IMG_PRICE, NO_TEXT, _jpeg, paint
from stories.series import ROOT, Series

PROTECTED = {"kael", "sola"}   # Driftborn's cast: never touch

THEMES = {
    "compliant": {
        "style": (
            "Frame from an adult animated dystopian thriller series, flat 2D cel animation in a stylised, angular "
            "graphic style that borrows the shapes of constructivist poster design: lean angular character designs "
            "with sharp jaws, narrow noses and small almond eyes, clean thin black outlines, flat colour fills with "
            "large hard-edged solid black shadow shapes so faces are half in shadow, no gradients; a strict limited "
            "palette of ink black, warm paper cream, concrete greys and Ministry red, with acid green only for screen "
            "light; bold diagonal compositions; very faint print grain on backgrounds only. Original characters and "
            "designs, not from any existing show."),
        "backdrop": "plain warm paper-cream background",
        "lead": "Ezra Vale",
        "notes": {
            "Ezra Vale": "very upright, careful posture, hands neatly at his sides, polished red pin catching the "
                         "light, an earnest, slightly anxious face",
        },
        "keys": [
            {"set": "records_floor", "cast": ["Ezra Vale", "Juno Park"],
             "frame": "Wide shot. Ezra sits upright at his desk in the front row typing, proud and content; Juno leans "
                      "over the low divider from the next desk, grinning and chatting at him, chin on her hands."},
            {"set": "clerk_desk", "cast": ["Ezra Vale"],
             "framing": "the same desk seen a little closer, a medium close-up",
             "frame": "Ezra sits frozen at the desk, his face lit acid green from the monitor below and half in hard "
                      "black shadow, eyes wide in shock, one hand hovering over a single cream file folder."},
        ],
    },
    "last-draft": {
        "style": (
            "Frame from an adult animated survival-drama series, 2D cel animation in a gritty comic-book ink style: "
            "realistic, grounded human proportions, bold heavy black ink outlines with spotted solid black shadow "
            "areas, flat desaturated colour fills in ash greys, dusty bone and dead teal, one warm orange light source "
            "per scene that casts a hard orange rim light, no gradients or painterly rendering on characters, no gore. "
            "Original characters and designs, not from any existing show."),
        "backdrop": "plain flat ash-grey background",
        "lead": "Cole Mercer",
        "notes": {
            "Cole Mercer": "a high school chemistry teacher two years into the apocalypse, tired kind eyes, he carries "
                           "no gun, a small chemistry kit satchel across his body",
        },
        "keys": [
            {"set": "school_yard", "cast": ["Cole Mercer", "Dani Ortiz", "Marcus \"Tank\" Bell"],
             "frame": "Wide shot. Cole stands in the yard with a clipboard handing out the supply-run list; Tank "
                      "stands beside him holding a bat over his shoulder; Dani stands slightly apart, tugging her "
                      "long hoodie sleeve down over her wrist."},
            {"set": "school_hallway", "cast": ["Cole Mercer", "Dani Ortiz"],
             "framing": "the same hallway, a medium shot near the lantern",
             "frame": "Cole kneels by the lantern packing his satchel and glances up, frowning, at Dani, who stands "
                      "in the orange light pulling her sleeve down and avoiding his eyes."},
        ],
    },
    "roll-for-fate": {
        "style": (
            "Frame from a cosy fantasy-adventure animated series, 2D cel animation over painted backgrounds: "
            "characters with chunky, appealing, exaggerated shapes and big expressive faces, clean warm dark-brown "
            "outlines (not black), flat colour fills with one soft cel shadow tone; backgrounds painted like a classic "
            "gouache storybook illustration with soft visible brushwork; warm parchment-gold light, rich forest "
            "greens, gold and wine red, deep ink-blue night shadows. Original characters and designs, not from any "
            "existing show or game."),
        "backdrop": "plain warm parchment background",
        "lead": "Wren Ashby",
        "notes": {
            "Wren Ashby": "the battered plate armour is clearly too big for her (it was her father's), freckles, a "
                          "stubborn scowl, a sword on her hip",
            "Crows": "a raven, full body standing on the ground, sly half-closed eyes, looks like he is lying",
        },
        "keys": [
            {"set": "lantern_hall", "cast": ["Wren Ashby", "Sister Maelle"],
             "frame": "Wide shot. Wren kneels in the middle of the hall floor without her armour, wearing only a "
                      "plain padded tunic, her armour piled on the stones beside her, head bowed and jaw clenched; "
                      "Sister Maelle stands over her holding her lantern staff, stern."},
            {"set": "stable_night", "cast": ["Wren Ashby", "Crows"],
             "framing": "the same stable, a medium shot",
             "frame": "Wren sits slumped on the hay in her plain tunic, startled and staring; Crows perches on the "
                      "top of the stall door in the lantern light, beak open as if talking, one wing raised like a "
                      "showman."},
        ],
    },
}

OUT = ROOT / "out" / "themes"


def folder(name: str) -> Path:
    first = name.split()[0].lower()
    if first in PROTECTED:
        raise SystemExit(f"{name}: folder '{first}' belongs to Driftborn; rename in THEMES")
    return ROOT / "characters" / first


def log_spend(series: str, what: str):
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / f"spend-{series}.json"
    data = json.loads(log.read_text()) if log.exists() else []
    data.append({"what": what, "usd": IMG_PRICE})
    log.write_text(json.dumps(data, indent=1))
    print(f"  painted {what}  ({series} total ${sum(d['usd'] for d in data):.2f})")


class Theme:
    def __init__(self, slug: str):
        self.slug = slug
        self.s = Series.load(slug)
        self.t = THEMES[slug]
        self.cast = self.s.cfg["characters"]
        self.sets = yaml.safe_load((self.s.dir / "cartoon" / "sets.yaml").read_text(encoding="utf-8"))
        self.lead_img = folder(self.t["lead"]) / "2d.jpg"

    def desc(self, name):
        note = self.t["notes"].get(name)
        return f"{name}, {self.cast[name]}" + (f"; {note}" if note else "")

    def lead(self):
        p = self.lead_img
        if p.exists():
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(paint(
            f"Character model sheet pose for an animated series: {self.desc(self.t['lead'])}. {self.t['style']} "
            f"Vertical 9:16, one character only, full body standing, three-quarter view, neutral pose, "
            f"{self.t['backdrop']}. {NO_TEXT}", []))
        log_spend(self.slug, f"lead {self.t['lead']}")

    def character(self, name):
        p = folder(name) / "2d.jpg"
        if p.exists():
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(paint(
            f"The image shows the exact art style to use (a different character): same line weight, shading, "
            f"proportions system, palette and rendering. Draw a NEW character in exactly that style: "
            f"{self.desc(name)}. {self.t['style']} Vertical 9:16, one character only, full body, three-quarter "
            f"view, {self.t['backdrop']}. {NO_TEXT}", [_jpeg(self.lead_img)]))
        log_spend(self.slug, f"cast {name}")

    def cast_all(self):
        for name in self.cast:
            if name != self.t["lead"]:
                self.character(name)

    def set_plate(self, key):
        p = self.s.dir / "cartoon" / "sets" / f"{key}.jpg"
        if p.exists():
            return p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(paint(
            f"The image shows the art style only. Paint an EMPTY background set in exactly that 2D style, with "
            f"no characters or people at all: {self.sets[key]} {self.t['style']} Vertical 9:16, eye-level, with open "
            f"floor space in the lower middle where characters will stand. {NO_TEXT}", [_jpeg(self.lead_img)]))
        log_spend(self.slug, f"set {key}")
        return p

    def sets_all(self):
        for key in self.sets:
            self.set_plate(key)

    def keys(self):
        d = OUT / self.slug
        d.mkdir(parents=True, exist_ok=True)
        for i, shot in enumerate(self.t["keys"], 1):
            path = d / f"key{i}.jpg"
            if path.exists():
                continue
            cast = shot["cast"]
            imgs = [_jpeg(self.set_plate(shot["set"]))] + [_jpeg(folder(c) / "2d.jpg") for c in cast]
            who = "; ".join(f"image {k + 2} is {c}" for k, c in enumerate(cast))
            path.write_bytes(paint(
                f"Image 1 is the background set: keep it EXACTLY, the same architecture, props, colours and lighting; "
                f"do not redesign, add or remove anything in it ({shot.get('framing', 'same framing as image 1')}). "
                f"{who}: keep each character design exactly (face, hair, outfit, colours). "
                f"Draw this moment in that set: {shot['frame']} {self.t['style']} Vertical 9:16. Keep heads fully "
                f"inside the frame. {NO_TEXT}", imgs))
            log_spend(self.slug, f"key{i}")

    def sheet(self):
        cfg = self.s.cfg
        bg, fg, acc = cfg["colors"]["bg"], cfg["colors"]["fg"], cfg["colors"]["accent"]
        fonts = ROOT / "assets" / "fonts"
        head = ImageFont.truetype(str(fonts / cfg["font_head"]), 64)
        small = ImageFont.truetype(str(fonts / cfg["font_head"]), 30)
        W, pad = 2400, 40

        def row(items, h):
            tiles = []
            for label, path in items:
                im = Image.open(path).convert("RGB")
                im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
                tiles.append((label, im))
            return tiles

        cast = [(n, folder(n) / "2d.jpg") for n in [self.t["lead"]] + [c for c in self.cast if c != self.t["lead"]]]
        sets = [(k, self.s.dir / "cartoon" / "sets" / f"{k}.jpg") for k in self.sets]
        keys = [(f"keyframe {i}: {k['set']}", OUT / self.slug / f"key{i}.jpg") for i, k in enumerate(self.t["keys"], 1)]

        def fit_h(items, gap=20):   # tallest tiles that still fit the width
            n = len(items)
            return int((W - 2 * pad - gap * (n - 1)) / n * 16 / 9)

        sections = [("CAST", row(cast, min(fit_h(cast), 640))), ("SETS", row(sets, min(fit_h(sets), 900))),
                    ("SAMPLE KEYFRAMES", row(keys, min(fit_h(keys), 1100)))]
        H = 140 + sum(70 + tiles[0][1].height + 60 for _, tiles in sections) + pad
        sheet = Image.new("RGB", (W, H), bg)
        dr = ImageDraw.Draw(sheet)
        dr.text((pad, 40), f"{cfg['title']}  2D LOOK", font=head, fill=fg)
        y = 140
        for title, tiles in sections:
            dr.text((pad, y), title, font=small, fill=acc)
            y += 50
            total = sum(im.width for _, im in tiles) + 20 * (len(tiles) - 1)
            x = (W - total) // 2
            for label, im in tiles:
                sheet.paste(im, (x, y))
                dr.text((x, y + im.height + 8), label.upper(), font=small, fill=fg)
                x += im.width + 20
            y += tiles[0][1].height + 80
        out = OUT / f"{self.slug}-sheet.jpg"
        sheet.save(out, quality=88)
        print("sheet", out)


if __name__ == "__main__":
    slug, step = sys.argv[1], sys.argv[2]
    th = Theme(slug)
    steps = {"lead": [th.lead], "cast": [th.lead, th.cast_all], "sets": [th.lead, th.sets_all],
             "keys": [th.lead, th.keys], "sheet": [th.sheet],
             "all": [th.lead, th.cast_all, th.sets_all, th.keys, th.sheet]}[step]
    for f in steps:
        f()
