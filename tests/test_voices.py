"""Every recurring character must have a voice that fits them and their world."""
import pytest

import voice

SERIES = ["compliant", "driftborn", "last-draft", "roll-for-fate"]


@pytest.mark.parametrize("slug", SERIES)
def test_every_character_has_a_voice(slug):
    assert voice.missing(slug) == []


@pytest.mark.parametrize("slug", SERIES)
def test_voices_have_brief_and_free_stand_in(slug):
    cast = voice.load_cast(voice.ROOT / slug)
    assert "narrator" in cast
    for who, v in cast.items():
        assert v.get("brief") and v.get("kokoro"), who
