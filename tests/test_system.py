"""Machine et modèles : devices, doctor. `models pull` installe depuis le réseau : non testé ici."""

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
