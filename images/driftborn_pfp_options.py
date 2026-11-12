"""Three new profile picture options for @driftborn.saga (1080x1080, safe for Instagram's circle crop).

    python images/driftborn_pfp_options.py   -> images/options/driftborn-pfp-1.png .. -3.png (+ a circle preview sheet)
"""
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "options"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
FONTS = "https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Space+Grotesk:wght@700&display=block"
RUST, SPACE, TEAL, SAND = "#B5532A", "#0E1A2B", "#2EC4B6", "#E9C896"

STARS = "".join(f'<circle cx="{(i * 397) % 1080}" cy="{(i * 631) % 1080}" r="{1 + i % 3}" fill="{SAND}" opacity="{0.25 + (i % 5) / 10}"/>'
                for i in range(70))

# 1. The diver: Kael's goggled, masked head in silhouette against a giant ringed planet, teal eyes of the Current
DIVER = f"""<svg viewBox="0 0 1080 1080" xmlns="http://www.w3.org/2000/svg">
<defs><radialGradient id="g" cx="50%" cy="38%" r="60%"><stop offset="0" stop-color="#1d3350"/><stop offset="1" stop-color="{SPACE}"/></radialGradient>
<linearGradient id="p" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d9773f"/><stop offset="1" stop-color="{RUST}"/></linearGradient>
<filter id="glow"><feGaussianBlur stdDeviation="10"/></filter></defs>
<rect width="1080" height="1080" fill="url(#g)"/>{STARS}
<circle cx="770" cy="330" r="190" fill="url(#p)"/>
<path d="M580 330 A190 190 0 0 1 960 330" fill="none" stroke="{SAND}" stroke-width="5" opacity=".25"/>
<ellipse cx="770" cy="340" rx="300" ry="48" fill="none" stroke="{TEAL}" stroke-width="12" opacity=".85" transform="rotate(-14 770 340)"/>
<!-- head and shoulders silhouette -->
<path d="M330 1080 C330 900 400 840 470 820 L470 760 C410 740 380 680 380 610 C380 510 450 450 540 450 C630 450 700 510 700 610
 C700 680 670 740 610 760 L610 820 C680 840 750 900 750 1080 Z" fill="#0b1524" stroke="{TEAL}" stroke-width="5" stroke-opacity=".55"/>
<!-- goggles -->
<rect x="410" y="560" width="260" height="70" rx="35" fill="#0a1220" stroke="{SAND}" stroke-width="6"/>
<circle cx="478" cy="595" r="28" fill="{TEAL}" filter="url(#glow)"/><circle cx="602" cy="595" r="28" fill="{TEAL}" filter="url(#glow)"/>
<circle cx="478" cy="595" r="18" fill="#bffaf3"/><circle cx="602" cy="595" r="18" fill="#bffaf3"/>
<!-- breath mask -->
<rect x="470" y="660" width="140" height="80" rx="22" fill="#1a2638" stroke="{RUST}" stroke-width="6"/>
<circle cx="505" cy="700" r="16" fill="none" stroke="{RUST}" stroke-width="5"/><circle cx="575" cy="700" r="16" fill="none" stroke="{RUST}" stroke-width="5"/>
<path d="M610 700 Q690 720 680 820" fill="none" stroke="{RUST}" stroke-width="10" stroke-linecap="round"/>
</svg>"""

# 2. The emblem: a "D" cut like a scrap-metal plate, with the Current's teal wave running through it, in a mission-patch ring
EMBLEM = f"""<svg viewBox="0 0 1080 1080" xmlns="http://www.w3.org/2000/svg">
<defs><filter id="glow"><feGaussianBlur stdDeviation="8"/></filter>
<path id="arc" d="M190 540 A350 350 0 0 1 890 540"/><path id="arc2" d="M210 560 A330 330 0 0 0 870 560"/></defs>
<rect width="1080" height="1080" fill="{SPACE}"/>{STARS}
<circle cx="540" cy="540" r="420" fill="#13233a" stroke="{RUST}" stroke-width="22"/>
<circle cx="540" cy="540" r="372" fill="none" stroke="{SAND}" stroke-width="4" opacity=".5"/>
<text font-family="Orbitron" font-weight="900" font-size="64" letter-spacing="14" fill="{SAND}"><textPath href="#arc" startOffset="50%" text-anchor="middle">DRIFTBORN</textPath></text>
<text font-family="Space Grotesk" font-weight="700" font-size="40" letter-spacing="10" fill="{TEAL}"><textPath href="#arc2" startOffset="50%" text-anchor="middle">HOLLOW · VEYRA SYSTEM</textPath></text>
<path d="M410 330 L590 330 Q760 330 760 540 Q760 750 590 750 L410 750 Z" fill="{RUST}"/>
<path d="M480 410 L580 410 Q680 410 680 540 Q680 670 580 670 L480 670 Z" fill="#13233a"/>
<circle cx="430" cy="360" r="9" fill="#13233a"/><circle cx="430" cy="720" r="9" fill="#13233a"/>
<path d="M320 560 Q380 480 440 560 T560 560 T680 560 T800 520" fill="none" stroke="{TEAL}" stroke-width="18" filter="url(#glow)"/>
<path d="M320 560 Q380 480 440 560 T560 560 T680 560 T800 520" fill="none" stroke="#bffaf3" stroke-width="7"/>
</svg>"""

