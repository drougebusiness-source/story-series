# DRIFTBORN 2D: the adult-animation look (frame-by-frame study of reference clip 2)

Pivot (2026-11-13): the 3D route costs too much for now. Target is the *type* of animation in a modern adult
2D sci-fi comedy cartoon. Copy the technique only, never its characters, designs, names or dialogue. Reference
clips stay private in `reference/` (gitignored) and are never fed to image or video models.

Measured on all 564 frames (18.8 s at 30 fps).

## What it is
- **Flat 2D cel animation.** Even dark outlines, flat fill colours, one hard-edged shadow tone at most, no
  gradients on characters. Simple bean-shaped heads, big round eyes with tiny pupils, droopy lids.
- **Limited animation.** About 60-70% of frames are exact copies of the frame before. Characters hold a pose
  and only the mouth, eyes or one arm moves; action is drawn on twos or threes. Big movement is rare and short.
- **The motion lives in effects:** a laser beam that fills the frame, sparks, a cracking screen, a monitor
  flash. Effects are bright and saturated against a dark set.
- **Dark sets, bright accents.** Mean brightness 0.23, saturation 0.28, about 35% of the frame near-black.
  Palette: blue-greys and plum-blacks (#4e5759, #222028, #15141a, #313538, #828b86, #21373f), with
  cyan monitor light, neon red effects and acid green as accents.

## Camera and editing
- About 10 shots in 19 s. A bit of setup (0.5 s) cuts to a long held shot (4 s), then a burst of quick
  action cuts (0.2-0.7 s each), then long reaction holds (3-5 s) where characters just stare.
- **Camera is mostly locked.** Movement is a slow pan across a control room or a straight cut. No orbits.
- **Comedy is in the reaction shot:** two side-by-side characters staring blankly, a beat of silence, then a
  line on a radio. Timing does the work, not motion.
- Shots through screens and monitors (a fight seen on a TV wall) are cheap and read well.

## Prompt block (every 2D Driftborn keyframe and shot)
Adult animated TV comedy frame, flat 2D cel animation: even dark outlines, flat colour fills with one hard
shadow tone, no gradients on characters; simple rounded character designs with big round eyes and small
pupils; dark blue-grey and plum set with cyan monitor glow and saturated neon effects; locked or slowly
panning camera; limited animation with held poses. Original characters and designs.
