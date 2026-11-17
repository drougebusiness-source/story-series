# COMPLIANT 2D: the angular propaganda-thriller look

Designed 2026-11-12 (`theme_design.py compliant`). Target is the *type* of animation in a stylised, angular adult 2D
spy/noir thriller series, with shapes borrowed from constructivist poster design. Copy the technique only; every
character, emblem and place is original. Sample sheet: `out/themes/compliant-sheet.jpg`.

Driftborn is rounded, droopy and comic. COMPLIANT is the opposite: sharp, tall, rigid and cold.

## What it is
- **Flat 2D cel, angular shapes.** Lean, tall characters with sharp jaws, narrow noses and small almond eyes. Thin
  clean black outlines, flat fills, no gradients.
- **Hard black shadow shapes.** Big solid-black shadow blocks, often splitting a face down the middle (half-lit).
  Shadows are graphic shapes, not soft shading. They make the look and they stay stable in video.
- **Strict palette.** Ink Black `#111111`, Paper Cream `#EFE6D2`, concrete greys (`#6B6A63`, `#3A3A36`), Ministry
  Red `#C8102E`. Monitor Green `#39FF88` appears only as screen light and Underground secrets. Red always means the
  Ministry; green always means a secret.
- **Sets are concrete and screens:** brutalist pillars, endless identical desks, red banners with an abstract emblem,
  a giant watching eye on a wall screen. Hard low light throws long diagonal shadows across floors.
- **Faint print grain on backgrounds only.** Characters stay perfectly flat so they don't flicker when animated.
- **Limited animation.** Characters hold rigid poses; only eyes, mouth or one hand move. Stillness is the point:
  in Meridian, nobody moves unless they have to.

## Camera and editing
- **Locked, symmetrical wides** of the records floor (people as tiny identical units), then a hard cut to a tight,
  half-lit close-up. The scale jump is the drama.
- **Bold diagonals:** low or high angles on the city, banners and shadows cutting the frame. No orbits, no handheld.
- Slow push-ins on Ezra when he is thinking. Cuts on stamps, clicks and screen flashes.
- Shots through screens and camera feeds (the Ministry is always watching) are cheap and on-theme.
- About 30 s per episode: 2 s establishing wide, long holds on faces, quick inserts (stamp, file, screen), end on a
  frozen half-lit face for the vote.

## Acting
- Ezra is upright and tidy; he gets smaller and more hunched as the guilt grows. Crane barely moves and smiles.
  Kols's red visor hides his eyes; he turns his head slowly. Juno is the only one who moves loosely (suspicious).
- Fear is shown with light, not big gestures: the green screen glow taking over half of Ezra's face.

## Cast and sets (painted once, reused everywhere)
- Cast refs: `characters/ezra` (style anchor), `mira`, `director` (Halden Crane), `juno`, `officer` (Brann Kols).
  Folder names follow `cartoon.py`: first word of the name. Static is a voice only and has no picture.
- Sets: `compliant/cartoon/sets.yaml` → `records_floor`, `clerk_desk`, `meridian_street`.
- New characters and sets must use `characters/ezra/2d.jpg` as the style reference (not Kael's).

## Prompt block (every 2D COMPLIANT keyframe and shot)
Frame from an adult animated dystopian thriller series, flat 2D cel animation in a stylised, angular graphic style
that borrows the shapes of constructivist poster design: lean angular character designs with sharp jaws, narrow noses
and small almond eyes, clean thin black outlines, flat colour fills with large hard-edged solid black shadow shapes so
faces are half in shadow, no gradients; a strict limited palette of ink black, warm paper cream, concrete greys and
Ministry red, with acid green only for screen light; bold diagonal compositions; very faint print grain on backgrounds
only. Original characters and designs, not from any existing show.
