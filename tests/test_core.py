import numpy as np
import pytest

from arr import audio
from arr.project import Project, ProjectError, Section


def tone(freq: float, seconds: float, amp: float = 0.5) -> np.ndarray:
    t = np.arange(int(seconds * audio.SR)) / audio.SR
    mono = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return np.stack([mono, mono], axis=1)


def test_versions_are_never_overwritten(tmp_path):
    p = Project.create(tmp_path / "song", "song")
    for expected in ("v001", "v002"):
        version, path = p.new_version("bass", {"op": "import"})
        audio.save(path, tone(110, 0.1))
        p.activate("bass", version)
        assert version == expected
    assert p.versions("bass") == ["v001", "v002"]
    assert p.version_path("bass").name == "v002.flac"

    reloaded = Project.find(p.root / "tracks")
    assert reloaded.tracks["bass"]["active"] == "v002"
    assert reloaded.meta("bass", "v001")["op"] == "import"


def test_unknown_track_and_section(tmp_path):
    p = Project.create(tmp_path / "song", "song")
    p.set_sections([Section("intro", 0.0, 4.0)])
    assert p.section("intro").end == 4.0
    with pytest.raises(ProjectError):
        p.section("refrain")
    with pytest.raises(ProjectError):
        p.version_path("guitar")


def test_save_load_roundtrip(tmp_path):
    a = tone(440, 0.5)
    audio.save(tmp_path / "a.flac", a)
    assert np.allclose(audio.load(tmp_path / "a.flac"), a, atol=1e-4)


def test_mix_applies_gain_and_avoids_clipping():
    a = tone(440, 0.2, amp=0.5)
    quiet = audio.mix([(a, -6.0)])
    assert np.isclose(np.abs(quiet).max(), 0.5 * 10 ** (-6 / 20), atol=1e-3)
    loud = audio.mix([(a, 0.0), (a, 0.0), (a, 0.0)])
    assert np.abs(loud).max() <= 1.0


def test_splice_only_touches_the_range():
    base, patch = tone(220, 3.0), tone(880, 3.0)
    out = audio.splice(base, patch, 1.0, 2.0)
    sr = audio.SR
    assert np.array_equal(out[: sr - 1], base[: sr - 1])
    assert np.array_equal(out[2 * sr + 1 :], base[2 * sr + 1 :])
    assert np.allclose(out[int(1.5 * sr)], patch[int(1.5 * sr)])
    assert len(out) == len(base)


def test_fit_pads_and_trims():
    a = tone(440, 0.1)
    assert len(audio.fit(a, 100)) == 100
    padded = audio.fit(a, len(a) + 50)
    assert len(padded) == len(a) + 50 and not padded[-50:].any()


def test_scale_to_measures_only_the_given_region():
    ref = tone(220, 1.0, amp=0.2)
    x = tone(220, 1.0, amp=0.8)
    x[len(x) // 2 :] *= 3
    first_half = np.arange(len(x)) < len(x) // 2
    out = audio.scale_to(x, ref, first_half)
    assert np.allclose(out[first_half], ref[first_half], atol=1e-4)
    assert np.allclose(audio.scale_to(tone(220, 1.0, amp=0.9), ref), ref, atol=1e-4)
    assert not audio.scale_to(np.zeros_like(ref), ref).any()
