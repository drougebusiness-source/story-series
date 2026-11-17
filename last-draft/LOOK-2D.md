# THE LAST DRAFT 2D: the inked survival-drama look

Designed 2026-11-12 (`theme_design.py last-draft`). Target is the *type* of animation in a grounded adult 2D
survival drama drawn like a gritty inked comic book. Copy the technique only; every character and place is
original. No gore, ever. Sample sheet: `out/themes/last-draft-sheet.jpg`.

Driftborn is a cartoon with bean heads; THE LAST DRAFT has real human proportions so deaths and choices feel heavy.

## What it is
- **2D cel with heavy ink.** Realistic, grounded proportions; bold black outlines; spotted solid-black shadow areas
  like comic inking. Flat fills, no soft painterly shading on characters.
- **One warm light per scene** (fire, lantern, flashlight, sunset) that throws a hard orange rim light along one side
  of each character. Everything else is cold.
- **Palette:** Ash `#2B2B2B`, Bone `#E8E1D3`, Dead Teal `#3E6E6E`, faded olive and denim, Rust Orange `#D9692B` for the
  light. Orange is always warmth and safety; teal is always danger.
- **Worn, not gory:** dirt, patched clothes, scuffs. Danger is shown with shadows, silhouettes and reactions, never
  wounds.
- **Sets:** a fortified high school (bus walls, plywood, barbed wire, tyre gardens), dim hallways lit by one lantern,
  overgrown suburbs with dead cars. Weeds in every crack.
- **Limited animation.** Small movements: breathing, a glance, a hand on a strap. Big action happens off-screen or in
  very short cuts.

## Camera and editing
- **Eye-level, steady, documentary-like.** Slow push-ins on faces at decision moments; slow pans across a ruined
  street. No orbits, no whip pans.
- Group shots show who is standing with whom (who is next to Cole matters; it's the roster).
- About 30 s per episode: an establishing wide with the day counter, two or three medium shots, one long held close-up
  for the tense beat, end on a face caught in the orange light for the vote.
- Darkness is a tool: cut to a teal-black frame with one point of light for scares.

## Acting
- Cole: tired, gentle, pushes his glasses up, looks at the kids before deciding. Dani hides her arm, avoids eyes.
  Tank is big but flinches in the dark. Owen slouches with a smirk. Priya stands square, arms folded. Rook barely
  moves and always faces the door.
- Fear is quiet: freezing, held breath, a look over the shoulder.

## Cast and sets (painted once, reused everywhere)
- Cast refs: `characters/cole` (style anchor), `dani`, `marcus` (Tank), `lily`, `owen`, `priya`, `rook`.
  Folder names follow `cartoon.py`: first word of the name.
- Sets: `last-draft/cartoon/sets.yaml` → `school_yard`, `school_hallway`, `supply_street`.
- New characters and sets must use `characters/cole/2d.jpg` as the style reference (not Kael's).
- Note: the painted bus in `school_yard` shows partial letters on its side; crop or avoid close-ups of it.

## Prompt block (every 2D LAST DRAFT keyframe and shot)
Frame from an adult animated survival-drama series, 2D cel animation in a gritty comic-book ink style: realistic,
grounded human proportions, bold heavy black ink outlines with spotted solid black shadow areas, flat desaturated
colour fills in ash greys, dusty bone and dead teal, one warm orange light source per scene that casts a hard orange
rim light, no gradients or painterly rendering on characters, no gore. Original characters and designs, not from any
existing show.
