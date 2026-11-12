"""Profile pictures and pinned posts for the 4 story accounts (pure HTML/CSS rendered by Edge, no AI images).

    python make_images.py   -> images/<series>-profile.png (1080x1080), -pin1.png and -pin2.png (1080x1350)

pin1 = the series poster ("meet the character"), pin2 = "How this works: you decide".
Character art comes later from the episode pipeline; these use type and simple shapes so they work on day one.
"""
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "images"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
FONTS = ("https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@400;700&family=Special+Elite"
         "&family=Inter:wght@500;800&family=Cinzel+Decorative:wght@700;900&family=Cormorant+Garamond:wght@600;700"
         "&family=Orbitron:wght@600;900&family=Space+Grotesk:wght@500;700&display=block")

# Profile pictures the owner chose from Gemini art (images/gemini/), kept as they are
CUSTOM_PROFILE = {"driftborn": "gemini/driftborn-abstract-debris.jpg"}

S = {
    "compliant": dict(
        title="COMPLIANT", tag="YOU DECIDE", hero="Ezra Vale", role="Citizen 213 · Ministry Records Clerk",
        hook="He deletes people for a living.<br>Then he found his sister's file.",
        a="comply", b="copy the file", bg="#EFE6D2", fg="#111111", acc="#C8102E", acc2="#39FF88",
        hf="'Bebas Neue'", bf="'IBM Plex Mono'", mark="eye",
        rule="Rebel or builder. Every choice is yours."),
    "last-draft": dict(
        title="THE LAST DRAFT", tag="YOU DECIDE WHO LIVES", hero="Cole Mercer", role="Chemistry teacher · Day 731",
        hook="A teacher. 5 students.<br>1 stranger with a gun.<br>300 miles to the safe zone.",
        a="tell the group", b="keep her secret", bg="#2B2B2B", fg="#E8E1D3", acc="#D9692B", acc2="#3E6E6E",
        hf="'Special Elite'", bf="'Inter'", mark="roster",
        rule="Anyone can die. Even him."),
    "roll-for-fate": dict(
        title="ROLL FOR FATE", tag="YOU CHOOSE · DICE DECIDE", hero="Wren Ashby", role="Disgraced squire · Order of the Lantern",
        hook="Thrown out of the knighthood<br>for a crime she didn't commit.",
        a="follow the raven", b="break into the vault", bg="#1C1A2E", fg="#F1E3C3", acc="#C9A227", acc2="#7A1F3D",
        hf="'Cinzel Decorative'", bf="'Cormorant Garamond'", mark="d20",
        rule="Risky moves get a real random d20 roll."),
    "driftborn": dict(
        title="DRIFTBORN", tag="YOU DECIDE HIS FATE", hero="Kael Torvin", role="Scrap diver · Mining moon Hollow",
        hook="He hears the Current.<br>The Concord hunts those who do.",
        a="sell the core", b="hide it", bg="#0E1A2B", fg="#E9C896", acc="#2EC4B6", acc2="#B5532A",
        hf="'Orbitron'", bf="'Space Grotesk'", mark="planet",
        rule="Train it. Hide it. Join them. Or don't."),
}


def mark(kind, c):
    """A simple logo mark per series, in inline SVG."""
    if kind == "eye":
        return f'''<svg viewBox="0 0 200 200"><path d="M10 100 Q100 20 190 100 Q100 180 10 100Z" fill="none" stroke="{c['fg']}" stroke-width="10"/>
<circle cx="100" cy="100" r="38" fill="{c['acc']}"/><circle cx="100" cy="100" r="14" fill="{c['fg']}"/></svg>'''
    if kind == "roster":
        dots = "".join(f'<circle cx="{25 + i * 25}" cy="100" r="10" fill="{c["fg"]}"/>' for i in range(7))
        return f'''<svg viewBox="0 0 200 200"><circle cx="100" cy="100" r="88" fill="none" stroke="{c['acc']}" stroke-width="8"/>{dots}
<path d="M64 88 L86 112 M86 88 L64 112" stroke="{c['acc']}" stroke-width="7"/></svg>'''
    if kind == "d20":
        return f'''<svg viewBox="0 0 200 200"><polygon points="100,10 182,55 182,145 100,190 18,145 18,55" fill="none" stroke="{c['acc']}" stroke-width="8"/>
<polygon points="100,40 155,130 45,130" fill="none" stroke="{c['acc']}" stroke-width="5"/>
<text x="100" y="118" text-anchor="middle" font-family="Cinzel Decorative" font-weight="900" font-size="44" fill="{c['fg']}">20</text></svg>'''
    return f'''<svg viewBox="0 0 200 200"><circle cx="100" cy="100" r="60" fill="{c['acc2']}"/>
<ellipse cx="100" cy="100" rx="95" ry="24" fill="none" stroke="{c['acc']}" stroke-width="8" transform="rotate(-18 100 100)"/>
<path d="M45 92 A60 60 0 0 1 155 92" fill="none" stroke="{c['fg']}" stroke-width="3" opacity=".5"/></svg>'''


