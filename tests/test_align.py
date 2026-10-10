"""Calage : mesurer où se place une prise (time_map), le corriger (align) ou le régler à la main (nudge)."""

import json

import numpy as np
import pytest

from arr import audio, measure
from arr.cli import add_track, app
from arr.commands._common import load_track
from arr.project import Project, ProjectError, Section
from tests.helpers import chord_song, fake_studio, runner, tone

SR = audio.SR
BEAT, BAR = 0.5, 2.0  # chord_song() est à 120 à la noire


def skewed_take(song: np.ndarray) -> np.ndarray:
    """La prise que YuE2 pourrait rendre : un temps d'avance, puis une mesure jouée deux fois à 24 s."""
    early = song[int(BEAT * SR) : int(24 * SR)]
    repeated_bar = song[int(22 * SR) : int(24 * SR)]
    return audio.fit(np.concatenate([early, repeated_bar, song[int(24 * SR) :]]), len(song))


def test_time_map_sees_a_whole_beat_and_an_extra_bar():
    song = chord_song()
    windows = measure.time_map(song, skewed_take(song))
    first, second = measure.by_section(windows, [("a", 0.0, 24.0), ("b", 24.0, 48.0)])
    # une comparaison des seuls temps dirait « calé » : un temps d'avance tombe sur les temps
    assert abs(first["lag"] - -BEAT) < 0.02 and not first["ambiguous"]
    assert abs(second["lag"] - (BAR - BEAT)) < 0.02 and not second["ambiguous"]
    assert measure.within(windows) == 0.0
    assert measure.within(measure.time_map(song, song)) == 1.0


def test_by_section_resolves_a_repeating_passage_by_continuity():
    def window(time, lag):
        return {"time": time, "lag": lag, "confidence": 0.5, "harmony": 0.5}

    windows = [window(4, 1.30), window(8, 1.29)]
    windows += [window(12, 1.30), window(16, -2.31), window(20, 1.31), window(24, -2.30)]  # deux placements se valent
    windows += [window(30, 0.4), window(34, -0.4)]  # rien ne prolonge ce qui précède
    windows += [{"time": 40, "lag": 5.0, "confidence": 0.01, "harmony": 0.1}]  # peu fiable : ignorée
    a, b, c, d = measure.by_section(windows, [("a", 0, 10), ("b", 10, 28), ("c", 28, 38), ("d", 38, 50)])
    assert abs(a["lag"] - 1.295) < 1e-6 and not a["guessed"]
    assert abs(b["lag"] - 1.305) < 1e-6 and b["guessed"] and not b["ambiguous"] and b["spread"] > 3
    assert c["ambiguous"] and not c["guessed"]  # rien à prolonger : reste ambiguë
    assert d["lag"] is None and d["windows"] == 0


