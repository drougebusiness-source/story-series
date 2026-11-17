# THE LAST DRAFT goes horror: plan and handoff (2026-11-16)

Read this first if you're picking up the horror-format work in a new chat. The writing rules the model sees are in
`../HORROR-FORMAT.md`; this file is the why, the costs and what's left.

## Decision (owner, 2026-11-16)
- The owner DM'd a reel from **@3amchoicess** ("3 AM Choices | You Decide"): 62.4K followers from only 5 posts,
  parts at 510K / 684K / 1M / 1.6M / 5M views. One subway horror story told in 3 parts, each ~80 s, ending
  "Option A... Option B... Comment A or B." Same comment-vote mechanic our pipeline already has.
- The owner asked for a price, then chose to **put this format into THE LAST DRAFT (@lastdraft.survival)**. It fits
  best: survival dread, someone can die, dark scenes lit by one warm light. Compliant (political thriller), Roll for
  Fate and Driftborn stay on the old format (both became comedies on 2026-11-16, see their BRAND.md). JIC stays out (a horror tone
  would confuse a safety brand).
- **Voice: the owner will move to a bigger ElevenLabs plan** rather than go captions-only, because narration is a big
  part of why the 3amchoicess reels work.

## What the format is
See `../HORROR-FORMAT.md`. In short: the viewer is Cole ("you"), a narrator speaks every line, ~80 s parts with
8-14 dark one-light shots, short arcs of 2-4 parts in one place that end on a fair twist planted in part 1, and every
part ends with the options read aloud. SEASON1.md, CANON.md, the cast and REWINDs all stay; each SEASON1 beat
becomes one arc.

Reference transcripts and a contact sheet of the 3amchoicess parts are in
`../../agent-office/reels/done/Dfn6jwjznfz`, `.../DfqSxJlTFXv` and `../../agent-office/reels/inbox/DfyBN-ZTFdi`.

## Price (per ~80 s part)
| Item | Cost |
|---|---|
| Art: 12-15 Gemini images at ~4¢ | about $0.40-0.60 |
| Build and post (GitHub Actions, public repo) | $0 |
| Narration: ~1,100 characters (eleven_v3, 1 credit/char) | ~1,100 ElevenLabs credits |

Mon/Wed/Fri (~13 parts/month): about $6-8 art + ~14K credits. Daily like 3amchoicess (~30 parts): about $15-18 art
+ ~33K credits. The current Creator plan (131K/month) is already used up by JIC's two full videos a week, hence the
upgrade.

## Done (2026-11-16, not committed: the repo also has another chat's uncommitted cartoon work)
- `last-draft/series.yaml`: `format: horror`.
- `stories/writer.py`: horror mode. Second-person narrated prompt with HORROR-FORMAT.md fed in, 8-14 scenes,
  60-90 s, ≤3 spoken words per second checked per scene, arc/part tracking made by code (`arc`, `part`), the model
  sets `arc_title` and `arc_end`, part 4 must land the twist, and episodes get `narrated: true`. Other series
  unchanged.
- `stories/series.py`: `root_text()` reads shared files at the repo root.
- `tests/test_horror.py` (new) and the Last Draft caption test in `tests/test_pipeline.py`: 45 tests pass.

## Still to do (in order)
1. **Owner: upgrade ElevenLabs** (from Creator to the next tier) and add the key as a GitHub secret if the workflow
   doesn't have it yet.
2. **Narration in the Reel builder.** `stories/reel.py` doesn't speak yet: for an episode with `narrated: true`,
   voice each scene's `text` with one narrator voice (pick a dark, calm, close-mic voice; record it in
   `last-draft/cartoon/voices.yaml`), set each shot's length to its audio (not the model's guessed `seconds`), and
   show the caption word by word (the current word highlighted). `voice.py` at the repo root has ElevenLabs code from
   the cartoon work. Careful: another chat has uncommitted edits in reel.py.
3. **Art look: owner's call.** The approved LOOK-2D (gritty ink) can stay, just darker with one light per shot, or
   switch to the 3amchoicess flat vector look (cheaper, simpler). Ask the owner with one sample of each.
4. **Preview part 1** (`.venv/Scripts/python -m stories preview last-draft`, about $0.50 of art) and send it to the
   owner for OK. Check it against the owner's episode rules (set up the story, show entrances, clean audio,
   continuity) before sending.
5. Launch with the other series after the Nov 22 reset. Consider Mon/Wed/Fri first, daily if it takes off.
