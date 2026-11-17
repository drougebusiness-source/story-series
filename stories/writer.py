"""Writes the next episode as JSON with Gemini, from the series bible, the canon so far and the vote result.

Episode JSON (what the Reel builder reads):
{
  "n": 3, "title": "Static",
  "opening": "YOU CHOSE B (63%)",          # made by code, never by the model
  "chosen": "B",                            # the option this episode follows ("" for episode 1)
  "scenes": [{"image": "...", "text": "...", "seconds": 5}, ...],
  "death": false,                           # true: a character dies, the next episode REWINDs
  "choice": {"question": "...", "options": {"A": "...", "B": "..."}, "risky": {"B": 14}},   # null when death
  "canon": "one line for CANON.md",
  "caption": "Instagram caption, without the vote line and hashtags (code adds them)"
}
Horror format (series.yaml `format: horror`, 3amchoicess-style, see HORROR-FORMAT.md) adds:
  "arc": 2, "part": 3,                      # made by code: short story arcs of 2-4 parts
  "arc_title": "The Last Car",              # from the model, the same for every part of an arc
  "arc_end": true,                          # from the model: this part lands the arc's twist
  "narrated": true                          # each scene "text" is a spoken narrator line (also the caption)
"""
from __future__ import annotations

import json
import secrets

from . import gemini
from .series import ROOT, Series

MIN_SECONDS, MAX_SECONDS = 35, 75
MAX_TEXT = 140
# horror format: ~80 s narrated parts, many short shots, 2-4 parts per arc
HORROR_MIN_SECONDS, HORROR_MAX_SECONDS = 60, 90
HORROR_SCENES = (8, 14)
HORROR_MAX_TEXT = 160
MAX_ARC_PARTS = 4
WORDS_PER_SECOND = 3.0   # a narrator can't say more than this; more words need more seconds


def is_horror(series: Series) -> bool:
    return series.cfg.get("format") == "horror"


def arc_position(prev: dict | None) -> tuple[int, int]:
    """(arc, part) for the next episode: a new arc starts after an episode marked arc_end."""
    if prev is None:
        return 1, 1
    arc, part = int(prev.get("arc") or 1), int(prev.get("part") or 1)
    return (arc + 1, 1) if prev.get("arc_end") else (arc, part + 1)


def roll_d20() -> int:
    return secrets.randbelow(20) + 1


def decision(series: Series, prev: dict | None, result: dict | None) -> dict:
    """What this episode follows: {"kind": "first"|"vote"|"ai"|"rewind", "chosen": letter|"", "opening": str,
    "rolls": {letter: (dc, roll)}}."""
    if prev is None:
        return {"kind": "first", "chosen": "", "opening": "", "rolls": {}}
    if prev.get("death"):
        # the death came from the choice asked one episode earlier: rewind to that choice
        return {"kind": "rewind", "chosen": "", "died_on": prev.get("chosen", ""), "opening": "REWIND", "rolls": {},
                "options": list((prev.get("asked") or {}).get("options", {})) or ["A", "B", "C"]}
    opts = list((prev.get("choice") or {}).get("options", {}))
    rolls = _rolls(series, prev)
    if result and result.get("winner"):
        w = result["winner"]
        return {"kind": "vote", "chosen": w, "opening": f"YOU CHOSE {w} ({result['share']}%)", "rolls": rolls,
                "options": opts}
    why = "TIE" if result and result.get("total") else "NO VOTES"
    return {"kind": "ai", "chosen": "", "why": why, "opening": "", "rolls": rolls, "options": opts}


def _rolls(series: Series, prev: dict) -> dict:
    if not series.cfg.get("dice"):
        return {}
    risky = (prev.get("choice") or {}).get("risky") or {}
    return {k: (int(dc), roll_d20()) for k, dc in risky.items()}


def story_path(eps: list[dict]) -> list[str]:
    """The letters chosen so far, in order (FLOW.md's path codes). A rewind replaces the choice that killed."""
    path: list[str] = []
    for e in eps:
        if e.get("decided_by") == "rewind" and path:
            path[-1] = e.get("chosen", "")
        elif e.get("chosen"):
            path.append(e["chosen"])
    return path