# 3. The signal: a lone ship rising off the rust moon, its trail curving into a teal Current spiral
SIGNAL = f"""<svg viewBox="0 0 1080 1080" xmlns="http://www.w3.org/2000/svg">
<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{SPACE}"/><stop offset=".75" stop-color="#2a1d2b"/><stop offset="1" stop-color="#5c2d1c"/></linearGradient>
<filter id="glow"><feGaussianBlur stdDeviation="9"/></filter></defs>
<rect width="1080" height="1080" fill="url(#sky)"/>{STARS}
<circle cx="780" cy="300" r="150" fill="none" stroke="{SAND}" stroke-width="3" opacity=".35"/>
<circle cx="780" cy="300" r="120" fill="#c58a5a" opacity=".55"/>
<ellipse cx="540" cy="1080" rx="760" ry="260" fill="{RUST}"/>
<ellipse cx="540" cy="1090" rx="760" ry="230" fill="#8f3f1f"/>
<path d="M300 860 C380 700 640 760 600 600 C570 480 420 520 460 420 C500 330 640 360 660 300" fill="none" stroke="{TEAL}" stroke-width="22" stroke-linecap="round" filter="url(#glow)"/>
<path d="M300 860 C380 700 640 760 600 600 C570 480 420 520 460 420 C500 330 640 360 660 300" fill="none" stroke="#bffaf3" stroke-width="8" stroke-linecap="round"/>
<g transform="translate(672 278) rotate(35)"><path d="M0 -46 L22 22 L0 10 L-22 22 Z" fill="{SAND}"/><path d="M-8 22 L0 46 L8 22 Z" fill="{TEAL}"/></g>
<text x="540" y="1010" text-anchor="middle" font-family="Orbitron" font-weight="900" font-size="66" letter-spacing="10" fill="{SAND}">DRIFTBORN</text>
</svg>"""


def shot(name, svg):
    src = OUT / f"_{name}.html"
    src.write_text(f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}">'
                   f'<style>html,body{{margin:0;width:1080px;height:1080px;overflow:hidden}}</style></head><body>{svg}</body></html>',
                   encoding="utf-8")
    out = OUT / f"{name}.png"
    out.unlink(missing_ok=True)
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1080,1080",
                    "--virtual-time-budget=8000", f"--user-data-dir={Path(tempfile.gettempdir()) / 'story-series-edge'}",
                    "--no-first-run", "--disable-extensions", f"--screenshot={out}", src.as_uri()],
                   check=False, capture_output=True, timeout=120)
    for _ in range(40):
        if out.exists() and out.stat().st_size > 1000:
            break
        time.sleep(0.5)
    src.unlink()
    print(out.name, out.stat().st_size if out.exists() else "FAILED")


def sheet():
    """The three side by side, cropped to circles the way Instagram shows them, at real profile size and big."""
    cells = "".join(f'<div class="c"><img src="driftborn-pfp-{i}.png"><b>{i}</b><img class="s" src="driftborn-pfp-{i}.png"></div>'
                    for i in (1, 2, 3))
    src = OUT / "_sheet.html"
    src.write_text(f"""<!doctype html><html><head><style>
html,body{{margin:0;width:1500px;height:700px;background:#fafafa;font:700 40px sans-serif}}
.c{{display:inline-flex;flex-direction:column;align-items:center;width:500px;padding-top:40px}}
img{{width:440px;height:440px;border-radius:50%;box-shadow:0 0 0 2px #ddd}} .s{{width:110px;height:110px;margin-top:14px}}
b{{margin-top:10px}}</style></head><body>{cells}</body></html>""", encoding="utf-8")
    out = OUT / "driftborn-pfp-compare.png"
    out.unlink(missing_ok=True)
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1500,700",
                    "--virtual-time-budget=4000", f"--user-data-dir={Path(tempfile.gettempdir()) / 'story-series-edge'}",
                    "--no-first-run", f"--screenshot={out}", src.as_uri()], check=False, capture_output=True, timeout=120)
    for _ in range(40):
        if out.exists() and out.stat().st_size > 1000:
            break
        time.sleep(0.5)
    src.unlink()
    print(out.name)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for i, svg in enumerate((DIVER, EMBLEM, SIGNAL), 1):
        shot(f"driftborn-pfp-{i}", svg)
    sheet()
