"""Audio en direct : capture, record, calibrate, levels, choix des périphériques."""

import json
import shutil

import numpy as np
import pytest

from arr import audio
from arr.cli import add_track, app
from arr.project import Project, ProjectError
from tests.helpers import (
    chunks_of,
    fake_studio,
    runner,
    tone,
)


def test_gate_keeps_the_song_and_drops_the_silences():
    from arr import studio

    silence = lambda s: np.zeros((int(s * audio.SR), 2), np.float32)
    song = tone(220, 2.0, amp=0.3)
    started = []
    out = studio.gate(
        chunks_of(np.concatenate([silence(1.0), song, silence(5.0), tone(440, 1.0)])),
        silence=3.0,
        on_start=lambda: started.append(True),
    )
    assert started == [True]
    assert 2.2 <= len(out) / audio.SR <= 2.9  # un peu d'avance, un peu de queue, pas le son suivant
    assert not out[: int(0.1 * audio.SR)].any() and out[int(0.5 * audio.SR)].any()

    out = studio.gate(chunks_of(np.concatenate([song, song])), should_stop=lambda: True)
    assert len(out) / audio.SR < 0.2  # arrêt demandé (changement de titre)
    with pytest.raises(ProjectError):
        studio.gate(chunks_of(silence(1.0)))


def test_stereo_picks_requested_or_loudest_pair():
    from arr import studio

    captured = np.zeros((1000, 12), np.float32)
    captured[:, 6], captured[:, 7], captured[:, 0] = 0.3, 0.2, 0.05
    assert np.allclose(studio.stereo(captured, [])[0], [0.3, 0.2])  # paire 7/8, la plus forte
    assert np.allclose(studio.stereo(captured, [1, 2])[0], [0.05, 0.0])  # paire imposée
    assert studio.stereo(captured, [7]).shape == (1000, 2)  # mono dupliqué


def test_capture_creates_a_project_named_after_the_song(tmp_path, monkeypatch):
    quiet = np.zeros((audio.SR, 2), np.float32)
    # 1 s de silence, le morceau (2 s), puis le morceau suivant enchaîné sans silence
    heard = np.concatenate([quiet, tone(220, 2.0, amp=0.3), tone(880, 3.0, amp=0.3)])
    calls = fake_studio(monkeypatch, heard)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["capture", "--play"])
    assert result.exit_code == 0, result.output
    p = Project(tmp_path / "freed-from-desire")
    assert p.song["title"] == "Freed From Desire" and p.song["artist"] == "Gala"
    assert calls["restart"] == ["/t/1"] and calls["pause"] == 1
    # coupé à la durée annoncée par Spotify (+ marge) : le morceau suivant n'y est presque pas
    assert 2.0 <= p.song["duration"] <= 3.3
    assert runner.invoke(app, ["capture", "freed-from-desire"]).exit_code != 0  # n'écrase pas un projet


