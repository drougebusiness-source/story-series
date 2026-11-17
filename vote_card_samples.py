"""Sci-fi hardware vote card options for Driftborn: Gemini paints a blank panel, code writes the text on its screen.

    python vote_card_samples.py   -> out/cards/driftborn-card-<n>.png  (about $0.10)
"""
from PIL import Image, ImageDraw, ImageFilter

from stories import gemini, reel
from stories.series import ROOT, Series

OUT = ROOT / "out" / "cards"
W, H = reel.W, reel.H
SCREEN = (150, 470, 930, 1480)  # where the text goes; the prompt asks for a blank screen here

BASE = ("Vertical 9:16 front view, perfectly straight-on and symmetrical, of a retro-futuristic spaceship control "
        "panel, worn and lived-in, rust-orange and gunmetal with teal light. In the middle, filling most of the frame "
        "(from about a quarter of the way down to three quarters), a large EMPTY, dark, slightly curved CRT monitor "
        "screen with a thick bolted metal bezel, glowing faintly teal, completely blank. ")
STYLES = [
    "Around it: brushed steel plates fastened with chunky hex bolts and Phillips screws, scuffed rivets, warning "
    "stripes, two small toggle switches and dials at the bottom.",
    "Around it: an exposed green-and-gold motherboard with circuit traces, capacitors, chips and ribbon cables, the "
    "screen bolted onto it with four big screws in the corners, small glowing LEDs.",
    "Around it: a battered cockpit console of dented riveted metal, bundled wires, pressure gauges, a row of chunky "
    "backlit buttons at the bottom, scratches and grime, bolts in every corner.",
]
NO_TEXT = ("Absolutely no text, letters, numbers, logos or symbols anywhere, the screen must be completely empty. "
           "Painted illustration, highly detailed.")


def screen_text(s, ep):
    """The vote on a CRT: teal glow, scanlines, monospace-feeling headings."""
    x0, y0, x1, y1 = SCREEN
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    teal, amber = (120, 255, 230), (255, 190, 110)
    head, body = (lambda n: reel._font(s.font("head"), n)), (lambda n: reel._font(s.font("body"), n))
    cx = (x0 + x1) / 2

    def centred(text, font, y, fill, width=x1 - x0 - 80, gap=1.15):
        for line in reel._wrap(d, text, font, width):
            d.text((cx - d.textlength(line, font=font) / 2, y), line, font=font, fill=fill)
            y += int(font.size * gap)
        return y

    y = centred("> INCOMING TRANSMISSION", body(34), y0 + 60, amber)
    y = centred(s.cfg.get("vote_line", "YOU DECIDE."), head(50), y + 20, teal)
    y = centred(ep["choice"]["question"], head(66), y + 30, (230, 255, 250))
    y += 50
    for letter, label in ep["choice"]["options"].items():
        d.rectangle([x0 + 60, y, x0 + 160, y + 100], outline=teal, width=5)
        lf = head(70)
        d.text((x0 + 110 - d.textlength(letter, font=lf) / 2, y + 6), letter, font=lf, fill=teal)
        yy = y + 22
        for line in reel._wrap(d, label, body(46), x1 - x0 - 260):
            d.text((x0 + 190, yy), line, font=body(46), fill=(230, 255, 250))
            yy += 54
        y = max(y + 135, yy + 30)
    y = centred("COMMENT " + " OR ".join(ep["choice"]["options"]), head(54), y + 30, amber)
    centred("Voting closes in 24 h. No votes? The story chooses.", body(30), y + 14, (170, 220, 210))
    glow = layer.filter(ImageFilter.GaussianBlur(8))
    out = Image.alpha_composite(glow, layer)
    lines = ImageDraw.Draw(out)
    for yy in range(y0, y1, 4):  # scanlines
        lines.line([(x0, yy), (x1, yy)], fill=(0, 0, 0, 60))
    return out


def main():
    s = Series.load("driftborn")
    OUT.mkdir(parents=True, exist_ok=True)
    p = gemini.Painter()
    ep = {"choice": {"question": "Something is standing behind him.",
                     "options": {"A": "Turn and face it", "B": "Grab the core and run"}}}
    for i, style in enumerate(STYLES, 1):
        raw = p.picture(BASE + style + " " + NO_TEXT)
        bg = reel.cover(raw).crop((54, 96, 54 + W, 96 + H)).convert("RGBA")
        bg.save(OUT / f"driftborn-panel-{i}.png")
        Image.alpha_composite(bg, screen_text(s, ep)).convert("RGB").save(OUT / f"driftborn-card-{i}.png")
        print("card", i)
    print(f"spent ${p.spent:.2f}")


if __name__ == "__main__":
    main()
