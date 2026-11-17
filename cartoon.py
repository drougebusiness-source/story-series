"""Animated 2D episodes (look: <series>/LOOK-2D.md). Backgrounds and characters are painted ONCE and reused, so the
set and the cast stay the same in every shot and every episode.

    python cartoon.py driftborn ep1 keys    -> paints missing cast refs, set plates and keyframes (~$0.03 each)
    python cartoon.py driftborn ep1 video   -> animates the shots and cuts out/cartoon/<series>-<ep>.mp4 (~$0.07/s)

Episode files: <series>/cartoon/<ep>.yaml   Cast refs: characters/<name>/2d.jpg   Sets: <series>/cartoon/sets/<set>.jpg
Fixes:  python cartoon.py <series> <ep> recast "<Name>"  (uses <series>/cartoon/cast.yaml notes)
        python cartoon.py <series> <ep> redo 2 3 [--video-only]
"""
import base64
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from PIL import Image

from hybrid_sample import PRICE_PER_SECOND, animate
from stories import gemini, reel
from stories.series import ROOT, Series
from vote_card_samples import screen_text

STYLE = ("Frame from an adult animated sci-fi TV comedy, flat 2D cel animation: even dark outlines, flat colour fills "
         "with one hard-edged shadow tone, no gradients or painterly texture; simple rounded character designs with "
         "big round eyes and small dot pupils, slightly droopy lids; muted sets with saturated glowing accents; clean "
         "TV composition. Original characters and designs only, not from any existing show.")
NO_TEXT = "No text, letters, numbers or logos anywhere."
SOUND = " Sound: only ambient sound effects. No music, no dialogue, no voices."
IMG_PRICE = 0.034


def _jpeg(path: Path) -> bytes:
    if path.suffix.lower() in (".jpg", ".jpeg"):
        return path.read_bytes()
    import io
    buf = io.BytesIO()
    Image.open(path).convert("RGB").save(buf, "JPEG", quality=92)
    return buf.getvalue()


def paint(prompt: str, images: list[bytes]) -> bytes:
    inp = [{"type": "image", "data": base64.b64encode(b).decode(), "mime_type": "image/jpeg"} for b in images]
    inp.append({"type": "text", "text": prompt})
    out = gemini._post(f"{gemini.API}/interactions", {
        "model": gemini.IMAGE_MODEL, "input": inp,
        "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "9:16",
                            "image_size": gemini.IMAGE_SIZE}})
    raw = gemini._find_image(out)
    if not raw:
        raise RuntimeError("no picture in response")
    return raw