def test_record_plays_backing_with_count_in_and_compensates_latency(tmp_path, monkeypatch):
    from arr import studio

    fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "drums", tone(110, 4.0, amp=0.1), {"op": "split"})
    add_track(p, "bass", tone(55, 4.0, amp=0.1), {"op": "split"})
    # temps toutes les 0,5 s à partir de 0,5 s : un décompte de 4 temps doit commencer à -1,5 s
    beats = [0.5 * i + 0.5 for i in range(7)]
    (p.root / "analysis.json").write_text(json.dumps({"beats": beats, "downbeats": [0.5, 2.5]}))
    monkeypatch.chdir(p.root)
    heard = {}

    def fake_duplex(playback, channel):
        heard["playback"], heard["channel"] = playback, channel
        # le musicien « joue » un son reconnaissable, que la carte restitue 100 ms en retard
        played = np.concatenate([np.zeros((int(1.5 * audio.SR), 2), np.float32), tone(880, 4.0, amp=0.2)])
        return audio.shift(audio.fit(played, len(playback)), 0.1), 0.1

    monkeypatch.setattr(studio, "play_and_record", fake_duplex)
    result = runner.invoke(app, ["record", "bass", "--channel", "3"])
    assert result.exit_code == 0, result.output

    playback = heard["playback"]
    assert heard["channel"] == 3 and len(playback) == int(5.5 * audio.SR)  # 1,5 s de décompte en plus
    lead = playback[: int(1.5 * audio.SR)]
    assert (
        np.abs(lead).max() > 0.3 and not lead[int(0.1 * audio.SR) : int(0.4 * audio.SR)].any()
    )  # des clics, pas de musique
    body = playback[int(1.6 * audio.SR) : int(1.9 * audio.SR)]
    assert np.allclose(
        body, tone(110, 4.0, amp=0.1)[int(0.1 * audio.SR) : int(0.4 * audio.SR)], atol=1e-3
    )  # batterie seule, sans la basse

    p = Project.find()
    assert p.versions("bass") == ["v001", "v002"] and p.meta("bass", "v002")["latency_ms"] == 100
    take = audio.load(p.version_path("bass"))
    assert len(take) == 4 * audio.SR
    assert np.allclose(
        take[: 3 * audio.SR], tone(880, 4.0, amp=0.2)[: 3 * audio.SR], atol=1e-3
    )  # calé sur le début du morceau


def test_calibrate_measures_and_saves_the_round_trip(tmp_path, monkeypatch):
    from arr import studio

    fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    monkeypatch.setattr(studio, "CONFIG", tmp_path / "audio.toml")
    (tmp_path / "audio.toml").write_text('[output]\ndevice = "X"\n')
    monkeypatch.setattr(studio, "play_and_record", lambda playback, channel: (audio.shift(playback, 0.0375) * 0.5, 0.0))
    result = runner.invoke(app, ["calibrate"])
    assert result.exit_code == 0, result.output
    saved = (tmp_path / "audio.toml").read_text()
    assert "latency_ms = 37.5" in saved and 'device = "X"' in saved  # les autres réglages restent

    monkeypatch.setattr(studio, "play_and_record", lambda playback, channel: (np.zeros_like(playback), 0.0))
    assert runner.invoke(app, ["calibrate"]).exit_code != 0  # rien n'est revenu : pas de valeur écrite
    assert "latency_ms = 37.5" in (tmp_path / "audio.toml").read_text()


def test_capture_source_follows_the_setup(monkeypatch):
    from arr import studio

    known = [
        ("alsa_output.presonus.monitor", 2),
        ("alsa_output.Soundcraft.monitor", 12),
        ("alsa_input.Soundcraft.multi", 14),
    ]
    monkeypatch.setattr(studio, "sources", lambda: known)
    monkeypatch.setattr(studio, "default_monitor", lambda: known[0])
    setting = {"source": ""}
    monkeypatch.setattr(studio, "config", lambda: {"capture": setting})
    assert studio.capture_source() == ("alsa_input.Soundcraft.multi", 14)  # les entrées de la table, pas son moniteur
    setting["source"] = "monitor"
    assert studio.capture_source() == ("alsa_output.presonus.monitor", 2)
    setting["source"] = "alsa_output.Soundcraft.monitor"
    assert studio.capture_source() == ("alsa_output.Soundcraft.monitor", 12)
    setting["source"] = "nope"
    with pytest.raises(ProjectError):
        studio.capture_source()
    monkeypatch.setattr(studio, "sources", lambda: known[:1])
    setting["source"] = ""
    assert studio.capture_source() == known[0]  # sans la table : copie numérique de la sortie


def test_levels_reports_each_channel(monkeypatch):
    heard = np.zeros((audio.SR, 4), np.float32)
    heard[:, 2] = audio.db(-12) * np.sign(np.sin(np.arange(audio.SR)))  # canal 3 : bon niveau
    heard[:, 3] = 1.0  # canal 4 : sature
    fake_studio(monkeypatch, heard)
    result = runner.invoke(app, ["levels", "--seconds", "0.5"])
    assert result.exit_code == 0, result.output
    lines = [line for line in result.output.splitlines() if "canal" in line and "crête" in line]
    assert "rien" in lines[0] and "-12.0 dB  bon niveau" in lines[2] and "SATURE" in lines[3]
    assert runner.invoke(app, ["levels", "--seconds", "0.2", "--source", "nope"]).exit_code != 0


