import numpy as np
from typer.testing import CliRunner

from arr import audio
from arr.cli import add_track, app
from arr.project import Project
from tests.test_core import tone

runner = CliRunner()


def test_merge_sums_tracks_and_mutes_sources(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    piano, guitar = tone(220, 0.5, amp=0.2), tone(330, 0.5, amp=0.3)
    add_track(p, "piano", piano, {"op": "split"})
    add_track(p, "guitar", guitar, {"op": "split"})
    monkeypatch.chdir(p.root)

    result = runner.invoke(app, ["merge", "piano", "guitar", "--as", "synth"])
    assert result.exit_code == 0, result.output

    p = Project.find()
    assert np.allclose(audio.load(p.version_path("synth")), piano + guitar, atol=1e-4)
    assert p.tracks["piano"]["mute"] and p.tracks["guitar"]["mute"]
    assert p.meta("synth", "v001")["source"] == "piano/v001 + guitar/v001"
    assert p.versions("piano") == ["v001"]


def test_merge_into_one_of_the_sources_keeps_it_audible(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "other", tone(220, 0.5, amp=0.2), {"op": "split"})
    add_track(p, "piano", tone(330, 0.5, amp=0.2), {"op": "split"})
    monkeypatch.chdir(p.root)

    assert runner.invoke(app, ["merge", "other", "piano", "--as", "other"]).exit_code == 0

    p = Project.find()
    assert p.tracks["other"]["active"] == "v002" and not p.tracks["other"]["mute"]
    assert p.tracks["piano"]["mute"]


def test_new_split_replaces_previous_stems_and_merges(tmp_path, monkeypatch):
    from arr.engines import separation

    a = tone(220, 0.5, amp=0.2)
    six = {n: a for n in ("drums", "bass", "other", "vocals", "guitar", "piano")}
    four = {n: a for n in ("drums", "bass", "other", "vocals")}
    monkeypatch.setattr(separation, "separate", lambda path, model, shifts: six if model == "htdemucs_6s" else four)

    p = Project.create(tmp_path / "song", "song")
    audio.save(p.root / "source/original.flac", a)
    monkeypatch.chdir(p.root)
    assert runner.invoke(app, ["split"]).exit_code == 0
    assert runner.invoke(app, ["merge", "guitar", "piano", "other", "--as", "synth"]).exit_code == 0
    result = runner.invoke(app, ["split", "--model", "htdemucs_ft"])
    assert result.exit_code == 0, result.output

    p = Project.find()
    audible = {n for n, t in p.tracks.items() if not t.get("mute")}
    assert audible == {"drums", "bass", "other", "vocals"}
    assert p.tracks["other"]["active"] == "v002"
    assert runner.invoke(app, ["split", "--model", "nope"]).exit_code != 0
