# The weekly loop (owner, 2026-11-19)

One episode per series every **Monday, Wednesday and Friday evening** (Central):
6 PM COMPLIANT (@citizen.213), 7 PM THE LAST DRAFT (@lastdraft.survival), 8 PM ROLL FOR FATE (@roll.for.fate),
9 PM DRIFTBORN (@driftborn.saga). Episode 1 of all four goes out Friday 2026-11-20.

**Video check: ON**
(While ON, the owner OKs each finished batch of videos before it's queued. The owner turns it OFF by saying so;
then a video that passes the quality gate is queued on its own. Scripts ALWAYS need the owner's OK.)

## The cycle

| Step | When (Central) | Who / where | What happens |
|---|---|---|---|
| 1. Post | Mon/Wed/Fri 6-9 PM | GitHub "Post episode" | Posts release `<series>-epN` if it's there, opens the vote. Missing = skipped (posts next slot). |
| 2. Votes close | Noon the day before the next episode: **Sun** (for Fri), **Tue** (for Mon), **Thu** (for Wed) | GitHub "Count votes" (~12:10 PM) | Counts A/B comments up to the close, saves `result` in `<series>/state.json`. |
| 3. Write | Same day, ~12:45 PM | PC task "Sloane, next story episodes" | Pulls the votes, writes `<series>/cartoon/epN.yaml` for each series, one script review file, one approval item. |
| 4. Owner OKs the scripts | Any time that afternoon/evening | Agent Office Approve button | (hq/approvals.md item "Story EPN scripts".) |
| 5. Render | Every 2 h, 7 AM-11 PM, once approved | PC task "Story episodes: render and queue" | `render.py <series> epN` → quality gate. PASS → `review/EPN-<SERIES>.mp4`. |
| 6. Owner OKs the videos | Before the post slot | Agent Office Approve button | Only while Video check is ON (item "Story EPN videos"). |
| 7. Queue | Right after 6 (or 5 when OFF) | same render task | `python publish.py <series> epN` → GitHub release → step 1 posts it. |

Deadline: a series whose episode isn't queued by its slot just skips that slot and posts at the next one; the
vote stays open meanwhile (the post job only ever posts the next episode in order). Nothing is ever made up.

## Rules the scheduled jobs follow
- The vote is the story. `result.winner` A/B picks what happens; no winner (no votes, tie, or a comment-read error)
  = the writer chooses the more dramatic option and the episode says "The story chose". Never ignore a winner.
- ROLL FOR FATE: an option marked "(roll 13+)" that wins is rolled in code, once:
  `.venv/Scripts/python -c "import secrets; print(secrets.randbelow(20) + 1)"`, written into the script
  (a comment line `# d20 roll: 14 (needed 13+)`) and shown on screen. Never re-roll.
- Every script follows WRITING.md, the series' BRAND.md / SEASON1.md / FLOW.md / CANON.md, the episode-1 YAML
  format (`<series>/cartoon/ep1.yaml`), the locked voices in `cartoon/voices.yaml` (OWNER PICK: never change),
  the existing sets in `cartoon/sets.yaml` (same place = same look), and the short form: 15-29 s, open on a
  "Last time, you chose…" beat, end with the question spoken over the vote screen: "Vote A or B in the comments."
- After a vote is used, append the canon line to `<series>/CANON.md`:
  `- Ep N "Title" (audience voted B, 12-5 | no votes: story chose A): what happened.`
- Renders: `NO_NEW_VIDEO=1` for word/sound fixes, never filter voices, never post without `PASS.json`.
- Costs: Gemini art/animation is prepaid; ElevenLabs credits reset monthly (the 22nd). If credits run out, stop and
  tell the owner; never buy anything.
- Git: the GitHub jobs commit `state.json`. Always `git pull --rebase` before work and before pushing.
