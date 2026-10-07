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
