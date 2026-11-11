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
"""
from __future__ import annotations

import json
import secrets

from . import gemini
from .series import Series

MIN_SECONDS, MAX_SECONDS = 35, 75
MAX_TEXT = 140


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
    return f"""You write one episode of "{series.title}", an interactive story told as a 45-75 second Instagram Reel
(captions on still pictures, no narration). The audience votes on what happens next.

=== SERIES BIBLE ===
{series.text('BRAND.md')}

=== SEASON PLAN (an outline; votes may take the story elsewhere, then continue in the same spirit) ===
{series.text('SEASON1.md')}

=== CANON SO FAR (never contradict) ===
{series.text('CANON.md')}

=== RECENT EPISODES ===
{recent_txt or '(none yet)'}

=== THIS EPISODE: number {n} ===
{what}
{dice}

Rules:
- 5 to 8 scenes, 4 to 8 seconds each, {MIN_SECONDS}-{MAX_SECONDS} seconds in total.
- Each scene "text" is the on-screen caption: at most {MAX_TEXT} characters, punchy, in the series' voice. Scene 1
  hooks in the first 2 seconds.
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
 "choice": {{"question": str, "options": {{"A": str, "B": str}}, "risky": {{}}}} or null, "canon": str, "caption": str}}"""


def validate(ep: dict, d: dict) -> list[str]:
    errs = []
    scenes = ep.get("scenes") or []
    if not 4 <= len(scenes) <= 9:
        errs.append(f"{len(scenes)} scenes (want 5-8)")
    total = sum(int(s.get("seconds", 0)) for s in scenes)
    if not MIN_SECONDS - 5 <= total <= MAX_SECONDS + 5:
        errs.append(f"{total} s in total (want {MIN_SECONDS}-{MAX_SECONDS})")
    for i, s in enumerate(scenes, 1):
        if not s.get("image") or not s.get("text"):
            errs.append(f"scene {i} is missing image or text")
        if len(s.get("text", "")) > MAX_TEXT + 20:
            errs.append(f"scene {i} text is {len(s['text'])} characters")
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
    for attempt in range(3):
        ep = ask(prompt)
        if d["kind"] == "vote":
            ep["chosen"] = d["chosen"]
        if d["kind"] == "first":
            ep["chosen"] = ""
        errs = validate(ep, d)
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
    return ep
