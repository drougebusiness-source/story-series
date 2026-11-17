# DRIFTBORN: the look (from a frame-by-frame study of a reference clip)

Owner's target: the *type* of animation in a 2008-era stylized 3D TV war-cartoon. We copy the technique (lighting,
camera, pacing, shading), never its characters, designs, ships, names or dialogue. Reference clips stay private in
`reference/` (never committed; the repo is public) and are never fed to image or video models.

Measured on 486 frames (16.2 s at 30 fps), 2026-11-13.

## What it is
- **Real 3D CG, not 2D.** Characters are 3D models with a matte, painted-texture "toon" shader: soft 2-3 step
  shading, no glossy highlights, no outlines. Faces and bodies are carved in flat planes (angular jaw, cheek and brow
  planes), hair is solid sculpted shapes.
- **Muted and dark.** Mean brightness 0.28 (of 1), contrast 0.14, saturation 0.26 (low). About 17% of every frame is
  near-black; nothing ever blows out to white. Light lives in a narrow, moody mid-range.
- **Palette:** cold teal-greys and dark olive dominate (#383d38, #212f2f, #5a6a67, #141a1a, #344d4a, #60857d);
  warm accents only on skin, leather and lit windows (#9a968a, #5a554b); one soft pink-lavender sky gradient behind.
- **Light:** strong rim or back light separating characters from the set, visible light shafts through haze, cool
  ambient fill with warm practical lights in the background. Heavy atmospheric haze: the farther away, the paler and
  bluer.

## Camera and editing
- 6 shots in 16 s. Action shots are 0.6-2.3 s; a dialogue two-shot holds 7 s. Action cuts fast, talk breathes.
- **Low angles** looking up at characters (heroic), over-the-shoulder openings, a two-shot with characters at
  different depths.
- **The camera never stops:** slow drift or push in dialogue, fast whip pans and orbits in action. Motion blur on
  fast moves; foreground objects wipe across the lens to transition (a ship passes close, blurred).
- Background extras keep moving (soldiers walking, ships flying) so frames feel alive even when the leads stand
  still.

## Acting
- Full-body acting with weight: walk or run toward camera, turn the head before the body, step forward on a line.
- Dialogue gestures are few but clear: open-palm gesture, cross arms and hold, uncross on the reply. Holds of 1-3 s
  between gestures. Small head turns toward whoever speaks.

## Prompt block (use for every Driftborn keyframe and shot)
Stylized 3D CGI animated TV series frame: 3D character models with a matte hand-painted toon shader, soft 2-3 step
shading, no outlines, no glossy highlights; angular faces sculpted in flat planes; low-saturation teal-grey and dark
olive palette with warm skin and practical lights; strong rim light, hazy atmosphere with light shafts; deep crushed
shadows, no blown highlights; cinematic low camera angle; slight motion blur on movement. Original characters and
designs.