def house_style() -> str:
    """The Head Writer's craft guide (WRITING.md, copied from agent-office/hq/WRITING.md)."""
    p = ROOT / "WRITING.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def build_prompt(series: Series, n: int, prev: dict | None, d: dict, recent: list[dict]) -> str:
    recent_txt = "\n".join(f"- Ep {e['n']} \"{e['title']}\": followed {e.get('chosen') or '(start)'}; "
                           f"asked: {(e.get('choice') or {}).get('question', '(death)')} "
                           f"{json.dumps((e.get('choice') or {}).get('options', {}))}" for e in recent[-4:])
    if d["kind"] == "first":
        what = "This is EPISODE 1. Follow episode 1 of SEASON1.md."
    elif d["kind"] == "rewind":
        what = (f"Episode {prev['n']} ended in a death after option {d['died_on']} of this choice: "
                f"{json.dumps(prev.get('asked'))}. That death is undone. This episode is a REWIND: open on the same "
                f"choice point, then play out a DIFFERENT option (if there were 3, pick the most interesting one). "
                f"Set \"chosen\" to that letter.")
    elif d["kind"] == "vote":
        what = (f"The audience voted {d['chosen']} on episode {prev['n']}'s choice. This episode shows option "
                f"{d['chosen']} happening and its consequences. Set \"chosen\" to \"{d['chosen']}\".")
    else:
        what = (f"Nobody won the vote on episode {prev['n']} ({d['why']}). YOU choose which option happens: the one "
                f"that makes the best story AND fits who the main character has become so far. Set \"chosen\" to "
                f"that letter. Options were: {json.dumps(prev['choice']['options'])}.")
    dice = ""
    if d.get("rolls"):
        dice = "Dice (d20) for risky options, already rolled: " + "; ".join(
            f"if {k} happens: needed {dc}+, rolled {r} = {'SUCCESS' if r >= dc else 'FAILURE'}"
            for k, (dc, r) in d["rolls"].items()) + ". Honour the result: a FAILURE goes wrong."
    horror = is_horror(series)
    if horror:
        arc, part = arc_position(prev)
        intro = f"""You write one PART of "{series.title}", told in the HORROR FORMAT: a 60-90 second narrated Instagram Reel
(a narrator speaks every line in SECOND PERSON, "you"; the same words appear as captions on dark still pictures).
The audience votes on what happens next. This is arc {arc}, part {part} (an arc is 2-{MAX_ARC_PARTS} parts in one
place over one night or one stretch of road, and ends on a twist).

=== HORROR FORMAT (overrides the house guide where they differ) ===
{series.root_text('HORROR-FORMAT.md')}
"""
    else:
        intro = f"""You write one episode of "{series.title}", an interactive story told as a 45-75 second Instagram Reel
(captions on still pictures, no narration). The audience votes on what happens next.
"""
    return intro + f"""
=== HOUSE WRITING GUIDE (how every episode must read: hooks, open loops, rhythm, planted twists, the ban list) ===
{house_style()}

=== SERIES BIBLE ===
{series.text('BRAND.md')}

=== SEASON PLAN (an outline; votes may take the story elsewhere, then continue in the same spirit) ===
{series.text('SEASON1.md')}

=== BRANCH MAP for the first episodes (path codes: one letter per vote) ===
{series.text('FLOW.md') or '(none)'}
Votes so far, as a path code: {'-'.join(story_path(recent)) or '(none yet: this is the start)'}{(' then ' + d['chosen'] + ' (this episode)') if d.get('chosen') else ''}
While the story is still on the branch map, this episode IS the matching node: follow its beats and use its vote
options word for word (the dice and ☠ marks too). Once past the map, continue from SEASON1.md and the canon.

=== CANON SO FAR (never contradict) ===
{series.text('CANON.md')}

=== RECENT EPISODES ===
{recent_txt or '(none yet)'}

=== THIS EPISODE: number {n} ===
{what}
{dice}

{horror_rules(prev) if horror else ""}Rules:
- {"%d to %d scenes, 3 to 9 seconds each, %d-%d seconds in total" % (*HORROR_SCENES, HORROR_MIN_SECONDS, HORROR_MAX_SECONDS) if horror else f"5 to 8 scenes, 4 to 8 seconds each, {MIN_SECONDS}-{MAX_SECONDS} seconds in total"}.
- Each scene "text" is the on-screen caption{" AND the narrator's spoken line" if horror else ""}: at most {HORROR_MAX_TEXT if horror else MAX_TEXT} characters, in the series' voice and written to
  the house guide: scene 1 hooks in the first 2 seconds, every caption makes sense alone AND pulls the viewer into
  the next one, behavior over labels, varied rhythm (never a run of two-word fragments), nothing from the ban list.
- Each scene "image" describes ONE picture for an illustrator: who is there (use the character names from the
  bible), what they're doing, the setting, the light and the camera framing. Vertical 9:16. No text in pictures.
  No gore: deaths and violence are implied (a shadow, a cut away, an empty chair), never shown.
- End on a cliffhanger and a choice: "choice" has "question" (short) and "options" A and B (and C only for big
  moments), each under 40 characters, both genuinely tempting. Make at most ONE option deadly; to mark a deadly or
  risky option for the dice, add "risky": {{"B": 14}} (DC 10-17){' (this series rolls dice)' if series.cfg.get('dice') else ' (only used for the record)'}.
- If the chosen path kills the main character or a major character, set "death": true, make the last scene the
  death (implied), and set "choice" to null. Use this rarely and only when the chosen option was risky.
- "canon": one line saying what happened and what changed (who knows what, who is dead, what the hero now believes).
- "caption": 1-2 short sentences that tease the episode; no hashtags, no vote line.

Answer with JSON only:
{{"title": str, "chosen": str, "scenes": [{{"image": str, "text": str, "seconds": int}}], "death": bool,
 "choice": {{"question": str, "options": {{"A": str, "B": str}}, "risky": {{}}}} or null, "canon": str, "caption": str{', "arc_title": str, "arc_end": bool' if horror else ''}}}"""


