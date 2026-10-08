"""Créer un projet et y importer de l'audio : init, import."""

import shutil

import numpy as np
import pytest
import soundfile as sf

from arr import audio
from arr.cli import app
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
