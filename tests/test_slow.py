"""Vrais moteurs sur un signal synthétique : `uv run pytest -m slow`.

Exclus par défaut et de la CI : il faut les modèles installés (`arr models pull`), et pour
le MIDI le séquenceur ALSA. Ils vérifient qu'une machine fraîchement installée fonctionne,
pas la qualité musicale.
"""

import threading
import time

import numpy as np
import pytest

from arr import audio, engines, measure

pytestmark = pytest.mark.slow


def click_song(seconds: float = 12.0, bpm: float = 120.0) -> np.ndarray:
    """Un « morceau » minimal : un clic par temps sur une basse tenue."""
    beat = 60 / bpm
    t = np.arange(int(seconds * audio.SR)) / audio.SR
    bass = (0.2 * np.sin(2 * np.pi * 55 * t)).astype(np.float32)
    song = np.stack([bass, bass], axis=1)
    return audio.add_clicks(song, [(i * beat, i % 4 == 0) for i in range(int(seconds / beat))])


def test_beat_tracker_finds_the_tempo(tmp_path):
    from arr.engines import analysis

    engines.offline()
    path = tmp_path / "clics.flac"
    audio.save(path, click_song())
    beats, _ = analysis.beats(path)
    assert abs(60 / measure.period(beats) - 120) < 1.0


def test_separation_stems_add_up_to_the_song(tmp_path):
    from arr.engines.separation import separate

    engines.offline()
    song = click_song()
    path = tmp_path / "clics.flac"
    audio.save(path, song)
    stems = separate(path, "htdemucs_6s")
    assert set(stems) == {"drums", "bass", "other", "vocals", "guitar", "piano"}
    assert all(len(s) == len(song) for s in stems.values())
    total = sum(stems.values())
    assert np.corrcoef(total[:, 0], song[:, 0])[0, 1] > 0.95


def test_midi_goes_out_and_comes_back_through_the_alsa_loopback():
    """Le vrai `aseqsend` vers le port de bouclage du noyau, relu par le vrai `aseqdump`.

    Aucun matériel et aucune pédale touchée : « Midi Through » existe dès que le module
    snd-seq-dummy est chargé, et c'est ainsi qu'on vérifie la chaîne sans rien brancher.
    """
    from arr import midi

    if not any("Midi Through" in name for _, name in midi.ports()):
        pytest.skip("pas de port « Midi Through » (module snd-seq-dummy absent)")
    heard: list[str] = []
    listening = threading.Thread(target=lambda: heard.extend(midi.events("Midi Through", seconds=4)), daemon=True)
    listening.start()
    time.sleep(1.0)  # aseqdump doit être abonné au port avant l'envoi
    midi.send(midi.program_change(5) + midi.control_change(7, 100), "Midi Through")
    listening.join(6)
    assert any("Program change" in line and "program 4" in line for line in heard), heard
    assert any("Control change" in line and "controller 7, value 100" in line for line in heard), heard
