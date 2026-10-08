"""Projet et audio : fonctions pures, sur signaux synthétiques."""

import numpy as np
import pytest

from arr import audio
from arr.project import Project, ProjectError, Section
from tests.helpers import tone


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


def test_takes_are_numbered_and_never_reused(tmp_path):
    p = Project.create(tmp_path / "song", "song")
    assert p.takes() == []
    for expected in ("t001", "t002"):
        name, path = p.new_take({"style": "funk"})
        audio.save(path, tone(220, 0.1))
        assert name == expected
    assert p.takes() == ["t001", "t002"] and p.take_meta("t002")["style"] == "funk"
    with pytest.raises(ProjectError):
        p.take_path("t009")


def test_shift_delays_or_advances_at_constant_length():
    a = tone(220, 1.0)
    k = audio.SR // 10
    late, early = audio.shift(a, 0.1), audio.shift(a, -0.1)
    assert len(late) == len(early) == len(a)
    assert not late[:k].any() and np.array_equal(late[k:], a[:-k])
    assert np.array_equal(early[:-k], a[k:]) and not early[-k:].any()


def test_stretch_changes_duration_not_level():
    import shutil

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg absent")
    a = tone(220, 2.0, amp=0.3)
    slow = audio.stretch(a, 0.99)
    assert abs(len(slow) / len(a) - 1 / 0.99) < 0.002
    assert abs(np.abs(slow).max() - 0.3) < 0.05


def test_count_in_leads_to_the_first_downbeat():
    beats = [1.0 + 0.5 * i for i in range(8)]
    ticks = audio.count_in(beats, [1.0, 3.0], bars=1)
    assert [round(t, 2) for t, _ in ticks] == [-1.0, -0.5, 0.0, 0.5]
    assert [accent for _, accent in ticks] == [True, False, False, False]
    assert len(audio.count_in(beats, [1.0, 3.0], bars=2)) == 8


def test_add_clicks_only_touches_click_positions():
    silent = np.zeros((audio.SR, 2), np.float32)
    out = audio.add_clicks(silent, [(0.5, True), (-0.2, False), (5.0, False)])
    assert not out[: int(0.49 * audio.SR)].any() and out[int(0.5 * audio.SR) : int(0.53 * audio.SR)].any()
    assert not out[int(0.6 * audio.SR) :].any() and len(out) == len(silent)


def test_normalize_reaches_the_target_without_clipping():
    import shutil

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg absent")
    quiet, loud = tone(440, 4.0, amp=0.02), tone(440, 4.0, amp=0.6)
    a, gain_a = audio.normalize(quiet, -16.0)
    b, gain_b = audio.normalize(loud, -16.0)
    assert gain_a > 15 and gain_b < 0
    assert abs(audio.loudness(a) - -16.0) < 0.5 and abs(audio.loudness(b) - -16.0) < 0.5
    assert np.allclose(a / np.abs(a).max(), quiet / np.abs(quiet).max(), atol=1e-4)  # un seul gain, forme intacte

    # un son très dynamique : le plafond de crête limite le gain
    spiky = tone(440, 4.0, amp=0.01)
    spiky[1000:1010] = 0.9
    out, _ = audio.normalize(spiky, -16.0)
    assert np.abs(out).max() <= audio.db(-1.0) + 1e-4
    silent, gain = audio.normalize(np.zeros_like(quiet), -16.0)
    assert gain == 0.0 and not silent.any()
