"""Créer un projet, y importer de l'audio, nommer les dossiers : init, import, rename."""

import shutil
import tomllib

import numpy as np
import pytest
import soundfile as sf

from arr import audio
from arr.cli import app
from arr.commands._common import folder_name, slug
from arr.project import Project
from tests.helpers import runner, tone

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg absent")


def wav(path, data, rate=44100):
    """Un fichier à un autre taux que celui du projet, pour vérifier la conversion."""
    step = audio.SR / rate
    sf.write(path, data[(np.arange(int(len(data) / step)) * step).astype(int)], rate)
    return path


def test_init_creates_the_project_and_converts_the_song(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    song = wav(tmp_path / "song.wav", tone(220, 1.0))
    result = runner.invoke(app, ["init", "demo", "--from", str(song)])
    assert result.exit_code == 0, result.output
    p = Project(tmp_path / "demo")
    assert p.song["title"] == "demo" and p.tracks == {}
    original = audio.load(p.root / "source/original.flac")  # 48 kHz stéréo, sinon load() refuse
    assert abs(len(original) / audio.SR - 1.0) < 0.01
    for folder in ("source", "score", "takes", "tracks", "mix", "export"):
        assert (p.root / folder).is_dir()
    assert runner.invoke(app, ["init", "demo"]).exit_code != 0  # n'écrase pas un projet existant


def test_init_warns_when_the_song_is_silent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    silent = wav(tmp_path / "vide.wav", np.zeros((audio.SR, 2), np.float32))
    result = runner.invoke(app, ["init", "demo", "--from", str(silent)])
    assert result.exit_code == 0 and "silencieux" in result.output


def test_import_replaces_the_song_or_adds_a_track(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "demo", "demo")
    monkeypatch.chdir(p.root)
    assert runner.invoke(app, ["import", str(wav(tmp_path / "a.wav", tone(220, 0.5)))]).exit_code == 0
    assert (p.root / "source/original.flac").exists() and Project.find().tracks == {}

    idea = wav(tmp_path / "riff.wav", tone(55, 0.5))
    assert runner.invoke(app, ["import", str(idea), "--as", "bass"]).exit_code == 0
    assert runner.invoke(app, ["import", str(idea), "--as", "bass"]).exit_code == 0
    p = Project.find()
    assert p.versions("bass") == ["v001", "v002"] and p.meta("bass", "v001")["op"] == "import"


def test_song_folders_are_named_artist_then_title():
    assert slug("L'été n'a pas duré") == "l-ete-n-a-pas-dure"
    assert slug("Rivière - Version originale") == "riviere-version-originale"
    assert folder_name("Night Drive", "Paper Lanterns") == "paper-lanterns--night-drive"
    assert folder_name("It's Late?", "4 Walls") == "4-walls--it-s-late"
    assert folder_name("demo-cover") == "demo-cover"


def test_rename_names_folders_after_artist_and_title_and_follows_setlists(tmp_path, monkeypatch):
    def song(folder, title, artist=None):
        p = Project.create(tmp_path / folder, title)
        if artist:
            p.song["artist"] = artist
        p.save()

    song("night-drive", "Night Drive", "Paper Lanterns")
    song("l-t-n-a-pas-dur", "L'été n'a pas duré", "Hélène Faure")
    song("blue-hour", "Blue Hour", "The Night Shifts")
    song("the-night-shifts--blue-hour", "Blue Hour", "The Night Shifts")  # le même morceau, capturé deux fois
    song("cover", "cover")
    (tmp_path / "setlists").mkdir()
    setlist = tmp_path / "setlists/bar.toml"
    setlist.write_text(
        'title = "Bar"\nsongs = ["night-drive", "---", { song = "l-t-n-a-pas-dur", transpose = -2 }, "blue-hour"]\n'
    )
    monkeypatch.chdir(tmp_path)

    before = sorted(d.name for d in tmp_path.iterdir())
    result = runner.invoke(app, ["rename"], input="n\n")
    assert "night-drive  ->  paper-lanterns--night-drive" in result.output
    assert "blue-hour : the-night-shifts--blue-hour existe déjà" in result.output
    assert "cover : pas d'artiste" not in result.output  # déjà au bon nom, rien à dire
    assert sorted(d.name for d in tmp_path.iterdir()) == before  # refusé : rien ne bouge

    result = runner.invoke(app, ["rename"], input="o\n")
    assert result.exit_code == 0, result.output
    assert Project(tmp_path / "paper-lanterns--night-drive").song["title"] == "Night Drive"
    assert (tmp_path / "helene-faure--l-ete-n-a-pas-dure/song.toml").exists()
    assert (tmp_path / "blue-hour/song.toml").exists() and (tmp_path / "cover/song.toml").exists()
    assert tomllib.loads(setlist.read_text()) == {
        "title": "Bar",
        "songs": [
            "paper-lanterns--night-drive",
            "---",
            {"song": "helene-faure--l-ete-n-a-pas-dure", "transpose": -2},
            "blue-hour",
        ],
    }
    assert runner.invoke(app, ["rename", "--yes"]).output.endswith("rien à renommer\n")