def test_record_refuses_a_silent_take(tmp_path, monkeypatch):
    from arr import studio

    fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "drums", tone(110, 1.0, amp=0.1), {"op": "split"})
    monkeypatch.chdir(p.root)
    monkeypatch.setattr(studio, "play_and_record", lambda playback, channel: (np.zeros_like(playback), 0.0))
    result = runner.invoke(app, ["record", "bass", "--count-in", "0"])
    assert result.exit_code != 0 and "bass" not in Project.find().tracks


def test_duplex_devices_come_from_the_same_driver(monkeypatch):
    import sounddevice as sd

    from arr import studio

    devices = [
        {"name": "default", "hostapi": 0, "max_input_channels": 2, "max_output_channels": 2},
        {"name": "PreSonus", "hostapi": 1, "max_input_channels": 2, "max_output_channels": 2},
        {"name": "Soundcraft MTK", "hostapi": 1, "max_input_channels": 14, "max_output_channels": 12},
    ]
    apis = [
        {"name": "ALSA", "default_input_device": 0, "default_output_device": 0},
        {"name": "JACK Audio Connection Kit", "default_input_device": 1, "default_output_device": 1},
    ]
    monkeypatch.setattr(sd, "query_devices", lambda i=None: devices if i is None else devices[i])
    monkeypatch.setattr(sd, "query_hostapis", lambda i=None: apis if i is None else apis[i])
    table, system = {"device": "Soundcraft", "channels": [1]}, {"device": "", "channels": [1, 2]}

    # entrée sur la table, sortie « par défaut » : celle du même pilote, pas celle d'ALSA
    assert studio.duplex_devices(table, system, [7]) == (2, 1)
    assert studio.duplex_devices(system, {"device": "Soundcraft", "channels": [7, 8]}, [1]) == (1, 2)
    assert studio.duplex_devices(system, system, [1]) == (None, None)
    with pytest.raises(ProjectError):
        studio.duplex_devices({"device": "Soundcraft", "channels": [1]}, system, [20])  # canal inexistant


def test_capture_brings_every_song_to_the_same_loudness(tmp_path, monkeypatch):

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg absent")
    monkeypatch.chdir(tmp_path)
    for name, amp in (("faible", 0.02), ("fort", 0.5)):
        fake_studio(monkeypatch, tone(220, 3.0, amp=amp))
        result = runner.invoke(app, ["capture", name])
        assert result.exit_code == 0 and "LUFS" in result.output, result.output
    level = lambda name: audio.loudness(audio.load(tmp_path / name / "source/original.flac"))
    assert abs(level("faible") - -16.0) < 0.5 and abs(level("fort") - -16.0) < 0.5

    fake_studio(monkeypatch, tone(220, 3.0, amp=0.02))
    assert runner.invoke(app, ["capture", "brut", "--raw"]).exit_code == 0
    assert level("brut") < -30  # niveau d'origine conservé


def test_loop_block_wraps_to_the_loop_start():
    from arr import studio

    data = np.arange(10, dtype=np.float32)[:, None].repeat(2, axis=1)  # 4 de décompte, boucle sur 4..9
    block, position = studio.loop_block(data, 0, 8, loop_from=4)
    assert block[:, 0].tolist() == [0, 1, 2, 3, 4, 5, 6, 7] and position == 8
    block, position = studio.loop_block(data, position, 8, loop_from=4)
    assert block[:, 0].tolist() == [8, 9, 4, 5, 6, 7, 8, 9] and position == 10
    block, position = studio.loop_block(data, position, 15, loop_from=4)  # un bloc plus long que la boucle
    assert block[:, 0].tolist() == [4, 5, 6, 7, 8, 9] * 2 + [4, 5, 6] and position == 7