class Episode:
    def __init__(self, slug: str, ep: str):
        self.s = Series.load(slug)
        self.dir = self.s.dir / "cartoon"
        self.ep_name = ep
        self.ep = yaml.safe_load((self.dir / f"{ep}.yaml").read_text(encoding="utf-8"))
        self.sets = yaml.safe_load((self.dir / "sets.yaml").read_text(encoding="utf-8"))
        self.out = ROOT / "out" / "cartoon" / f"{slug}-{ep}"
        self.spent = 0.0
        look = self.s.dir / "LOOK-2D.md"   # each series' own style: the prompt block at the end of its LOOK-2D.md
        block = look.read_text(encoding="utf-8").split("## Prompt block", 1) if look.exists() else []
        global STYLE
        if len(block) == 2 and slug != "driftborn":
            STYLE = " ".join(block[1].split("\n", 1)[1].split())
        lead = next(iter(self.s.cfg["characters"])).split()[0].lower()
        self.style_ref = ROOT / "characters" / lead / "2d.jpg"
        tone = self.dir / "tone.md"           # the series' mood (owner 11-16: comedy is silly, horror is dark)
        self.tone = " ".join(tone.read_text(encoding="utf-8").split()) if tone.exists() else ""   # new characters and sets copy the lead's style

    # -- reusable assets
    def cast_ref(self, name: str) -> Path:
        first = name.split()[0].lower()
        p = ROOT / "characters" / first / "2d.jpg"
        if p.exists():
            return p
        desc = self.s.cfg["characters"][name] + self.note(name)
        style_ref = self.style_ref
        sheet = ROOT / "characters" / first / "sheet.webp"
        imgs = [_jpeg(style_ref)] + ([_jpeg(sheet)] if sheet.exists() else [])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(paint(
            f"The first image shows the exact art style to use (a different character). Draw a NEW character in "
            f"exactly that style{', based on the design sheet in the second image' if len(imgs) > 1 else ''}: "
            f"{name}, {desc}. {STYLE} Vertical 9:16, full body standing, three-quarter view, plain dark grey "
            f"background. {NO_TEXT}", imgs))
        self.spent += IMG_PRICE
        print("cast", name)
        import voice
        if name in voice.missing(self.s.dir.name):
            print(f"  !! {name} has no voice yet: add one to {self.dir / 'voices.yaml'} (brief + kokoro)")
        return p

    def note(self, name: str) -> str:
        """Extra design notes from <series>/cartoon/cast.yaml (fixes that must hold in every picture)."""
        f = self.dir / "cast.yaml"
        notes = yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}
        return f" {notes[name]}" if notes and notes.get(name) else ""

    def recast(self, name: str):
        """Repaint one character's reference with its cast.yaml note, keeping the old one as the style guide."""
        p = ROOT / "characters" / name.split()[0].lower() / "2d.jpg"
        n = 1
        while (old := p.with_name(f"2d-old{n}.jpg")).exists():
            n += 1
        p.rename(old)
        p.write_bytes(paint(
            f"Redraw this exact character in exactly the same art style, outfit and colours, but fix the design: "
            f"{name}, {self.s.cfg['characters'][name]}{self.note(name)} {STYLE} Vertical 9:16, full body standing, "
            f"three-quarter view, plain dark grey background. {NO_TEXT}", [_jpeg(old)]))
        self.spent += IMG_PRICE
        print("recast", name, "(old one kept as", old.name + ")")

    def redo(self, shots: list[int], video_only: bool = False):
        """Archive the given shots' keyframes (unless video_only) and clips, then rebuild them and the episode."""
        arch = self.out / "old"
        arch.mkdir(parents=True, exist_ok=True)
        for i in shots:
            for f in ([f"shot{i}.mp4"] if video_only else [f"key{i}.jpg", f"shot{i}.mp4"]):
                if (self.out / f).exists():
                    (self.out / f).replace(arch / f)
        self.keys()
        self.video()

    def set_plate(self, key: str) -> Path:
        p = self.dir / "sets" / f"{key}.jpg"
        if p.exists():
            return p
        p.parent.mkdir(parents=True, exist_ok=True)
        style_ref = self.style_ref
        p.write_bytes(paint(
            f"The image shows the art style only. Paint an EMPTY background set in exactly that flat 2D style, with "
            f"no characters or people at all: {self.sets[key]} {STYLE} {self.tone} Vertical 9:16, eye-level, with open floor "
            f"space in the lower middle where characters will stand. {NO_TEXT}", [_jpeg(style_ref)]))
        self.spent += IMG_PRICE
        print("set", key)
        return p

    # -- per episode
    def keys(self):
        self.out.mkdir(parents=True, exist_ok=True)
        for i, shot in enumerate(self.ep["shots"], 1):
            path = self.out / f"key{i}.jpg"
            if path.exists() or shot.get("continues"):     # continues: key is the last frame of the shot before
                continue
            cast = shot.get("cast", [])
            imgs = [_jpeg(self.set_plate(shot["set"]))] + [_jpeg(self.cast_ref(c)) for c in cast]
            who = "; ".join(f"image {k + 2} is {c}{self.note(c)}" for k, c in enumerate(cast))
            path.write_bytes(paint(
                f"Image 1 is the background set: keep it EXACTLY, the same architecture, props, colours and lighting; "
                f"do not redesign, add or remove anything in it ({shot.get('framing', 'same framing as image 1')}). "
                f"{who + ': keep each character design exactly (face, hair, outfit, colours). ' if cast else ''}"
                f"Draw this moment in that set: {shot['frame']} {STYLE} {self.tone} Vertical 9:16. Keep heads fully inside the "
                f"frame. {NO_TEXT}", imgs))
            self.spent += IMG_PRICE
            print("key", i)
        print(f"pictures spent ~${self.spent:.2f}")

    def video(self):
        self.out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            clips = []
            import voice
            for i, shot in enumerate(self.ep["shots"], 1):
                secs = int(shot["secs"])
                raw = self.out / f"shot{i}.mp4"
                key = self.out / f"key{i}.jpg"
                if shot.get("continues") and not key.exists():  # starts exactly where the last shot ended: no jumps
                    run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.1", "-i", str(self.out / f"shot{i - 1}.mp4"),
                         "-frames:v", "1", "-q:v", "2", str(key)])
                if not raw.exists():
                    raw.write_bytes(animate((self.out / f"key{i}.jpg").read_bytes(),
                                            f"{STYLE} {self.tone} Action: {shot['motion']} Every character keeps exactly the "
                                            f"same face, hair, body and outfit as in the first frame for the whole "
                                            f"shot.{''.join(' ' + self.note(n).strip() for n in shot.get('cast', []) if self.note(n))}"
                                            f" Locked-off camera unless the action "
                                            f"says otherwise. The background set must stay completely still and "
                                            f"unchanged for the whole shot; only characters and effects move. Limited "
                                            f"TV animation: clear poses and holds. {self.talk(shot)}" + (self.say_it(shot) or SOUND), secs))
                    self.spent += secs * PRICE_PER_SECOND
                    print("shot", i)
            # shot lengths fitted to the voice lines (lip-synced shots keep their own length): needs the shots made
            lengths = [p[0] for p in voice.timeline(self.s.slug, self.ep_name)]
            for i, shot in enumerate(self.ep["shots"], 1):
                clips.append(self._finish(self.out / f"shot{i}.mp4", shot, lengths[i - 1], tmp / f"c{i}.mp4",
                                          tmp / f"ov{i}.png"))
            clips.append(self._card(tmp))
            n = len(clips)
            joined = tmp / "joined.mp4"
            run(["ffmpeg", "-v", "error", "-y", *sum((["-i", str(c)] for c in clips), []), "-filter_complex",
                 "".join(f"[{k}:v][{k}:a]" for k in range(n)) + f"concat=n={n}:v=1:a=1[v][a]",
                 "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "19", "-c:a", "aac", str(joined)])
            final = ROOT / "out" / "cartoon" / f"{self.s.slug}-{self.ep_name}.mp4"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(joined), "-c", "copy", "-movflags", "+faststart",
                 str(final)])
        print(f"{final}  video spent ~${self.spent:.2f}")

    def final(self):
        """Teaser (flash-forward + rewind) and vote recap in front of the voiced episode. Free: voices are cached."""
        import numpy as np
        import wave
        import voice
        src = ROOT / "out" / "cartoon" / f"{self.s.slug}-{self.ep_name}-voiced.mp4"
        final = ROOT / "out" / "cartoon" / f"{self.s.slug}-{self.ep_name}-final.mp4"
        lengths = [p[0] for p in voice.timeline(self.s.slug, self.ep_name)]
        starts = [sum(lengths[:i]) for i in range(len(lengths))]
        norm = (f"scale={reel.W}:{reel.H}:force_original_aspect_ratio=increase,crop={reel.W}:{reel.H},"
                f"fps={reel.FPS},format=yuv420p")
        enc = ["-c:v", "libx264", "-crf", "19", "-c:a", "aac", "-ar", "48000", "-ac", "2"]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            parts = []
            t = self.ep.get("teaser")
            if t:
                n, secs = int(t["shot"]), float(t.get("secs", 2.0))
                at = starts[n - 1] + float(t.get("start", max(0.0, lengths[n - 1] - secs)))
                tz, rw = tmp / "teaser.mp4", tmp / "rewind.mp4"
                run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(src), "-t", f"{secs:.2f}",
                     "-vf", norm, "-af", "aresample=48000,afade=t=in:d=0.03", *enc, str(tz)])
                # the rewind: picture plays backwards fast; the sound is NOT reversed (that scratches): the teaser's
                # own sound carries on and fades out under it
                run(["ffmpeg", "-v", "error", "-y", "-i", str(tz), "-ss", f"{at + secs:.2f}", "-t", "0.55",
                     "-i", str(src), "-filter_complex", f"[0:v]reverse,setpts=0.25*PTS,{norm}[v];"
                     "[1:a]aresample=48000,afade=t=out:st=0:d=0.55[a]", "-map", "[v]", "-map", "[a]", "-t", "0.55",
                     *enc, str(rw)])
                parts += [tz, rw]
            r = self.ep.get("recap")
            if r:
                png, wav, rc = tmp / "recap.png", tmp / "recap.wav", tmp / "recap.mp4"
                reel.recap_card(self.s, r["question"], r["options"], r.get("counts", {}), r["chosen"]).save(png)
                v = voice.load_voices(self.s.dir)
                line = voice.say(r.get("line") or f"Last time, you chose {r['chosen']}.", v.get("narrator"))
                line = voice._decode(None, pcm=line, extra="highpass=f=80")       # same cleaning as story lines
                line = voice._fade(line / (np.abs(line).max() or 1) * 0.85, int(voice.MIX * 0.02))
                secs = max(2.6, len(line) / voice.MIX + 0.9)
                n = int(voice.MIX * secs)
                mix = np.zeros(n, np.float32)
                s0 = int(voice.MIX * 0.3)
                mix[s0:s0 + len(line)] += line[: n - s0]
                bedf = self.dir / "sound" / f"{self.ep['shots'][0]['set']}.mp3"   # no dead air: the opening set's bed
                if bedf.exists():
                    b = voice._decode(bedf)
                    b = np.resize(b / (np.sqrt(np.mean(b ** 2)) or 1) * 0.05 * 0.55, n)
                    mix += voice._fade(b, int(voice.MIX * 0.15))
                with wave.open(str(wav), "wb") as w:
                    w.setnchannels(1), w.setsampwidth(2), w.setframerate(voice.MIX)
                    w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
                run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(png), "-i", str(wav), "-t", f"{secs:.2f}",
                     "-vf", norm, "-af", "aresample=48000", *enc, str(rc)])
                parts.append(rc)
            if not parts:
                print("no teaser or recap in the episode yaml: nothing to add")
                return
            story = tmp / "story.mp4"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", norm, "-af", "aresample=48000,afade=t=in:d=0.03", *enc, str(story)])
            parts.append(story)
            k = len(parts)
            run(["ffmpeg", "-v", "error", "-y", *sum((["-i", str(c)] for c in parts), []), "-filter_complex",
                 "".join(f"[{i}:v][{i}:a]" for i in range(k)) + f"concat=n={k}:v=1:a=1[v][a]",
                 "-map", "[v]", "-map", "[a]", *enc, "-movflags", "+faststart", str(final)])
        if voice.audio_check(final, label=final.name):   # qa.py's gate fails the episode on these (render.py)
            print(f"  {final.name}: the audio is not clean (see AUDIO lines); the quality gate will fail it")
        print(final)

    def say_it(self, shot: dict) -> str:
        """Lip-synced shot (speaker has an ElevenLabs voice): the video model speaks the line itself so the mouth
        matches the words; voice.timeline() then swaps that voice for the cast voice with the same timing."""
        import voice
        who, text, entry = voice.lipsync_line(self.s.dir, shot)
        if not who:
            return ""
        return (f" {entry.get('name', who.title())} says, out loud and clearly, exactly these words and nothing else: "
                f"\"{text}\" {'They shout it.' if shot.get('shout') else 'They say it at a normal, calm speaking volume: no shouting, no yelling.'} "
                f"Their mouth moves in sync with every word and closes when they finish. Everyone else "
                f"keeps their mouth closed. Sound: only {entry.get('name', who.title())}'s voice, no music, no other "
                f"voices. No subtitles or written words.")

    def talk(self, shot: dict) -> str:
        """Mouth instructions: the speaker flaps in time with the line, everyone else keeps their mouth shut."""
        import voice
        who, text = voice.speaker_and_text(shot.get("caption", ""))
        if voice.lipsync_line(self.s.dir, shot)[0]:
            return ""
        if who == "narrator":
            return "Nobody speaks in this shot: every character keeps their mouth closed."
        entry = voice.load_cast(self.s.dir).get(who) or {}
        name = entry.get("name", who.title()) if isinstance(entry, dict) else who.title()
        return (f"{name} is talking for most of the shot: their mouth opens and closes clearly in simple cartoon "
                f"lip flaps the whole time they speak, with matching expression. Everyone else keeps their mouth "
                f"closed. No subtitles or written words.")

    def _finish(self, raw: Path, shot: dict, secs: float, out: Path, ov: Path) -> Path:
        """Shot clip of exactly `secs`: a shot that needs more room for its line plays up to 20% slower, then holds."""
        reel.caption_overlay(self.s, shot.get("caption", ""), 1).save(ov)
        have = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     str(raw)], capture_output=True, text=True, check=True).stdout)
        slow = min(1.2, secs / have) if secs > have else 1.0
        fit = f"setpts={slow:.4f}*PTS,tpad=stop_mode=clone:stop_duration={max(0.0, secs - have * slow) + 0.1:.2f},"
        has_audio = False   # the video model's own sound was scratchy and clicked at every cut: voice.py adds the mix
        run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-i", str(ov), "-f", "lavfi", "-i",
             "anullsrc=r=48000:cl=stereo", "-filter_complex",
             f"[0:v]{fit}scale={reel.W}:{reel.H}:force_original_aspect_ratio=increase,crop={reel.W}:{reel.H},"
             f"fps={reel.FPS}[v];[v][1]overlay=0:0,format=yuv420p[vo];"
             + ("[0:a][2:a]amix=inputs=2:duration=first[ao]" if has_audio else "[2:a]anull[ao]"),
             "-map", "[vo]", "-map", "[ao]", "-t", f"{secs:.2f}", "-c:v", "libx264", "-crf", "19",
             "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out)])
        return out

    def _card(self, tmp: Path) -> Path:
        png = self.out / "card.png"
        panel = ROOT / "out" / "cards" / "driftborn-panel-1.png"
        if self.s.slug == "driftborn" and panel.exists():   # Driftborn's sci-fi screen card
            Image.alpha_composite(Image.open(panel).convert("RGBA"),
                                  screen_text(self.s, self.ep)).convert("RGB").save(png)
        else:
            reel.card(self.s, "choice", self.ep).save(png)
        cc = tmp / "card.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(png), "-f", "lavfi", "-i",
             "anullsrc=r=48000:cl=stereo", "-t", "4", "-vf", "format=yuv420p", "-r", str(reel.FPS),
             "-c:v", "libx264", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(cc)])
        return cc


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])


if __name__ == "__main__":
    # extra commands:  recast "<Character Name>"   |   redo <shot numbers...> [--video-only]
    slug, ep, what, *rest = sys.argv[1:]
    e = Episode(slug, ep)
    if what == "recast":
        e.recast(rest[0])
    elif what == "redo":
        e.redo([int(x) for x in rest if x.isdigit()], video_only="--video-only" in rest)
    else:
        {"keys": e.keys, "video": e.video, "final": e.final}[what]()
