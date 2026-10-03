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


def mixed_project(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    a = tone(220, 0.2)
    add_track(p, "guitar", a, {"op": "split", "model": "htdemucs_6s", "source": "source/original.flac"})
    add_track(p, "bass", a, {"op": "split", "model": "htdemucs_6s", "source": "source/original.flac"})
    add_track(p, "bass", a, {"op": "fix", "prompt": "walking fill", "start": 5.0, "end": 10.0})
    p.tracks["guitar"]["mute"] = True
    p.tracks["bass"]["gain"] = -3.0
    p.save()
    monkeypatch.chdir(p.root)


def test_tracks_shows_mix_first_then_muted(tmp_path, monkeypatch):
    mixed_project(tmp_path, monkeypatch)
    out = runner.invoke(app, ["tracks"]).output
    lines = out.splitlines()
    bass = next(l for l in lines if "bass" in l and "v002" in l)
    guitar = next(l for l in lines if "guitar" in l and "v001" in l)
    assert lines.index(bass) < lines.index(guitar)
    assert "sur 2" in bass and "-3.0 dB" in bass and "walking fill [5-10 s]" in bass
    assert "muette" in guitar and "htdemucs_6s" in guitar
    assert "v001" not in bass  # l'historique n'apparaît pas par défaut
    assert "Dans le mix : bass" in out and "1 muette" in out


def test_tracks_history_marks_the_active_version(tmp_path, monkeypatch):
    mixed_project(tmp_path, monkeypatch)
    for args in (["tracks", "-v"], ["tracks", "bass"]):
        out = runner.invoke(app, args).output
        assert "▸ v002" in out and "  v001" in out and "▸ v001" not in out.split("guitar")[0]
    assert "guitar" not in runner.invoke(app, ["tracks", "bass"]).output
    assert runner.invoke(app, ["tracks", "nope"]).exit_code != 0
