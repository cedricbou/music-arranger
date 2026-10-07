"""Prises : render, split d'une prise, graft, share."""

import shutil

import pytest

from arr import audio
from arr.cli import app
from arr.project import Project
from tests.helpers import ABC, fake_render, runner, song_project


def test_render_creates_versioned_takes(tmp_path, monkeypatch):
    p = song_project(tmp_path, monkeypatch)
    assert runner.invoke(app, ["render", "-s", "funk"]).exit_code != 0  # pas encore de partition
    runner.invoke(app, ["transcribe"])
    (p.root / "lyrics.txt").write_text("[Verse]\nla la\n")
    result = runner.invoke(app, ["render", "-s", "funk band", "--seed", "3", "-n", "2"])
    assert result.exit_code == 0, result.output
    assert runner.invoke(app, ["render", "-s", "jazz trio", "--free"]).exit_code == 0

    p = Project.find()
    assert p.takes() == ["t001", "t002", "t003"]
    assert [c["seed"] for c in fake_render.calls] == [3, 4, -1]
    assert fake_render.calls[0]["lyrics"] == "[Verse]\nla la\n" and fake_render.calls[0]["abc"] == ABC.replace(
        "=121", "=120"
    )
    assert p.take_meta("t003") | {"created": ""} == {
        "created": "",
        "model": "fake",
        "mode": "free",
        "style": "jazz trio",
        "seed": 7,
        "score": "score/score.abc",
        "instrumental": False,
    }
    assert audio.duration(p.take_path("t001")) == 4.0 and not (p.root / "takes/rendu.wav").exists()
    listing = runner.invoke(app, ["takes"]).output
    assert "t001" in listing and "fidèle" in listing and "libre" in listing and "jazz trio" in listing


def test_melody_only_strips_chords_but_not_voice_names():
    from arr.engines.yue2 import melody_only

    out = melody_only(ABC)
    assert '"Dm"' not in out and '"C"' not in out and "f4d4z4d4|A4z8e4|" in out
    assert 'name="Vocal Melody"' in out


def test_split_take_then_graft(tmp_path, monkeypatch):
    p = song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["transcribe"])
    runner.invoke(app, ["split"])
    runner.invoke(app, ["render", "-s", "funk"])
    assert runner.invoke(app, ["graft", "t001", "guitar"]).exit_code != 0  # pas encore séparée
    result = runner.invoke(app, ["split", "t001"])
    assert result.exit_code == 0, result.output

    p = Project.find()
    audible = lambda: {n for n, t in Project.find().tracks.items() if not t.get("mute")}
    assert audible() == {"drums", "bass", "guitar", "vocals"}  # les stems de la prise arrivent muets
    meta = p.meta("t001.guitar", "v001")
    assert meta["superposable"] and meta["on_beat"] == 1.0 and meta["offset_ms"] == 100 and meta["speed"] == 1.0
    # la prise était en retard de 100 ms sur l'original : ses stems sont avancés d'autant
    got = audio.load(p.version_path("t001.guitar"))
    k = audio.SR // 10
    assert len(got) == 4 * audio.SR and not got[-k // 2 :].any() and got[: 3 * audio.SR].any()

    assert runner.invoke(app, ["graft", "t001", "guitar"]).exit_code == 0
    assert audible() == {"drums", "bass", "guitar", "vocals", "t001.guitar"}
    assert runner.invoke(app, ["graft", "t001", "drums", "bass", "--replace"]).exit_code == 0
    assert audible() == {"guitar", "vocals", "t001.guitar", "t001.drums", "t001.bass"}
    assert runner.invoke(app, ["graft", "t001", "kazoo"]).exit_code != 0
    assert runner.invoke(app, ["split"]).exit_code == 0  # re-séparer l'original ne touche pas aux greffes
    assert {"t001.guitar", "t001.drums"} <= audible()


def test_split_take_stretches_to_the_original_tempo(tmp_path, monkeypatch):
    from arr.engines import analysis

    song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["transcribe"])
    runner.invoke(app, ["render", "-s", "funk"])
    original = analysis.beats
    # la prise bat 1 % plus vite que l'original
    monkeypatch.setattr(
        analysis,
        "beats",
        lambda path: original(path) if path.name == "original.flac" else ([0.495 * i for i in range(8)], [0.0, 1.98]),
    )
    assert runner.invoke(app, ["split", "t001"]).exit_code == 0
    meta = Project.find().meta("t001.guitar", "v001")
    assert meta["superposable"] and meta["speed"] == 0.99 and meta["offset_ms"] == 0


def test_split_take_off_the_grid_is_flagged(tmp_path, monkeypatch):
    from arr.engines import analysis

    song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["transcribe"])
    runner.invoke(app, ["render", "-s", "funk"])
    original = analysis.beats
    # même tempo, mais la seconde moitié a glissé de 200 ms (une mesure en trop, par exemple)
    drifting = [0.5 * i + (0.2 if i >= 4 else 0.0) for i in range(8)]
    monkeypatch.setattr(
        analysis, "beats", lambda path: original(path) if path.name == "original.flac" else (drifting, [0.0, 2.0])
    )
    result = runner.invoke(app, ["split", "t001"])
    assert result.exit_code == 0, result.output
    meta = Project.find().meta("t001.guitar", "v001")
    assert meta["superposable"] is False and meta["on_beat"] <= 0.5


def test_split_take_at_another_tempo_is_flagged(tmp_path, monkeypatch):
    from arr.engines import analysis

    song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["transcribe"])
    runner.invoke(app, ["render", "-s", "funk", "--free"])
    original = analysis.beats
    monkeypatch.setattr(
        analysis,
        "beats",
        lambda path: original(path) if path.name == "original.flac" else ([0.45 * i for i in range(9)], [0.0, 1.8]),
    )
    result = runner.invoke(app, ["split", "t001"])
    assert result.exit_code == 0, result.output
    assert Project.find().meta("t001.guitar", "v001")["superposable"] is False


def test_share_exports_part_mix_and_backing(tmp_path, monkeypatch):

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg absent")
    p = song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["split"])
    result = runner.invoke(app, ["share", "guitar"])
    assert result.exit_code == 0, result.output
    out = p.root / "export/guitar"
    assert {f.name for f in out.iterdir()} == {"partie.mp3", "mix.mp3", "sans.mp3"}
    assert abs(audio.duration(out / "sans.mp3") - 4.0) < 0.1
