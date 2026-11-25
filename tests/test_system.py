"""Machine et modèles : devices, doctor, et l'installation d'audio.cpp sur une fausse release."""

from arr.cli import app
from tests.helpers import runner


def test_devices_shows_effective_settings_and_hardware(monkeypatch):
    import sounddevice as sd

    from arr import studio

    monkeypatch.setattr(
        studio,
        "config",
        lambda: {
            "output": {"device": "", "channels": [1, 2]},
            "input": {"device": "Soundcraft", "channels": [3], "latency_ms": 68.0},
            "capture": {"source": "", "channels": [7, 8], "loudness": -16.0},
        },
    )
    monkeypatch.setattr(studio, "capture_source", lambda: ("alsa_input.table", 14))
    monkeypatch.setattr(studio, "sources", lambda: [("alsa_input.table", 14), ("alsa_output.carte.monitor", 2)])
    devices = [
        {"name": "default", "hostapi": 0, "max_input_channels": 2, "max_output_channels": 2},
        {"name": "Soundcraft MTK", "hostapi": 1, "max_input_channels": 14, "max_output_channels": 12},
    ]
    apis = [{"name": "ALSA"}, {"name": "JACK Audio Connection Kit"}]
    monkeypatch.setattr(sd, "query_devices", lambda i=None: devices if i is None else devices[i])
    monkeypatch.setattr(sd, "query_hostapis", lambda i=None: apis if i is None else apis[i])

    result = runner.invoke(app, ["devices"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "sortie    par défaut  canaux [1, 2]" in out
    assert "entrée    Soundcraft  canaux [3]  latence 68.0 ms (mesurée)" in out
    assert "capture   alsa_input.table  canaux [7, 8]  volume cible -16 LUFS" in out
    assert "alsa_output.carte.monitor  (2 canaux)" in out
    assert "Soundcraft MTK  (14 entrées, 12 sorties)" in out and "default  (" not in out  # seuls ceux de JACK


def test_doctor_fails_clearly_without_the_gpu(monkeypatch):
    import torch

    monkeypatch.setattr(torch.xpu, "is_available", lambda: False)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1 and "xpu: indisponible" in result.output


def test_check_reports_levels_and_anomalies(tmp_path, monkeypatch):
    import shutil

    import numpy as np
    import pytest

    from arr import audio
    from arr.cli import add_track
    from arr.project import Project
    from tests.helpers import tone

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg absent")
    p = Project.create(tmp_path / "song", "song")
    audio.save(p.root / "source/original.flac", tone(220, 2.0, amp=0.5))
    add_track(p, "drums", tone(110, 2.0, amp=0.5), {"op": "split"})
    add_track(p, "vide", np.zeros((2 * audio.SR, 2), np.float32), {"op": "record"})
    add_track(p, "courte", tone(330, 1.0, amp=0.1), {"op": "import"})
    add_track(p, "t001.guitar", tone(330, 2.0, amp=0.1), {"op": "split", "superposable": False})
    add_track(p, "t001.bass", tone(110, 2.0, amp=0.1), {"op": "split", "superposable": False, "on_beat": 0.26})
    monkeypatch.chdir(p.root)
    monkeypatch.setenv("COLUMNS", "200")

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0, result.output
    line = lambda name: next(row for row in result.output.splitlines() if row.startswith(name))
    assert "2.0 s" in line("original") and "-6.0 dB" in line("original") and "LUFS" in line("original")
    assert "silencieux" in line("vide") and "LUFS" not in line("vide")
    assert "longueur différente de l'original (-1.00 s)" in line("courte")
    assert "non superposable" in line("t001.guitar")
    assert "non superposable" not in line("t001.bass")
    assert "silencieux" not in line("drums") and "longueur" not in line("drums")


def audiocpp_archive(tmp_path, monkeypatch, releases):
    """Une fausse release par version : l'archive est locale, l'API GitHub ne répond que ce qu'on lui a donné."""
    import hashlib
    import tarfile
    import urllib.request

    from arr import engines
    from arr.commands import system

    monkeypatch.setattr(engines, "AUDIOCPP", tmp_path / "home/audiocpp/current/audiocpp_cli")
    asked = []

    def release(version):
        asked.append(version)
        version = version or releases[-1]
        binary = tmp_path / "audiocpp_cli"
        binary.write_text(version)
        archive = tmp_path / f"{version}.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(binary, arcname="audiocpp_cli")
        return version, str(archive), hashlib.sha256(archive.read_bytes()).hexdigest()

    monkeypatch.setattr(system, "audiocpp_release", release)
    monkeypatch.setattr(urllib.request, "urlretrieve", lambda url: (url, None))
    return asked


def test_audiocpp_follows_the_latest_release_and_keeps_the_others(tmp_path, monkeypatch):
    from arr import engines
    from arr.commands import system
    from arr.engines import yue2

    asked = audiocpp_archive(tmp_path, monkeypatch, ["v0.9.0", "v0.9.1"])
    assert system.install_audiocpp("v0.9.0") == "v0.9.0"
    assert system.install_audiocpp() == "v0.9.1"
    monkeypatch.setattr(yue2, "AUDIOCPP", engines.AUDIOCPP)
    assert engines.AUDIOCPP.read_text() == "v0.9.1" and yue2.version() == "v0.9.1"
    assert engines.AUDIOCPP.stat().st_mode & 0o111

    # revenir à une version déjà installée ne demande rien au réseau
    asked.clear()
    assert system.install_audiocpp("v0.9.0") == "v0.9.0"
    assert asked == [] and engines.AUDIOCPP.read_text() == "v0.9.0"
    assert (engines.AUDIOCPP.parents[1] / "v0.9.1/audiocpp_cli").exists()


def test_audiocpp_with_another_checksum_is_refused(tmp_path, monkeypatch):
    import pytest

    from arr import engines
    from arr.commands import system
    from arr.project import ProjectError

    audiocpp_archive(tmp_path, monkeypatch, ["v0.9.0", "v0.9.1"])
    system.install_audiocpp("v0.9.0")
    honest = system.audiocpp_release
    monkeypatch.setattr(system, "audiocpp_release", lambda version: (*honest(version)[:2], "0" * 64))
    with pytest.raises(ProjectError, match="empreinte inattendue"):
        system.install_audiocpp()
    assert engines.AUDIOCPP.read_text() == "v0.9.0"
    assert not (engines.AUDIOCPP.parents[1] / "v0.9.1").exists()


def test_audiocpp_release_reads_the_portable_vulkan_archive(monkeypatch):
    import io
    import json
    import urllib.request

    import pytest

    from arr.commands import system
    from arr.project import ProjectError

    assets = [
        {"name": "audio-v0.9.1-bin-ubuntu-x64-vulkan.tar.gz", "browser_download_url": "non", "digest": "sha256:aa"},
        {
            "name": "audio-v0.9.1-bin-ubuntu-x64-vulkan-portable.tar.gz",
            "browser_download_url": "oui",
            "digest": "sha256:bb",
        },
    ]
    urls = []

    def urlopen(url):
        urls.append(url)
        return io.BytesIO(json.dumps({"tag_name": "v0.9.1", "assets": assets}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    assert system.audiocpp_release("") == ("v0.9.1", "oui", "bb")
    assert system.audiocpp_release("v0.9.1")[0] == "v0.9.1"
    assert [u.rsplit("releases/")[1] for u in urls] == ["latest", "tags/v0.9.1"]
    del assets[1]
    with pytest.raises(ProjectError, match="pas d'archive"):
        system.audiocpp_release("")


def test_doctor_reports_each_engine(tmp_path, monkeypatch):
    import torch

    from arr import engines
    from arr.engines import analysis, yue2
    from arr.project import ProjectError

    def absent():
        raise ProjectError("poids de beat_this absents (arr models pull)")

    cli = tmp_path / "audiocpp/v0.9.1/audiocpp_cli"
    cli.parent.mkdir(parents=True)
    cli.touch()
    (tmp_path / "audiocpp/current").symlink_to("v0.9.1")
    monkeypatch.setattr(engines, "AUDIOCPP", tmp_path / "audiocpp/current/audiocpp_cli")
    monkeypatch.setattr(yue2, "AUDIOCPP", engines.AUDIOCPP)
    monkeypatch.setattr(engines, "YUE2", tmp_path / "yue2")
    monkeypatch.setattr(analysis, "checkpoint", absent)
    randn = torch.randn
    monkeypatch.setattr(torch.xpu, "is_available", lambda: True)
    monkeypatch.setattr(torch.xpu, "get_device_name", lambda i: "Arc")
    monkeypatch.setattr(torch, "randn", lambda *shape, device: randn(*shape))

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "audio.cpp: présent (v0.9.1)" in result.output
    assert "YuE2: absent (arr models pull)" in result.output
    assert "beat_this: absent (arr models pull)" in result.output


def test_doubts_lists_the_passages_arr_is_unsure_of(tmp_path, monkeypatch):
    from tests.test_play import doubtful_song

    p = doubtful_song(tmp_path, monkeypatch)
    result = runner.invoke(app, ["doubts"])
    assert result.exit_code == 0, result.output
    lines = [" ".join(line.split()) for line in result.output.splitlines()]
    assert lines == [
        "0:04 mes. 3 à 4 verse temps 3 entendu faiblement (0,70) ; 1 de plus",
        "0:12 mes. 7 chorus temps 3 entendu faiblement (0,85)",
        "3 mesures douteuses sur 8 (38%)",
    ]
    # un morceau analysé avant que les activations ne soient gardées
    (p.root / "analysis_frames.npz").rename(p.root / "ailleurs.npz")
    result = runner.invoke(app, ["doubts"])
    assert result.exit_code != 0 and "lance arr analyze" in str(result.exception)