def test_nudged_shifts_the_whole_track_or_one_range():
    data = np.concatenate([tone(110, 1.0), tone(220, 1.0), tone(440, 1.0)])
    assert audio.nudged(data, 0.0, []) is data
    later = audio.nudged(data, 0.1, [])
    assert len(later) == len(data) and np.array_equal(later[SR // 10 :], data[: -SR // 10])

    out = audio.nudged(data, 0.0, [(1.0, 2.0, -0.25)])  # la plage du milieu joue 250 ms plus tôt
    inside = slice(int(1.1 * SR), int(1.7 * SR))
    assert np.array_equal(out[inside], data[int(1.35 * SR) : int(1.95 * SR)])
    assert np.array_equal(out[: int(0.9 * SR)], data[: int(0.9 * SR)])  # le reste ne bouge pas
    assert np.array_equal(out[int(2.1 * SR) :], data[int(2.1 * SR) :])
    assert not out[SR].any() and not out[2 * SR - 1].any()  # fondu aux deux raccords


def take_project(tmp_path, monkeypatch):
    """Un projet dont la prise t001 est décalée comme `skewed_take`."""
    song = chord_song()
    p = Project.create(tmp_path / "song", "song")
    audio.save(p.root / "source/original.flac", song)
    grid = {"beats": [BEAT * i for i in range(96)], "downbeats": [BAR * i for i in range(24)]}
    (p.root / "analysis.json").write_text(json.dumps(grid))
    p.set_sections([Section("verse", 0.0, 24.0), Section("chorus", 24.0, 48.0)])
    audio.save(p.new_take({"style": "x", "mode": "close", "seed": 1})[1], skewed_take(song))
    add_track(p, "vocals", song, {"op": "split"})
    add_track(p, "t001.vocals", skewed_take(song) * 0.5, {"op": "split"})
    add_track(p, "t001.drums", skewed_take(song) * 0.5, {"op": "split"})
    for track in ("t001.vocals", "t001.drums"):
        p.tracks[track]["mute"] = True
    p.save()
    monkeypatch.chdir(p.root)
    return p


def test_align_measures_then_stores_the_correction_as_nudges(tmp_path, monkeypatch):
    p = take_project(tmp_path, monkeypatch)
    before = (p.root / "tracks/t001.vocals/v001.flac").read_bytes()

    result = runner.invoke(app, ["align", "t001", "--report"])
    assert result.exit_code == 0, result.output
    assert Project.find().nudges("t001.vocals") == []  # --report ne règle rien

    result = runner.invoke(app, ["align", "t001"])
    assert result.exit_code == 0, result.output
    p = Project.find()
    rules = {n["scope"]: n for n in p.nudges("t001.vocals")}
    assert p.nudges("t001.drums") == p.nudges("t001.vocals")  # les stems d'une prise partagent leur calage
    assert all(n["by"] == "align" for n in rules.values())
    base = rules["track"]["ms"]
    placed = {s.name: base + rules.get(s.name, {"ms": 0.0})["ms"] for s in p.sections}
    assert abs(placed["verse"] - 500) <= 20  # un temps d'avance : jouer un temps plus tard
    assert abs(placed["chorus"] - -1500) <= 20  # trois temps de retard après la mesure en trop

    # les fichiers ne changent pas ; c'est le chargement qui applique le calage
    assert (p.root / "tracks/t001.vocals/v001.flac").read_bytes() == before
    fixed = measure.time_map(audio.load(p.root / "source/original.flac"), load_track(p, "t001.vocals"))
    assert measure.within(fixed) >= 0.8

    # relancer remplace les réglages automatiques et garde les manuels
    assert runner.invoke(app, ["nudge", "t001.vocals", "-s", "verse", "--ms=7"]).exit_code == 0
    assert runner.invoke(app, ["align", "t001"]).exit_code == 0
    rules = {n["scope"]: n for n in Project.find().nudges("t001.vocals")}
    assert rules["verse"] == {"scope": "verse", "ms": 7.0, "by": "manual"}
    assert runner.invoke(app, ["align", "t009"]).exit_code != 0


def test_nudge_sets_replaces_adds_and_resets(tmp_path, monkeypatch):
    p = take_project(tmp_path, monkeypatch)
    assert "aucun calage" in runner.invoke(app, ["nudge"]).output

    assert runner.invoke(app, ["nudge", "t001.vocals", "--beats=+1"]).exit_code == 0
    assert Project.find().nudges("t001.vocals") == [{"scope": "track", "ms": 500.0, "by": "manual"}]
    assert runner.invoke(app, ["nudge", "t001.vocals", "-s", "chorus", "--beats=-4"]).exit_code == 0
    assert runner.invoke(app, ["nudge", "t001.vocals", "-s", "chorus", "--ms=-1990"]).exit_code == 0  # remplace
    assert runner.invoke(app, ["nudge", "t001.vocals", "-s", "chorus", "--add", "--ms=-10"]).exit_code == 0  # ajuste
    rules = {n["scope"]: n["ms"] for n in Project.find().nudges("t001.vocals")}
    assert rules == {"track": 500.0, "chorus": -2000.0}

    listing = runner.invoke(app, ["nudge", "t001.vocals"]).output
    assert "toute la piste" in listing and "+1.00 temps (+500 ms)" in listing
    assert "chorus" in listing and "-4.00 temps (-2000 ms)" in listing and "manuel" in listing
    assert "calée" in runner.invoke(app, ["tracks"]).output

    # une prise entière : tous ses stems
    assert runner.invoke(app, ["nudge", "t001", "-s", "verse", "--ms=5"]).exit_code == 0
    p = Project.find()
    assert {"scope": "verse", "ms": 5.0, "by": "manual"} in p.nudges("t001.drums")
    assert {"scope": "verse", "ms": 5.0, "by": "manual"} in p.nudges("t001.vocals")

    # annuler une portée, puis tout
    assert runner.invoke(app, ["nudge", "t001.vocals", "-s", "chorus", "--reset"]).exit_code == 0
    assert {n["scope"] for n in Project.find().nudges("t001.vocals")} == {"track", "verse"}
    assert runner.invoke(app, ["nudge", "t001", "--reset"]).exit_code == 0
    p = Project.find()
    assert p.nudges("t001.vocals") == [] and p.nudges("t001.drums") == [] and "nudges" not in p.tracks["t001.vocals"]

    for bad in (
        ["nudge", "t001.vocals", "-s", "nope", "--ms=5"],
        ["nudge", "--ms=5"],
        ["nudge", "nope"],
        ["nudge", "t001.vocals", "--ms=5", "--beats=1"],
        ["nudge", "--reset"],
    ):
        assert runner.invoke(app, bad).exit_code != 0, bad
    assert Project.find().nudges("t001.vocals") == []


def test_nudges_reach_the_mix_and_playback(tmp_path, monkeypatch):
    p = take_project(tmp_path, monkeypatch)
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    raw = audio.load(p.version_path("t001.vocals"))
    assert runner.invoke(app, ["nudge", "t001.vocals", "--ms=100"]).exit_code == 0
    assert runner.invoke(app, ["play", "t001.vocals"]).exit_code == 0
    assert np.allclose(calls["played"][0], audio.shift(raw, 0.1), atol=1e-4)
    assert runner.invoke(app, ["mix", "--only", "t001.vocals"]).exit_code == 0
    assert np.allclose(audio.load(p.root / "mix/mix.flac"), audio.shift(raw, 0.1), atol=1e-3)


def test_nudge_in_beats_needs_a_known_tempo(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "bass", tone(55, 1.0), {"op": "record"})
    monkeypatch.chdir(p.root)
    assert runner.invoke(app, ["nudge", "bass", "--beats=1"]).exit_code != 0
    assert runner.invoke(app, ["nudge", "bass", "--ms=30"]).exit_code == 0
    assert "+30 ms" in runner.invoke(app, ["nudge", "bass"]).output
    with pytest.raises(ProjectError):
        Project.find().set_nudge("nope", "track", 5)
