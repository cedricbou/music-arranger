"""Pistes et mix : merge, split, tracks, rm, gain, play."""

import json

import numpy as np

from arr import audio
from arr.cli import add_track, app
from arr.project import Project, Section
from tests.helpers import fake_studio, mixed_project, runner, song_project, tone


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


def test_tracks_shows_mix_first_then_muted(tmp_path, monkeypatch):
    mixed_project(tmp_path, monkeypatch)
    out = runner.invoke(app, ["tracks"]).output
    lines = out.splitlines()
    bass = next(line for line in lines if "bass" in line and "v002" in line)
    guitar = next(line for line in lines if "guitar" in line and "v001" in line)
    assert lines.index(bass) < lines.index(guitar)
    assert "sur 2" in bass and "-3.0 dB" in bass and "takes/t001.flac" in bass
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


def test_play_partial_mix(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    for name, f in (("drums", 110), ("bass", 55), ("guitar", 330)):
        add_track(p, name, tone(f, 0.5, amp=0.1), {"op": "split"})
    monkeypatch.chdir(p.root)
    total = lambda *fs: sum(tone(f, 0.5, amp=0.1) for f in fs)

    assert runner.invoke(app, ["play", "--without", "bass"]).exit_code == 0
    assert runner.invoke(app, ["play", "-o", "bass", "-o", "drums"]).exit_code == 0
    assert runner.invoke(app, ["play", "guitar"]).exit_code == 0
    assert np.allclose(calls["played"][0], total(110, 330), atol=1e-3)
    assert np.allclose(calls["played"][1], total(110, 55), atol=1e-3)
    assert np.allclose(calls["played"][2], total(330), atol=1e-3)


def test_play_sections_in_series_looped_after_a_count_in(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    song = np.concatenate([tone(110, 2.0, amp=0.1), tone(220, 2.0, amp=0.1), tone(440, 2.0, amp=0.1)])
    add_track(p, "guitar", song, {"op": "split"})
    p.set_sections([Section("verse", 0.0, 2.0), Section("chorus", 2.0, 4.0), Section("outro", 4.0, 6.0)])
    p.save()
    # 120 à la noire, quatre temps par mesure
    grid = {"beats": [0.5 * i for i in range(12)], "downbeats": [0.0, 2.0, 4.0]}
    (p.root / "analysis.json").write_text(json.dumps(grid))
    audio.save(p.new_take({"style": "x"})[1], tone(220, 1.0))
    monkeypatch.chdir(p.root)
    sr, inside = audio.SR, slice(1000, -1000)

    # une section, une fois
    assert runner.invoke(app, ["play", "-s", "chorus"]).exit_code == 0
    assert len(calls["played"][0]) == 2 * sr and calls["looped"][0] is None
    assert np.allclose(calls["played"][0][inside], song[2 * sr : 4 * sr][inside], atol=1e-3)

    # deux sections dans l'ordre demandé, qui n'est pas celui du morceau
    result = runner.invoke(app, ["play", "guitar", "-s", "outro", "-s", "verse"])
    assert result.exit_code == 0 and "outro → verse" in result.output
    first, second = calls["played"][1][: 2 * sr], calls["played"][1][2 * sr :]
    assert np.allclose(first[inside], song[4 * sr :][inside], atol=1e-3)
    assert np.allclose(second[inside], song[: 2 * sr][inside], atol=1e-3)

    # en boucle après une mesure de décompte : les clics précèdent la section et ne sont pas dans la boucle
    result = runner.invoke(app, ["play", "-s", "chorus", "--loop", "--count-in", "1"])
    assert result.exit_code == 0, result.output
    played, looped = calls["played"][2], calls["looped"][2]
    assert len(played) == 4 * sr and len(looped) == 2 * sr
    lead = played[: 2 * sr]
    for k in range(4):
        assert lead[int(0.5 * k * sr) + 10 : int(0.5 * k * sr) + 500].any()
        assert not lead[int((0.5 * k + 0.1) * sr) : int((0.5 * k + 0.45) * sr)].any()
    assert np.array_equal(played[2 * sr :], looped)
    assert np.allclose(looped[inside], song[2 * sr : 4 * sr][inside], atol=1e-3)

    assert runner.invoke(app, ["play", "-s", "nope"]).exit_code != 0
    # une prise brute n'est pas calée sur l'original
    result = runner.invoke(app, ["play", "t001", "-s", "chorus"])
    assert result.exit_code != 0 and "arr split t001" in str(result.exception)
    assert runner.invoke(app, ["play", "t001", "--loop"]).exit_code == 0
    assert len(calls["played"]) == 4


def test_play_count_in_without_a_known_tempo_only_warns(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "guitar", tone(330, 0.5, amp=0.1), {"op": "split"})
    monkeypatch.chdir(p.root)

    result = runner.invoke(app, ["play", "--count-in", "1"])
    assert result.exit_code == 0 and "pas de décompte" in result.output
    assert len(calls["played"][0]) == audio.SR // 2


def test_rm_moves_tracks_to_the_project_trash(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    for name in ("drums", "bass", "guitar"):
        add_track(p, name, tone(110, 0.2), {"op": "split"})
    add_track(p, "bass", tone(55, 0.2), {"op": "record"})
    monkeypatch.chdir(p.root)

    assert runner.invoke(app, ["rm", "guitar", "nope"]).exit_code != 0
    assert "guitar" in Project.find().tracks  # une erreur ne retire rien

    result = runner.invoke(app, ["rm", "guitar", "drums"])
    assert result.exit_code == 0, result.output
    p = Project.find()
    assert set(p.tracks) == {"bass"} and not (p.root / "tracks/guitar").exists()
    assert len(list((p.root / "trash").glob("*/tracks/guitar/v001.flac"))) == 1  # récupérable

    # retirer la version active rend la précédente active ; retirer la dernière retire la piste
    assert runner.invoke(app, ["rm", "bass", "-v", "v002"]).exit_code == 0
    p = Project.find()
    assert p.versions("bass") == ["v001"] and p.tracks["bass"]["active"] == "v001"
    assert runner.invoke(app, ["rm", "bass", "-v", "v001"]).exit_code == 0
    assert "bass" not in Project.find().tracks and runner.invoke(app, ["tracks"]).exit_code == 0


def test_rm_purge_asks_before_deleting_for_good(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "guitar", tone(330, 0.2), {"op": "split"})
    add_track(p, "piano", tone(440, 0.2), {"op": "split"})
    monkeypatch.chdir(p.root)

    assert runner.invoke(app, ["rm", "--purge", "guitar"], input="n\n").exit_code != 0
    assert "guitar" in Project.find().tracks
    assert runner.invoke(app, ["rm", "--purge", "guitar"], input="o\n").exit_code == 0
    assert "guitar" not in Project.find().tracks and not (p.root / "trash").exists()

    assert runner.invoke(app, ["rm", "piano"]).exit_code == 0 and (p.root / "trash").exists()
    assert runner.invoke(app, ["rm", "trash"]).exit_code != 0  # la corbeille ne se vide qu'avec --purge
    assert runner.invoke(app, ["rm", "--purge", "--yes", "trash"]).exit_code == 0
    assert not (p.root / "trash").exists()


def test_rm_take_removes_its_stems_too(tmp_path, monkeypatch):
    song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["transcribe"])
    runner.invoke(app, ["split"])
    runner.invoke(app, ["render", "-s", "funk", "-n", "2"])
    runner.invoke(app, ["split", "t001"])
    result = runner.invoke(app, ["rm", "t001"])
    assert result.exit_code == 0, result.output
    p = Project.find()
    assert p.takes() == ["t002"] and not any(t.startswith("t001.") for t in p.tracks)
    assert {"drums", "bass", "guitar", "vocals"} <= set(p.tracks)  # les stems de l'original restent
    name, _ = p.new_take({"style": "x"})
    assert name == "t003"  # un numéro de prise n'est jamais réutilisé tant qu'il en reste de plus récentes


def test_gain_accepts_negative_values(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "bass", tone(55, 0.2), {"op": "record"})
    monkeypatch.chdir(p.root)
    for value, expected in (("-5", -5.0), ("+3", 3.0), ("-2.5", -2.5), ("0", 0.0)):
        result = runner.invoke(app, ["gain", "bass", value])
        assert result.exit_code == 0, result.output
        assert Project.find().tracks["bass"]["gain"] == expected
    assert runner.invoke(app, ["gain", "bass", "fort"]).exit_code != 0


def test_pick_changes_the_active_version(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "bass", tone(55, 0.2, amp=0.1), {"op": "split"})
    add_track(p, "bass", tone(55, 0.2, amp=0.4), {"op": "record"})
    monkeypatch.chdir(p.root)
    assert Project.find().tracks["bass"]["active"] == "v002"
    assert runner.invoke(app, ["pick", "bass", "v001"]).exit_code == 0
    assert Project.find().tracks["bass"]["active"] == "v001"
    assert runner.invoke(app, ["pick", "bass", "v009"]).exit_code != 0
    assert Project.find().tracks["bass"]["active"] == "v001"


def test_mix_honours_gain_mute_and_selection(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    for name, f in (("drums", 110), ("bass", 55), ("guitar", 330)):
        add_track(p, name, tone(f, 0.5, amp=0.1), {"op": "split"})
    monkeypatch.chdir(p.root)
    mixed = lambda: audio.load(p.root / "mix/mix.flac")

    assert runner.invoke(app, ["gain", "bass", "-6"]).exit_code == 0
    assert runner.invoke(app, ["mute", "guitar"]).exit_code == 0
    assert runner.invoke(app, ["mix"]).exit_code == 0
    assert np.allclose(mixed(), tone(110, 0.5, amp=0.1) + tone(55, 0.5, amp=0.1) * audio.db(-6), atol=1e-3)

    assert runner.invoke(app, ["mix", "--without", "drums"]).exit_code == 0
    assert np.allclose(mixed(), tone(55, 0.5, amp=0.1) * audio.db(-6), atol=1e-3)
    assert runner.invoke(app, ["mix", "--only", "guitar"]).exit_code == 0  # --only passe outre la sourdine
    assert np.allclose(mixed(), tone(330, 0.5, amp=0.1), atol=1e-3)
    assert runner.invoke(app, ["mix", "--only", "nope"]).exit_code != 0
