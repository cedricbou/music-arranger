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
    assert slug("Dieu m'a donné la foi") == "dieu-m-a-donne-la-foi"
    assert slug("Maldòn - Version originale") == "maldon-version-originale"
    assert folder_name("Complicated", "Avril Lavigne") == "avril-lavigne--complicated"
    assert folder_name("What's Up?", "4 Non Blondes") == "4-non-blondes--what-s-up"
    assert folder_name("shepardxp-cover") == "shepardxp-cover"


def test_rename_names_folders_after_artist_and_title_and_follows_setlists(tmp_path, monkeypatch):
    def song(folder, title, artist=None):
        p = Project.create(tmp_path / folder, title)
        if artist:
            p.song["artist"] = artist
        p.save()

    song("complicated", "Complicated", "Avril Lavigne")
    song("dieu-m-a-donn-la-foi", "Dieu m'a donné la foi", "Ophélie Winter")
    song("starlight", "Starlight", "The Supermen Lovers")
    song("the-supermen-lovers--starlight", "Starlight", "The Supermen Lovers")  # le même morceau, capturé deux fois
    song("cover", "cover")
    (tmp_path / "setlists").mkdir()
    setlist = tmp_path / "setlists/bar.toml"
    setlist.write_text(
        'title = "Bar"\nsongs = ["complicated", "---", { song = "dieu-m-a-donn-la-foi", transpose = -2 }, "starlight"]\n'
    )
    monkeypatch.chdir(tmp_path)

    before = sorted(d.name for d in tmp_path.iterdir())
    result = runner.invoke(app, ["rename"], input="n\n")
    assert "complicated  ->  avril-lavigne--complicated" in result.output
    assert "starlight : the-supermen-lovers--starlight existe déjà" in result.output
    assert "cover : pas d'artiste" not in result.output  # déjà au bon nom, rien à dire
    assert sorted(d.name for d in tmp_path.iterdir()) == before  # refusé : rien ne bouge

    result = runner.invoke(app, ["rename"], input="o\n")
    assert result.exit_code == 0, result.output
    assert Project(tmp_path / "avril-lavigne--complicated").song["title"] == "Complicated"
    assert (tmp_path / "ophelie-winter--dieu-m-a-donne-la-foi/song.toml").exists()
    assert (tmp_path / "starlight/song.toml").exists() and (tmp_path / "cover/song.toml").exists()
    assert tomllib.loads(setlist.read_text()) == {
        "title": "Bar",
        "songs": [
            "avril-lavigne--complicated",
            "---",
            {"song": "ophelie-winter--dieu-m-a-donne-la-foi", "transpose": -2},
            "starlight",
        ],
    }
    assert runner.invoke(app, ["rename", "--yes"]).output.endswith("rien à renommer\n")
