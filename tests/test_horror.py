"""The horror format (series.yaml `format: horror`): narrated second-person parts in short arcs."""
import pytest

from stories import writer
from stories.series import Series


def fake_part(chosen="", arc_end=False, n_scenes=12, seconds=7, words=12, arc_title="The Morgue"):
    line = " ".join(["you"] * words)
    return {"title": "Cold Hands", "chosen": chosen, "death": False, "arc_title": arc_title, "arc_end": arc_end,
            "scenes": [{"image": f"dark corridor, flashlight, shot {i}", "text": line, "seconds": seconds}
                       for i in range(n_scenes)],
            "choice": {"question": "Open it?", "options": {"A": "open the door", "B": "hide"}, "risky": {}},
            "canon": "You found the morgue door locked from the inside.", "caption": "Something knocks back."}


def test_last_draft_uses_horror_and_others_do_not():
    assert writer.is_horror(Series.load("last-draft"))
    for slug in ("compliant", "roll-for-fate", "driftborn"):
        assert not writer.is_horror(Series.load(slug))


def test_prompt_is_second_person_narrated_with_the_format_guide():
    s = Series.load("last-draft")
    p = writer.build_prompt(s, 1, None, writer.decision(s, None, None), [])
    assert "HORROR FORMAT" in p and "SECOND PERSON" in p and "arc 1, part 1" in p
    assert "What makes it work" in p          # HORROR-FORMAT.md is fed in
    assert "Imagine you" in p and "arc_end" in p


def test_arcs_count_parts_and_restart_after_a_twist():
    s = Series.load("last-draft")
    p1 = writer.write_episode(s, None, None, [], ask=lambda p: fake_part())
    assert (p1["arc"], p1["part"], p1["narrated"]) == (1, 1, True)
    p2 = writer.write_episode(s, p1, {"winner": "B", "share": 60, "total": 5}, [p1],
                              ask=lambda p: fake_part("B", arc_title="Something Else"))
    assert (p2["arc"], p2["part"]) == (1, 2) and p2["arc_title"] == "The Morgue"   # one title per arc
    p3 = writer.write_episode(s, p2, {"winner": "A", "share": 70, "total": 5}, [p1, p2],
                              ask=lambda p: fake_part("A", arc_end=True))
    assert p3["arc_end"] is True
    p4 = writer.write_episode(s, p3, {"winner": "A", "share": 70, "total": 5}, [p1, p2, p3],
                              ask=lambda p: fake_part("A", arc_title="The Bridge"))
    assert (p4["arc"], p4["part"], p4["arc_title"]) == (2, 1, "The Bridge")


def test_part_four_must_land_the_twist():
    s = Series.load("last-draft")
    prev = fake_part("A") | {"n": 3, "arc": 1, "part": 3, "chosen": "A"}
    answers = iter([fake_part("A"), fake_part("A", arc_end=True)])
    ep = writer.write_episode(s, prev, {"winner": "A", "share": 80, "total": 4}, [prev], ask=lambda p: next(answers))
    assert ep["part"] == 4 and ep["arc_end"] is True


@pytest.mark.parametrize("bad", [dict(n_scenes=5), dict(seconds=2, words=20), dict(arc_title="")])
def test_bad_parts_are_rejected(bad):
    s = Series.load("last-draft")
    with pytest.raises(RuntimeError):
        writer.write_episode(s, None, None, [], ask=lambda p: fake_part(**bad))