def horror_rules(prev: dict | None) -> str:
    arc, part = arc_position(prev)
    if part == 1:
        where = ('Part 1 of a NEW arc: open with "Imagine you\'re..." or drop the viewer straight into the place, '
                 "name it, give the time, and plant the clue the twist will pay off. Pick a short new \"arc_title\". "
                 "Take this arc's place and dilemma from the next beat of SEASON1.md.")
    else:
        where = (f"Part {part} of the arc \"{(prev or {}).get('arc_title', '')}\": keep that arc_title. Scene 1's line "
                 'starts "You chose to..." and says the chosen option in plain words.')
    land = (f'This is part {part}, the LAST allowed: land the twist now and set "arc_end": true.'
            if part >= MAX_ARC_PARTS else
            'Set "arc_end": true only on the part that lands the twist (parts 2-4); otherwise false.')
    return f"""Horror format rules:
- {where}
- {land}
- Write every line for the ear: second person ("you", "your"), present tense, short spoken sentences, at most
  {WORDS_PER_SECOND:g} words per second of the scene's "seconds". Sound and silence are tools ("Silence.",
  "Then, someone knocks.").
- One shot per line: 8-14 pictures, each one clear subject in a dark scene with ONE light source. Close-ups of
  hands, faces, doors, phones. The viewer is Cole, so show Cole only from behind, his hands, or his reflection.
- The last two scenes read the options out loud: "Option A, ..." then "Option B, ... Comment A or B." The last
  scene of an arc_end part still asks the vote (it opens the next arc) and adds "Follow for the next night."
"""


