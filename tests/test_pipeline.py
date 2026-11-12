import json
import shutil
import subprocess

import pytest

from stories import gemini, reel, votes, writer
from stories.__main__ import caption
from stories.series import SLUGS, Series

T0 = "2026-11-24T00:00:00+0000"


def c(text, user, ts="2026-11-24T05:00:00+0000"):
    return {"text": text, "username": user, "timestamp": ts}


@pytest.mark.parametrize("text,vote", [
    ("A", "A"), ("b", "B"), ("B!", "B"), ("option b because", "B"), ("Option A", "A"), ("going with B for sure", "B"),
    ("a lot of people will die", None), ("I think a stranger is lying", None), ("C", None), ("", None),
])
def test_parse_vote(text, vote):
    assert votes.parse_vote(text, ["A", "B"]) == vote


def test_tally_latest_vote_per_account_window_and_own_account():
    cs = [c("A", "ann"), c("B", "ann", "2026-11-24T06:00:00+0000"),   # ann changed her mind: B
          c("A", "bob"), c("A", "cat"), c("B", "dan"),
          c("B", "late", "2026-11-25T01:00:00+0000"),                 # after 24 h: ignored
          c("A", "series_account")]                                   # our own: ignored
    r = votes.tally(cs, ["A", "B"], T0, own_username="series_account")
    assert r["counts"] == {"A": 2, "B": 2} and r["winner"] is None    # tie -> the story chooses
    r = votes.tally(cs + [c("A", "eve")], ["A", "B"], T0, "series_account")
    assert r["winner"] == "A" and r["share"] == 60


def test_no_comments_means_no_winner():
    assert votes.tally([], ["A", "B"], T0)["winner"] is None


def test_pick_text_model_prefers_newest_plain_flash():
    models = [{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
              {"name": "models/gemini-3.0-flash", "supportedGenerationMethods": ["generateContent"]},
              {"name": "models/gemini-3.1-flash-image", "supportedGenerationMethods": ["generateContent"]},
              {"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]},
              {"name": "models/gemini-3.5-pro", "supportedGenerationMethods": ["generateContent"]}]
    assert gemini.pick_text_model(models) == "gemini-3.0-flash"


def fake_episode(chosen="", death=False, n_scenes=6):
    return {"title": "Static", "chosen": chosen, "death": death,
            "scenes": [{"image": f"Ezra in the stairwell, shot {i}", "text": f"line {i} of the story", "seconds": 7}
                       for i in range(n_scenes)],
            "choice": None if death else {"question": "Report it?", "options": {"A": "report", "B": "follow"},
                                          "risky": {"B": 14}},
            "canon": "Ezra heard Static say Mira's name.", "caption": "The radio knows his sister."}


def test_writer_first_episode_and_vote_result():
    s = Series.load("compliant")
    ep = writer.write_episode(s, None, None, [], ask=lambda p: fake_episode())
    assert ep["n"] == 1 and ep["opening"] == "" and ep["decided_by"] == "first"
    ep2 = writer.write_episode(s, ep, {"winner": "B", "share": 63, "total": 8}, [ep], ask=lambda p: fake_episode("B"))
    assert ep2["n"] == 2 and ep2["opening"] == "YOU CHOSE B (63%)" and ep2["chosen"] == "B"
    assert ep2["asked"] == ep["choice"]


def test_writer_ai_pick_and_rewind_after_death():
    s = Series.load("compliant")
    ep1 = writer.write_episode(s, None, None, [], ask=lambda p: fake_episode())
    prompts = []
    ep2 = writer.write_episode(s, ep1, {"winner": None, "total": 0}, [ep1],
                               ask=lambda p: prompts.append(p) or fake_episode("B", death=True))
    assert "YOU choose" in prompts[0] and ep2["opening"] == "NO VOTES. THE STORY CHOSE B." and ep2["death"]
    ep3 = writer.write_episode(s, ep2, None, [ep1, ep2], ask=lambda p: fake_episode("A"))
    assert ep3["opening"] == "REWIND. THIS TIME: A." and ep3["asked"] == ep1["choice"]


def test_writer_retries_bad_answers_then_fails():
    s = Series.load("compliant")
    answers = iter([fake_episode(n_scenes=2), fake_episode()])
    assert writer.write_episode(s, None, None, [], ask=lambda p: next(answers))["n"] == 1
    with pytest.raises(RuntimeError):
        writer.write_episode(s, None, None, [], ask=lambda p: fake_episode(n_scenes=1))


def test_dice_roll_recorded_for_risky_choice(monkeypatch):
    s = Series.load("roll-for-fate")
    monkeypatch.setattr(writer, "roll_d20", lambda: 7)
    ep1 = writer.write_episode(s, None, None, [], ask=lambda p: fake_episode())
    ep2 = writer.write_episode(s, ep1, {"winner": "B", "share": 100, "total": 1}, [ep1], ask=lambda p: fake_episode("B"))
    assert ep2["roll"] == {"dc": 14, "rolled": 7}


def test_caption_has_vote_line_and_hashtags():
    s = Series.load("last-draft")
    ep = writer.write_episode(s, None, None, [], ask=lambda p: fake_episode())
    t = caption(s, ep)
    assert "Comment A or B" in t and "#zombie" in t and len(t) < 2200


@pytest.mark.parametrize("slug", SLUGS)
def test_every_series_config_loads_and_fonts_exist(slug):
    s = Series.load(slug)
    assert s.font("head").exists() and s.font("body").exists()
    assert s.cfg["live"] is False and s.cfg["secret"].isupper()
    assert s.text("BRAND.md") and s.text("SEASON1.md")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_reel_builds_a_vertical_video(tmp_path):
    s = Series.load("driftborn")
    ep = writer.write_episode(s, None, None, [], ask=lambda p: fake_episode(n_scenes=5))
    ep["opening"] = "YOU CHOSE A (70%)"
    ep["roll"] = {"dc": 12, "rolled": 15}
    pics = [reel.placeholder(s, sc, i) for i, sc in enumerate(ep["scenes"], 1)]
    out = reel.build(s, ep, pics, tmp_path / "ep.mp4")
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                                       str(out)], capture_output=True, text=True, check=True).stdout)
    v = next(x for x in probe["streams"] if x["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert any(x["codec_type"] == "audio" for x in probe["streams"])
    assert 40 < float(probe["format"]["duration"]) < 60


def test_profile_art_prompts_and_square_output(tmp_path, monkeypatch):
    import io

    from PIL import Image

    from stories import art
    s = Series.load("driftborn")
    prompts = art.profile_prompts(s, 3)
    assert len(set(prompts)) == 3 and all("Kael Torvin" in p and "No text" not in p for p in prompts)
    assert all("Absolutely no text" in p and "Square 1:1" in p for p in prompts)

    class FakePainter:
        spent = 0.0

        def picture(self, prompt, aspect="9:16"):
            assert aspect == "1:1"
            buf = io.BytesIO()
            Image.new("RGB", (1200, 1000), "teal").save(buf, "JPEG")
            return buf.getvalue()

    monkeypatch.setattr(art, "OUT", tmp_path)
    paths = art.make_profile(s, 2, painter=FakePainter())
    assert [Image.open(p).size for p in paths] == [(1080, 1080)] * 2
