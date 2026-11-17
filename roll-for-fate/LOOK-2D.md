# ROLL FOR FATE 2D: the cosy storybook-adventure look

Designed 2026-11-12 (`theme_design.py roll-for-fate`). Target is the *type* of animation in a warm 2D fantasy
adventure cartoon: flat cel characters in front of painted storybook backgrounds. Copy the technique only; every
character, emblem and place is original (nothing from any existing show or tabletop game). Sample sheet:
`out/themes/roll-for-fate-sheet.jpg`.

Driftborn is dark sci-fi with black outlines. ROLL FOR FATE is warm, golden and drawn with brown lines.

## What it is
- **Cel characters on painted backgrounds.** Characters are flat 2D with clean **warm dark-brown outlines (never
  black)**, flat fills and one soft cel shadow tone. Backgrounds look like gouache book illustration with soft
  visible brushwork.
- **Chunky, appealing, exaggerated shapes** and big readable faces: Wren short and square in too-big armour,
  Fennick long and bendy, Brunhild wide as a door, Osric all robe and nerves, Crows sleek with a white feather.
- **Palette:** Parchment `#F1E3C3`, Forest `#2F5D3A`, Gold `#C9A227`, Wine `#7A1F3D`, Night Ink `#1C1A2E`. Day scenes
  glow parchment-gold; night scenes are ink-blue with warm lantern pools.
- **Light comes from lanterns and torches** (the Order of the Lantern): warm gold pools against cool blue shadow.
- **Limited animation, comic timing.** Holds, then a snappy reaction: a double-take, a raven wing flourish.
- Dice moments can use the d20 card overlay; the painting itself stays free of text.

## Camera and editing
- **Storybook framing:** wide establishing shots like a book page, then mediums for dialogue. Gentle slow pans and
  push-ins; no orbits.
- Scene changes can use an ink-map wipe (done in editing, not by the video model).
- About 30 s per episode: page-like wide, two or three medium dialogue beats, a reaction hold for the joke or the
  twist, end on Wren's face (or Crows's smug one) for the vote.

## Acting
- Wren: stubborn scowl, fists, stomps; hates asking for help. Crows: half-closed eyes, theatrical wing gestures,
  tilts his head when lying. Fennick: flourishes his lute, cringes when a sung lie comes true. Brunhild: arms folded,
  says little. Osric: wide nervous eyes, the skeletal mouse peeks out. Maelle: stands tall and still with the staff.

## Cast and sets (painted once, reused everywhere)
- Cast refs: `characters/wren` (style anchor), `crows`, `fennick`, `brunhild`, `osric`, `sister` (Maelle).
  Folder names follow `cartoon.py`: first word of the name.
- Sets: `roll-for-fate/cartoon/sets.yaml` → `lantern_hall`, `stable_night`, `vault_corridor`.
- New characters and sets must use `characters/wren/2d.jpg` as the style reference (not Kael's).
- Note: Crows came out with a white plume rather than a single feather; that is now his design, keep it.

## Prompt block (every 2D ROLL FOR FATE keyframe and shot)
Frame from a cosy fantasy-adventure animated series, 2D cel animation over painted backgrounds: characters with
chunky, appealing, exaggerated shapes and big expressive faces, clean warm dark-brown outlines (not black), flat colour
fills with one soft cel shadow tone; backgrounds painted like a classic gouache storybook illustration with soft
visible brushwork; warm parchment-gold light, rich forest greens, gold and wine red, deep ink-blue night shadows.
Original characters and designs, not from any existing show or game.
