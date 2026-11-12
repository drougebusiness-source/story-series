"""One episode-1 key scene per series, drawn exactly the way episodes are drawn, to approve the art style.

    python style_samples.py [series ...]   -> out/style/<series>-art.jpg (raw) and <series>-frame.png (with caption)
"""
import sys
from pathlib import Path

from stories import reel
from stories.__main__ import pictures
from stories.series import ROOT, SLUGS, Series

OUT = ROOT / "out" / "style"
SCENES = {
    "compliant": ("Ezra Vale (Citizen 213) alone at his terminal in a vast Ministry records hall, rows of identical clerks "
                  "under hanging red banners with a giant eye symbol, his face lit red by the monitor as he freezes, "
                  "staring at the screen. Low angle, cold concrete, long shadows.",
                  "Batch 4471. Forty names. Routine. Then number 39: MIRA VALE. UNPERSON."),
    "last-draft": ("Cole Mercer in a barricaded high school hallway at golden hour, desks and lockers piled against the "
                   "windows, five teenage students behind him; in the foreground Dani Ortiz in a long-sleeved hoodie "
                   "flinches and grips her arm. Warm orange light through the gaps, teal shadows.",
                   "Day 731. Ninety degrees out. So why is Dani wearing long sleeves?"),
    "roll-for-fate": ("Wren Ashby sitting on a hay bale in a dark stable at night, her oversized armour gone, only a "
                      "lantern glowing; a sleek black raven (Crows) perched on the stall rail, head tilted, looking at "
                      "her. Moonlight through the slats, warm lantern gold against deep night blue.",
                      "\"I know who took it,\" said the raven. \"Probably.\""),
    "driftborn": ("Kael Torvin inside the dim, tilted wreck of a crashed freighter, breath mask on, goggles down, "
                  "reaching toward a sealed cylindrical data core that glows soft teal in the dark; dust in the air, "
                  "rust-orange light through a torn hull, the ringed planet visible through the gap.",
                  "Nobody else hears the hum. It's coming from inside the wreck."),
}


def main(slugs):
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0.0
    for slug in slugs:
        s = Series.load(slug)
        image, text = SCENES[slug]
        ep = {"n": 1, "scenes": [{"image": image, "text": text, "seconds": 6}]}
        (raw,), spent = pictures(s, ep, fake=False)
        total += spent
        (OUT / f"{slug}-art.jpg").write_bytes(raw)
        frame = reel.cover(raw).crop((54, 96, 54 + reel.W, 96 + reel.H)).convert("RGBA")
        frame.alpha_composite(reel.caption_overlay(s, text, 1))
        frame.convert("RGB").save(OUT / f"{slug}-frame.png")
        print(slug, "ok")
    print(f"art ${total:.2f}")


if __name__ == "__main__":
    main(sys.argv[1:] or list(SLUGS))