BASE = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{fonts}"><style>
html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:{bg};color:{fg};font-family:{bf},sans-serif}}
.c{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}}
h1{{font-family:{hf};margin:0;line-height:1;color:{fg}}}
.tag{{font-family:{bf};letter-spacing:6px;color:{acc};font-weight:700}}
.grain{{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(0,0,0,.035) 0 2px,transparent 2px 4px);pointer-events:none}}
.frame{{position:absolute;inset:36px;border:4px solid {acc}}}
.opt{{display:flex;gap:24px;align-items:center;font-size:44px;margin:14px 0;font-weight:700}}
.opt b{{display:inline-flex;width:84px;height:84px;align-items:center;justify-content:center;background:{acc};color:{bg};font-family:{hf};font-size:56px}}
</style></head><body>{body}<div class="grain"></div>
<script>/* shrink any heading that's wider than the frame until it fits */
document.fonts.ready.then(() => document.querySelectorAll("h1").forEach(h => {{
  h.style.whiteSpace = "nowrap"; let px = parseFloat(getComputedStyle(h).fontSize);
  while (h.scrollWidth > {w} - 200 && px > 20) {{ px -= 2; h.style.fontSize = px + "px"; }} }}));</script></body></html>"""


def render(name, w, h, body, c):
    src = OUT / f"_{name}.html"
    src.write_text(BASE.format(fonts=FONTS, w=w, h=h, body=body, **c), encoding="utf-8")
    out = OUT / f"{name}.png"
    out.unlink(missing_ok=True)
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}",
                    "--virtual-time-budget=8000", f"--user-data-dir={Path(tempfile.gettempdir()) / 'story-series-edge'}",
                    "--no-first-run", "--disable-extensions", f"--screenshot={out}", src.as_uri()],
                   check=False, capture_output=True, timeout=120)
    for _ in range(40):  # Edge returns before it finishes writing the file
        if out.exists() and out.stat().st_size > 1000:
            break
        time.sleep(0.5)
    src.unlink()
    print(out.name, out.stat().st_size if out.exists() else "FAILED")


def render_profile(slug, c, size):
    # Instagram crops the profile picture to a circle: keep everything inside the middle ~720 px
    render(f"{slug}-profile", 1080, 1080, f"""<div class="c"><div style="width:440px;height:440px">{mark(c['mark'], c)}</div>
<h1 style="font-size:{int(size * 0.5)}px;margin-top:20px;max-width:640px">{c['title']}</h1></div>""", c)


def main():
    OUT.mkdir(exist_ok=True)
    for slug, c in S.items():
        size = 110 if len(c["title"]) > 10 else 150
        if slug in CUSTOM_PROFILE:  # the owner picked Gemini art for this one: don't overwrite it
            print(f"{slug}-profile.png kept (from {CUSTOM_PROFILE[slug]})")
        else:
            render_profile(slug, c, size)
        if slug in CUSTOM_PROFILE:  # the chosen art, as a round badge, instead of the drawn mark
            emblem = (f'<img src="{CUSTOM_PROFILE[slug]}" style="width:400px;height:400px;border-radius:50%;'
                      f'margin:40px 0 20px;box-shadow:0 0 0 6px {c["acc2"]},0 0 60px {c["acc"]}55">')
        else:
            emblem = f"""<div style="width:300px;height:300px;margin:50px 0 30px">{mark(c['mark'], c)}</div>"""
        render(f"{slug}-pin1", 1080, 1350, f"""<div class="frame"></div><div class="c" style="padding:0 90px">
<div class="tag" style="font-size:34px">{c['tag']}</div>
{emblem}
<h1 style="font-size:{int(size * 1.15)}px">{c['title']}</h1>
<div style="font-size:64px;font-family:{c['hf']};margin-top:60px;color:{c['acc']}">{c['hero']}</div>
<div style="font-size:34px;opacity:.8;margin-top:10px">{c['role']}</div>
<div style="font-size:46px;line-height:1.35;margin-top:60px">{c['hook']}</div>
<div style="font-size:32px;margin-top:70px;letter-spacing:3px;color:{c['acc']}">EPISODE 1 · PINNED</div></div>""", c)
        render(f"{slug}-pin2", 1080, 1350, f"""<div class="frame"></div><div class="c" style="padding:0 110px;align-items:flex-start;text-align:left">
<div class="tag" style="font-size:34px">{c['title']}</div>
<h1 style="font-size:120px;margin:20px 0 50px">HOW THIS<br>WORKS</h1>
<div style="font-size:44px;line-height:1.4">Every episode ends on a choice.</div>
<div class="opt" style="margin-top:40px"><b>A</b><span>{c['a']}</span></div>
<div class="opt"><b>B</b><span>{c['b']}</span></div>
<div style="font-size:44px;line-height:1.4;margin-top:40px"><span style="color:{c['acc']};font-weight:700">Comment A or B.</span> Voting closes in 24 h.<br>
Most votes wins. No votes? The story chooses, and we'll always tell you.</div>
<div style="font-size:40px;margin-top:40px;opacity:.85">{c['rule']}</div></div>""", c)


if __name__ == "__main__":
    main()