def validate(ep: dict, d: dict, horror: bool = False, part: int = 1) -> list[str]:
    errs = []
    scenes = ep.get("scenes") or []
    lo, hi = (HORROR_SCENES[0] - 1, HORROR_SCENES[1] + 2) if horror else (4, 9)
    if not lo <= len(scenes) <= hi:
        errs.append(f"{len(scenes)} scenes (want {'%d-%d' % HORROR_SCENES if horror else '5-8'})")
    total = sum(int(s.get("seconds", 0)) for s in scenes)
    tmin, tmax = (HORROR_MIN_SECONDS, HORROR_MAX_SECONDS) if horror else (MIN_SECONDS, MAX_SECONDS)
    if not tmin - 5 <= total <= tmax + 5:
        errs.append(f"{total} s in total (want {tmin}-{tmax})")
    max_text = HORROR_MAX_TEXT if horror else MAX_TEXT
    for i, s in enumerate(scenes, 1):
        if not s.get("image") or not s.get("text"):
            errs.append(f"scene {i} is missing image or text")
        if len(s.get("text", "")) > max_text + 20:
            errs.append(f"scene {i} text is {len(s['text'])} characters")
        if horror and len(s.get("text", "").split()) > WORDS_PER_SECOND * max(1, int(s.get("seconds", 0))) + 2:
            errs.append(f"scene {i} has too many words for {s.get('seconds')} s of narration")
    if horror:
        if not ep.get("arc_title"):
            errs.append("missing arc_title")
        if part >= MAX_ARC_PARTS and not ep.get("arc_end"):
            errs.append(f"part {part} is the last allowed part of an arc: set arc_end true and land the twist")
    if ep.get("death"):
        if ep.get("choice"):
            errs.append("a death episode can't have a choice")
    else:
        opts = ((ep.get("choice") or {}).get("options") or {})
        if set(opts) not in ({"A", "B"}, {"A", "B", "C"}):
            errs.append(f"options must be A,B or A,B,C, got {sorted(opts)}")
    if d["kind"] in ("ai", "rewind") and ep.get("chosen") not in (d.get("options") or ["A", "B", "C"]):
        errs.append(f"chosen must be one of the previous options, got {ep.get('chosen')!r}")
    if d["kind"] == "rewind" and ep.get("chosen") == d.get("died_on"):
        errs.append("a rewind must follow a different option than the one that died")
    if not ep.get("canon") or not ep.get("title"):
        errs.append("missing title or canon")
    return errs


def write_episode(series: Series, prev: dict | None, result: dict | None, recent: list[dict], ask=gemini.write_json) -> dict:
    n = (prev["n"] + 1) if prev else 1
    d = decision(series, prev, result)
    prompt = build_prompt(series, n, prev, d, recent)
    horror = is_horror(series)
    arc, part = arc_position(prev)
    for attempt in range(3):
        ep = ask(prompt)
        if d["kind"] == "vote":
            ep["chosen"] = d["chosen"]
        if d["kind"] == "first":
            ep["chosen"] = ""
        if horror and part > 1 and prev and prev.get("arc_title"):
            ep["arc_title"] = prev["arc_title"]   # one title per arc
        errs = validate(ep, d, horror, part)
        if not errs:
            break
        prompt += f"\n\nYour last answer had problems: {'; '.join(errs)}. Fix them and answer again."
    else:
        raise RuntimeError(f"episode {n} failed checks 3 times: {errs}")
    if d["kind"] == "ai":
        d["opening"] = f"{d['why']}. THE STORY CHOSE {ep['chosen']}."
    if d["kind"] == "rewind":
        d["opening"] = f"REWIND. THIS TIME: {ep['chosen']}."
    roll = d["rolls"].get(ep.get("chosen", ""))
    # the choice this episode answered (a rewind answers the same one the death episode did)
    asked = (prev.get("asked") if prev.get("death") else prev.get("choice")) if prev else None
    ep.update(n=n, opening=d["opening"], decided_by=d["kind"], vote=result, asked=asked,
              roll={"dc": roll[0], "rolled": roll[1]} if roll else None)
    if horror:
        ep.update(arc=arc, part=part, arc_end=bool(ep.get("arc_end")), narrated=True)
    return ep
